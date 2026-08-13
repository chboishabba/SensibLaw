BEGIN;

-- 103: acquisition-source freshness is a consumer requirement, not a global
-- property of Wikidata. A June snapshot may satisfy historical/static work
-- while a current-office query can require a newer observation. Deduplicated
-- physical requests adopt the strongest freshness floor of all member fibres.

ALTER TABLE execution.semantic_pnf_consumer_external_need
    ADD COLUMN IF NOT EXISTS minimum_source_epoch BIGINT
        CHECK (minimum_source_epoch IS NULL OR minimum_source_epoch > 0);

ALTER TABLE execution.semantic_pnf_external_request
    ADD COLUMN IF NOT EXISTS minimum_source_epoch BIGINT
        CHECK (minimum_source_epoch IS NULL OR minimum_source_epoch > 0);

ALTER TABLE execution.semantic_pnf_external_evidence
    ADD COLUMN IF NOT EXISTS source_epoch BIGINT
        CHECK (source_epoch IS NULL OR source_epoch > 0);

ALTER TABLE execution.semantic_pnf_label_world_candidate
    ADD COLUMN IF NOT EXISTS source_epoch BIGINT
        CHECK (source_epoch IS NULL OR source_epoch > 0),
    ADD COLUMN IF NOT EXISTS source_ref TEXT;

CREATE INDEX IF NOT EXISTS semantic_pnf_external_evidence_fresh_probe_idx
    ON execution.semantic_pnf_external_evidence
       (provider_id,subject_world_entity_id,provider_property_numeric_id,source_epoch DESC)
    WHERE source_epoch IS NOT NULL;

CREATE INDEX IF NOT EXISTS semantic_pnf_label_world_candidate_fresh_idx
    ON execution.semantic_pnf_label_world_candidate
       (label_symbol_id,source_epoch DESC,candidate_ordinal,world_entity_id)
    WHERE source_epoch IS NOT NULL;

CREATE OR REPLACE FUNCTION execution.set_numeric_pnf_external_need_minimum_source_epoch(
    selected_need_id BIGINT,
    selected_minimum_source_epoch BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE changed BOOLEAN := FALSE;
BEGIN
    IF selected_minimum_source_epoch IS NOT NULL AND selected_minimum_source_epoch <= 0 THEN
        RAISE EXCEPTION 'minimum source epoch must be positive';
    END IF;

    UPDATE execution.semantic_pnf_consumer_external_need
       SET minimum_source_epoch=selected_minimum_source_epoch
     WHERE need_id=selected_need_id;
    changed := FOUND;
    IF NOT changed THEN RETURN FALSE; END IF;

    -- A need may already have request-member rows. Propagate a stricter floor
    -- immediately; do not rely only on a future member insertion trigger.
    IF selected_minimum_source_epoch IS NOT NULL THEN
        UPDATE execution.semantic_pnf_external_request AS request
           SET minimum_source_epoch=selected_minimum_source_epoch,
               request_state=CASE WHEN request.request_state IN (2,5) THEN 1 ELSE request.request_state END,
               updated_at=CURRENT_TIMESTAMP
          FROM execution.semantic_pnf_external_request_member AS member,
               execution.semantic_pnf_consumer_external_need AS need
         WHERE need.need_id=selected_need_id
           AND member.demand_id=need.demand_id
           AND member.consumer_ref=need.consumer_ref
           AND member.query_ref=need.query_ref
           AND member.policy_ref=need.policy_ref
           AND member.need_kind=need.need_kind
           AND member.request_id=request.request_id
           AND request.provider_id=need.provider_id
           AND (
                need.need_kind<>2
                OR (
                    need.axis_kind=request.axis_kind
                    AND need.provider_property_numeric_id=request.provider_property_numeric_id
                )
           )
           AND (
                request.minimum_source_epoch IS NULL
                OR selected_minimum_source_epoch>request.minimum_source_epoch
           );
    END IF;
    RETURN TRUE;
END;
$$;

-- The request member is the correct fan-in point: one physical request can
-- serve many semantic fibres, but it must satisfy the strongest freshness floor
-- among them. Property needs are matched at the exact requested P/axis pair so
-- unrelated needs do not accidentally strengthen one another.
CREATE OR REPLACE FUNCTION execution.strengthen_numeric_pnf_external_request_freshness()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE floor_value BIGINT;
BEGIN
    SELECT max(need.minimum_source_epoch) INTO floor_value
      FROM execution.semantic_pnf_consumer_external_need AS need
      JOIN execution.semantic_pnf_external_request AS request
        ON request.request_id=NEW.request_id
     WHERE need.active
       AND need.demand_id=NEW.demand_id
       AND need.consumer_ref=NEW.consumer_ref
       AND need.query_ref=NEW.query_ref
       AND need.policy_ref=NEW.policy_ref
       AND need.need_kind=NEW.need_kind
       AND need.provider_id=request.provider_id
       AND (
            need.need_kind<>2
            OR (
                need.axis_kind=request.axis_kind
                AND need.provider_property_numeric_id=request.provider_property_numeric_id
            )
       );

    IF floor_value IS NOT NULL THEN
        UPDATE execution.semantic_pnf_external_request
           SET minimum_source_epoch=floor_value,
               request_state=CASE WHEN request_state IN (2,5) THEN 1 ELSE request_state END,
               updated_at=CURRENT_TIMESTAMP
         WHERE request_id=NEW.request_id
           AND (minimum_source_epoch IS NULL OR floor_value>minimum_source_epoch);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_external_member_freshness_trg
    ON execution.semantic_pnf_external_request_member;
CREATE TRIGGER semantic_pnf_external_member_freshness_trg
AFTER INSERT ON execution.semantic_pnf_external_request_member
FOR EACH ROW EXECUTE FUNCTION execution.strengthen_numeric_pnf_external_request_freshness();

-- Re-probe using source age. NULL minimum_source_epoch means the consumer does
-- not observe freshness. A non-NULL floor requires explicit source provenance;
-- legacy/unknown-age cache rows therefore cannot satisfy a freshness-sensitive
-- request merely because a value exists.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_external_request_cache_state()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0; n BIGINT := 0;
BEGIN
    UPDATE execution.semantic_pnf_external_request AS request
       SET request_state=2,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE (
            request.request_state IN (1,3,6)
            OR (request.request_state=4 AND request.lease_expires_at<CURRENT_TIMESTAMP)
       )
       AND (
           (request.request_kind=1 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
                WHERE candidate.label_symbol_id=request.label_symbol_id
                  AND (request.minimum_source_epoch IS NULL OR candidate.source_epoch>=request.minimum_source_epoch)
           ))
           OR
           (request.request_kind=2 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_external_evidence AS evidence
                WHERE evidence.provider_id=request.provider_id
                  AND evidence.subject_world_entity_id=request.world_entity_id
                  AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
                  AND (request.minimum_source_epoch IS NULL OR evidence.source_epoch>=request.minimum_source_epoch)
           ))
           OR
           (request.request_kind=3 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_world_entity_numeric AS world
                WHERE world.world_entity_id=request.world_entity_id
                  AND world.canonical_entity_id IS NOT NULL
           ))
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    UPDATE execution.semantic_pnf_external_request AS request
       SET request_state=3,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE (
            request.request_state IN (1,2,6)
            OR (request.request_state=4 AND request.lease_expires_at<CURRENT_TIMESTAMP)
       )
       AND NOT (
           (request.request_kind=1 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
                WHERE candidate.label_symbol_id=request.label_symbol_id
                  AND (request.minimum_source_epoch IS NULL OR candidate.source_epoch>=request.minimum_source_epoch)
           ))
           OR
           (request.request_kind=2 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_external_evidence AS evidence
                WHERE evidence.provider_id=request.provider_id
                  AND evidence.subject_world_entity_id=request.world_entity_id
                  AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
                  AND (request.minimum_source_epoch IS NULL OR evidence.source_epoch>=request.minimum_source_epoch)
           ))
           OR
           (request.request_kind=3 AND EXISTS (
               SELECT 1 FROM execution.semantic_pnf_world_entity_numeric AS world
                WHERE world.world_entity_id=request.world_entity_id
                  AND world.canonical_entity_id IS NOT NULL
           ))
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;
    RETURN affected;
END;
$$;

-- Snapshot/live provenance is written once per immutable evidence row. The
-- evidence digest distinguishes acquisition source/revision at the Python
-- boundary; this helper refuses to rewrite an established epoch.
CREATE OR REPLACE FUNCTION execution.set_numeric_pnf_external_evidence_source_epoch(
    selected_external_evidence_id BIGINT,
    selected_source_epoch BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    IF selected_source_epoch IS NULL THEN RETURN FALSE; END IF;
    IF selected_source_epoch<=0 THEN RAISE EXCEPTION 'source epoch must be positive'; END IF;
    UPDATE execution.semantic_pnf_external_evidence
       SET source_epoch=selected_source_epoch
     WHERE external_evidence_id=selected_external_evidence_id
       AND source_epoch IS NULL;
    IF FOUND THEN RETURN TRUE; END IF;
    RETURN EXISTS (
        SELECT 1 FROM execution.semantic_pnf_external_evidence
         WHERE external_evidence_id=selected_external_evidence_id
           AND source_epoch=selected_source_epoch
    );
END;
$$;

CREATE OR REPLACE VIEW execution.semantic_pnf_external_freshness_v1 AS
SELECT request.request_id,request.provider_id,request.request_kind,
       request.minimum_source_epoch,request.request_state,
       max(evidence.source_epoch) FILTER (WHERE evidence.source_epoch IS NOT NULL)
           AS newest_property_source_epoch,
       max(candidate.source_epoch) FILTER (WHERE candidate.source_epoch IS NOT NULL)
           AS newest_candidate_source_epoch
  FROM execution.semantic_pnf_external_request AS request
  LEFT JOIN execution.semantic_pnf_external_evidence AS evidence
    ON request.request_kind=2
   AND evidence.provider_id=request.provider_id
   AND evidence.subject_world_entity_id=request.world_entity_id
   AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
  LEFT JOIN execution.semantic_pnf_label_world_candidate AS candidate
    ON request.request_kind=1
   AND candidate.label_symbol_id=request.label_symbol_id
 GROUP BY request.request_id,request.provider_id,request.request_kind,
          request.minimum_source_epoch,request.request_state;

COMMIT;
