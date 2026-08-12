BEGIN;

-- 109: external context requirements are a rebuildable hot projection of cold
-- provider evidence.  Historical observations remain immutable in
-- semantic_pnf_external_evidence, but the candidate requirement surface keeps
-- only the newest admissible observation epoch for each (candidate, axis,
-- provider property).  Removing stale hot pressure is not negative evidence.

ALTER TABLE execution.semantic_pnf_world_candidate_requirement
    ADD COLUMN IF NOT EXISTS external_evidence_id BIGINT
        REFERENCES execution.semantic_pnf_external_evidence(external_evidence_id)
        ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS provider_property_numeric_id BIGINT,
    ADD COLUMN IF NOT EXISTS source_epoch BIGINT
        CHECK (source_epoch IS NULL OR source_epoch>0);

-- Backfill older external projections without regex.  The established evidence
-- refs are `external-evidence:<id>` or
-- `external-evidence:<id>:request:<id>`.
UPDATE execution.semantic_pnf_world_candidate_requirement AS requirement
   SET external_evidence_id=parsed.external_evidence_id,
       provider_property_numeric_id=evidence.provider_property_numeric_id,
       source_epoch=evidence.source_epoch
  FROM LATERAL (
       SELECT CASE
           WHEN split_part(requirement.evidence_ref,':',1)='external-evidence'
            AND split_part(requirement.evidence_ref,':',2)<>''
           THEN split_part(requirement.evidence_ref,':',2)::BIGINT
           ELSE NULL
       END AS external_evidence_id
  ) AS parsed
  JOIN execution.semantic_pnf_external_evidence AS evidence
    ON evidence.external_evidence_id=parsed.external_evidence_id
 WHERE requirement.external_evidence_id IS NULL
   AND split_part(requirement.evidence_ref,':',1)='external-evidence';

CREATE INDEX IF NOT EXISTS semantic_pnf_world_candidate_requirement_external_idx
    ON execution.semantic_pnf_world_candidate_requirement
       (world_entity_id,axis_kind,provider_property_numeric_id,source_epoch DESC,
        required_symbol_id)
    WHERE external_evidence_id IS NOT NULL;

CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_for_request(
    selected_request_id BIGINT,
    selected_required_polarity SMALLINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    request RECORD;
    selected_epoch BIGINT;
    affected BIGINT := 0;
    n BIGINT := 0;
BEGIN
    IF selected_required_polarity NOT IN (-1,1) THEN
        RAISE EXCEPTION 'required polarity must be -1 or +1';
    END IF;

    SELECT request.* INTO STRICT request
      FROM execution.semantic_pnf_external_request AS request
     WHERE request.request_id=selected_request_id;
    IF request.request_kind<>2 OR request.axis_kind IS NULL THEN
        RETURN 0;
    END IF;

    -- Prefer the newest known acquisition epoch that satisfies the current
    -- floor.  Multiple values at that exact epoch are retained.  Unknown-age
    -- evidence is used only when no positive floor exists and no known-age
    -- observation is available.
    SELECT max(evidence.source_epoch)
      INTO selected_epoch
      FROM execution.semantic_pnf_external_evidence AS evidence
     WHERE evidence.provider_id=request.provider_id
       AND evidence.subject_world_entity_id=request.world_entity_id
       AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
       AND evidence.value_kind=2
       AND evidence.value_symbol_id IS NOT NULL
       AND (
           request.minimum_source_epoch IS NULL
           OR evidence.source_epoch>=request.minimum_source_epoch
       );

    -- Retract only the rebuildable external projection for this exact
    -- candidate/axis/property.  Manual/static candidate requirements and cold
    -- evidence are untouched.
    DELETE FROM execution.semantic_pnf_world_candidate_requirement AS requirement
     WHERE requirement.world_entity_id=request.world_entity_id
       AND requirement.axis_kind=request.axis_kind
       AND requirement.provider_property_numeric_id=request.provider_property_numeric_id
       AND requirement.external_evidence_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_external_evidence AS evidence
            WHERE evidence.external_evidence_id=requirement.external_evidence_id
              AND evidence.provider_id=request.provider_id
              AND evidence.subject_world_entity_id=request.world_entity_id
              AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
              AND evidence.value_kind=2
              AND evidence.value_symbol_id IS NOT NULL
              AND (
                  (selected_epoch IS NOT NULL AND evidence.source_epoch=selected_epoch)
                  OR
                  (selected_epoch IS NULL
                   AND request.minimum_source_epoch IS NULL
                   AND evidence.source_epoch IS NULL)
              )
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    INSERT INTO execution.semantic_pnf_world_candidate_requirement
        (world_entity_id,axis_kind,required_symbol_id,required_polarity,
         requirement_revision,evidence_ref,external_evidence_id,
         provider_property_numeric_id,source_epoch)
    SELECT request.world_entity_id,
           request.axis_kind,
           evidence.value_symbol_id,
           selected_required_polarity,
           COALESCE(evidence.provider_revision,1),
           'external-evidence:' || evidence.external_evidence_id::TEXT
               || ':request:' || selected_request_id::TEXT,
           evidence.external_evidence_id,
           evidence.provider_property_numeric_id,
           evidence.source_epoch
      FROM execution.semantic_pnf_external_evidence AS evidence
     WHERE evidence.provider_id=request.provider_id
       AND evidence.subject_world_entity_id=request.world_entity_id
       AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
       AND evidence.value_kind=2
       AND evidence.value_symbol_id IS NOT NULL
       AND (
           (selected_epoch IS NOT NULL AND evidence.source_epoch=selected_epoch)
           OR
           (selected_epoch IS NULL
            AND request.minimum_source_epoch IS NULL
            AND evidence.source_epoch IS NULL)
       )
    ON CONFLICT(world_entity_id,axis_kind,required_symbol_id,required_polarity)
    DO UPDATE SET
        requirement_revision=GREATEST(
            execution.semantic_pnf_world_candidate_requirement.requirement_revision,
            EXCLUDED.requirement_revision
        ),
        evidence_ref=EXCLUDED.evidence_ref,
        external_evidence_id=EXCLUDED.external_evidence_id,
        provider_property_numeric_id=EXCLUDED.provider_property_numeric_id,
        source_epoch=EXCLUDED.source_epoch;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    RETURN affected;
END;
$$;

COMMIT;
