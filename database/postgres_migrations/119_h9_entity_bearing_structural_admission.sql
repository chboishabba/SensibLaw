BEGIN;

-- 119: H9 external work begins at a structurally represented entity occurrence,
-- never at a bare lexical symbol. The previous compiler admitted any contract-
-- matched H9 demand carrying lexical_symbol_id; that allowed grammatical words
-- such as "be" and "have" to become Wikidata discovery labels.
--
-- This migration deliberately contains no stopword/case/fuzzy heuristics.
-- Entity-bearing is occurrence structural. Missing structural evidence remains
-- an unresolved H9 residual and never becomes negative evidence.

ALTER TABLE execution.semantic_pnf_consumer_external_need
    ADD COLUMN IF NOT EXISTS anchor_object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS label_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS semantic_pnf_external_need_anchor_idx
    ON execution.semantic_pnf_consumer_external_need
       (anchor_object_id,label_symbol_id,active,need_id);

-- 1 parser entity, 2 admitted local identity, 3 attached world candidate.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1 AS
SELECT DISTINCT demand.demand_id,demand.source_object_id,1::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_mention_support AS object_support
    ON object_support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention AS mention
    ON mention.mention_id=object_support.mention_id
   AND mention.mention_kind=1 AND mention.active
 WHERE demand.source_object_id IS NOT NULL
UNION
SELECT DISTINCT demand.demand_id,demand.source_object_id,2::SMALLINT
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_identity_projection AS identity_projection
    ON identity_projection.source_object_id=demand.source_object_id
 WHERE demand.source_object_id IS NOT NULL
UNION
SELECT DISTINCT demand.demand_id,demand.source_object_id,3::SMALLINT
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_token_support AS support
    ON support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=support.token_id AND attachment.attachment_state=1
 WHERE demand.source_object_id IS NOT NULL;

-- Provider lookup needs an exact occurrence label. Existing world attachment is
-- strongest because it already names the label/world fibre. Otherwise expose
-- parser-entity/admitted-identity labels only when the source object is backed by
-- one token. Multi-token entities stay entity-bearing but have no provider label
-- until a phrase-symbol carrier is available.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1 AS
WITH attached AS (
    SELECT DISTINCT demand.demand_id,demand.source_object_id,
           attachment.label_symbol_id,3::SMALLINT AS anchor_kind,
           300::SMALLINT AS anchor_strength
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object_token_support AS support
        ON support.object_id=demand.source_object_id
      JOIN execution.semantic_pnf_mention_world_attachment AS attachment
        ON attachment.token_id=support.token_id AND attachment.attachment_state=1
     WHERE demand.source_object_id IS NOT NULL
), one_token AS (
    SELECT demand.demand_id,demand.source_object_id,min(support.token_id) AS token_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object_token_support AS support
        ON support.object_id=demand.source_object_id
     WHERE demand.source_object_id IS NOT NULL
     GROUP BY demand.demand_id,demand.source_object_id
    HAVING count(DISTINCT support.token_id)=1
), admitted_identity AS (
    SELECT DISTINCT one_token.demand_id,one_token.source_object_id,
           token.orth_symbol_id AS label_symbol_id,2::SMALLINT AS anchor_kind,
           200::SMALLINT AS anchor_strength
      FROM one_token
      JOIN execution.semantic_pnf_identity_projection AS identity_projection
        ON identity_projection.source_object_id=one_token.source_object_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=one_token.token_id AND token.representation_version=2
     WHERE token.orth_symbol_id IS NOT NULL
), parser_entity AS (
    SELECT DISTINCT one_token.demand_id,one_token.source_object_id,
           token.orth_symbol_id AS label_symbol_id,1::SMALLINT AS anchor_kind,
           100::SMALLINT AS anchor_strength
      FROM one_token
      JOIN execution.semantic_pnf_object_mention_support AS object_support
        ON object_support.object_id=one_token.source_object_id
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.mention_id=object_support.mention_id
       AND mention.mention_kind=1 AND mention.active
      JOIN execution.semantic_pnf_mention_token AS mention_token
        ON mention_token.mention_id=mention.mention_id
       AND mention_token.token_id=one_token.token_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=one_token.token_id AND token.representation_version=2
     WHERE token.orth_symbol_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_mention_token AS extra
            WHERE extra.mention_id=mention.mention_id
              AND extra.token_id<>one_token.token_id
       )
)
SELECT * FROM attached
UNION SELECT * FROM admitted_identity
UNION SELECT * FROM parser_entity;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS
SELECT DISTINCT ON (anchor.demand_id)
       anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       anchor.anchor_kind,anchor.anchor_strength
  FROM execution.semantic_pnf_h9_entity_label_anchor_v1 AS anchor
 ORDER BY anchor.demand_id,anchor.anchor_strength DESC,
          anchor.label_symbol_id,anchor.source_object_id;

-- Explain every H9/contract intersection before creating semantic needs.
-- reason: 1 discovery, 2 property, 3 identity admitted; 10 no contract;
-- 11 no source object; 12 no entity witness; 13 no exact label anchor;
-- 14 no represented world candidate; 15 consumer sufficient; 16 proof resolved.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_v1 AS
WITH h9 AS MATERIALIZED (
    SELECT work.demand_id,work.consumer_ref,work.query_ref,work.policy_ref,
           demand.source_object_id,demand.expected_target_kind,
           demand.expected_factor_type_symbol_id,demand.expected_object_kind_symbol_id,
           demand.lexical_symbol_id,demand.role_symbol_id,demand.residual_type_symbol_id
      FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
      JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=work.demand_id
     WHERE work.horizon=9 AND work.work_state=1
), matched AS MATERIALIZED (
    SELECT h9.*,contract.contract_id,contract.need_kind,contract.provider_id,
           contract.axis_kind,contract.provider_property_numeric_id,
           contract.need_revision,contract.priority,contract.minimum_source_epoch,
           anchor.source_object_id AS anchor_object_id,anchor.label_symbol_id,
           anchor.anchor_kind,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 AS b
                    WHERE b.demand_id=h9.demand_id) AS entity_bearing,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS c
                    WHERE c.label_symbol_id=anchor.label_symbol_id) AS has_world_candidate,
           execution.numeric_pnf_consumer_stop_at_horizon(
               h9.demand_id,h9.consumer_ref,h9.query_ref,h9.policy_ref,6::SMALLINT
           ) AS consumer_sufficient,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS p
                    WHERE p.demand_id=h9.demand_id AND p.outcome_state=2
                      AND p.candidate_count=1) AS deductively_resolved
      FROM h9
      LEFT JOIN execution.semantic_pnf_consumer_world_axis_contract_current_v1 AS contract
        ON contract.consumer_ref=h9.consumer_ref
       AND contract.query_ref=h9.query_ref
       AND contract.policy_ref=h9.policy_ref AND contract.active
       AND (contract.expected_target_kind IS NULL OR contract.expected_target_kind=h9.expected_target_kind)
       AND (contract.expected_factor_type_symbol_id IS NULL OR contract.expected_factor_type_symbol_id=h9.expected_factor_type_symbol_id)
       AND (contract.expected_object_kind_symbol_id IS NULL OR contract.expected_object_kind_symbol_id=h9.expected_object_kind_symbol_id)
       AND (contract.lexical_symbol_id IS NULL OR contract.lexical_symbol_id=h9.lexical_symbol_id)
       AND (contract.role_symbol_id IS NULL OR contract.role_symbol_id=h9.role_symbol_id)
       AND (contract.residual_type_symbol_id IS NULL OR contract.residual_type_symbol_id=h9.residual_type_symbol_id)
      LEFT JOIN execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS anchor
        ON anchor.demand_id=h9.demand_id
)
SELECT matched.*,
       CASE
         WHEN contract_id IS NULL OR consumer_sufficient OR deductively_resolved THEN FALSE
         WHEN source_object_id IS NULL OR NOT entity_bearing OR label_symbol_id IS NULL THEN FALSE
         WHEN need_kind IN (2,3) AND NOT has_world_candidate THEN FALSE
         ELSE TRUE
       END AS admitted,
       CASE
         WHEN contract_id IS NULL THEN 10
         WHEN consumer_sufficient THEN 15
         WHEN deductively_resolved THEN 16
         WHEN source_object_id IS NULL THEN 11
         WHEN NOT entity_bearing THEN 12
         WHEN label_symbol_id IS NULL THEN 13
         WHEN need_kind IN (2,3) AND NOT has_world_candidate THEN 14
         WHEN need_kind=1 THEN 1 WHEN need_kind=2 THEN 2 WHEN need_kind=3 THEN 3
       END::SMALLINT AS admission_reason
  FROM matched;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1 AS
SELECT consumer_ref,query_ref,policy_ref,admission_reason,admitted,
       count(*)::BIGINT AS admission_rows,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_h9_external_admission_v1
 GROUP BY consumer_ref,query_ref,policy_ref,admission_reason,admitted;

-- Reconcile historical needs without deleting receipts. Existing valid anchors
-- are backfilled; origins which cannot satisfy the structural invariant become
-- inactive. This preserves the receipt while preventing provider execution.
UPDATE execution.semantic_pnf_consumer_external_need AS need
   SET anchor_object_id=anchor.source_object_id,label_symbol_id=anchor.label_symbol_id
  FROM execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS anchor
 WHERE need.demand_id=anchor.demand_id
   AND need.need_kind IN (1,2,3);

UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND (
       need.anchor_object_id IS NULL OR need.label_symbol_id IS NULL
       OR (need.need_kind IN (2,3) AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS c
            WHERE c.label_symbol_id=need.label_symbol_id
       ))
   );

-- Recompute need state from retained origin receipts after reconciliation.
WITH state AS MATERIALIZED (
    SELECT need.need_id,COALESCE(bool_or(origin.active),FALSE) AS any_active,
           min(origin.priority) FILTER (WHERE origin.active) AS min_priority,
           max(origin.minimum_source_epoch) FILTER (WHERE origin.active) AS max_floor
      FROM execution.semantic_pnf_consumer_external_need AS need
      LEFT JOIN execution.semantic_pnf_consumer_external_need_origin AS origin
        ON origin.need_id=need.need_id
     GROUP BY need.need_id
)
UPDATE execution.semantic_pnf_consumer_external_need AS need
   SET active=state.any_active,
       priority=COALESCE(state.min_priority,need.priority),
       minimum_source_epoch=state.max_floor
  FROM state WHERE state.need_id=need.need_id;

-- Explicit/manual registration now obeys the same structural gate. It remains an
-- escape hatch for exact-demand intent, not an escape hatch from entity-bearing
-- admission. Property/identity needs require an already represented candidate.
CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_external_need(
    selected_demand_id BIGINT,selected_consumer_ref TEXT,selected_query_ref TEXT,
    selected_policy_ref TEXT,selected_need_kind SMALLINT,selected_provider_id SMALLINT,
    selected_axis_kind SMALLINT,selected_provider_property_numeric_id BIGINT,
    selected_priority SMALLINT,selected_need_revision BIGINT,selected_active BOOLEAN
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_need_id BIGINT; selected_anchor RECORD;
BEGIN
    IF selected_need_kind NOT IN (1,2,3) THEN RAISE EXCEPTION 'external need kind must be discovery, property, or identity'; END IF;
    IF selected_priority<=0 THEN RAISE EXCEPTION 'external need priority must be positive'; END IF;
    IF selected_need_kind=2 AND (selected_axis_kind IS NULL OR selected_provider_property_numeric_id IS NULL OR selected_provider_property_numeric_id<=0) THEN
        RAISE EXCEPTION 'property need requires positive property id and axis';
    END IF;
    IF selected_need_kind<>2 AND (selected_axis_kind IS NOT NULL OR selected_provider_property_numeric_id IS NOT NULL) THEN
        RAISE EXCEPTION 'discovery/identity need cannot carry property-axis coordinates';
    END IF;

    SELECT * INTO selected_anchor FROM execution.semantic_pnf_h9_preferred_entity_anchor_v1
     WHERE demand_id=selected_demand_id;
    IF selected_active AND selected_anchor.demand_id IS NULL THEN
        RAISE EXCEPTION 'external need requires entity-bearing structural label anchor';
    END IF;
    IF selected_active AND selected_need_kind IN (2,3) AND NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS c
         WHERE c.label_symbol_id=selected_anchor.label_symbol_id
    ) THEN
        RAISE EXCEPTION 'property/identity need requires represented world candidate';
    END IF;

    INSERT INTO execution.semantic_pnf_consumer_external_need
        (demand_id,consumer_ref,query_ref,policy_ref,need_kind,provider_id,
         axis_kind,provider_property_numeric_id,priority,need_revision,active,
         anchor_object_id,label_symbol_id)
    VALUES (selected_demand_id,selected_consumer_ref,selected_query_ref,selected_policy_ref,
            selected_need_kind,selected_provider_id,selected_axis_kind,
            selected_provider_property_numeric_id,selected_priority,selected_need_revision,
            selected_active,selected_anchor.source_object_id,selected_anchor.label_symbol_id)
    ON CONFLICT DO NOTHING;

    SELECT need_id INTO STRICT resolved_need_id
      FROM execution.semantic_pnf_consumer_external_need AS need
     WHERE need.demand_id=selected_demand_id AND need.consumer_ref=selected_consumer_ref
       AND need.query_ref=selected_query_ref AND need.policy_ref=selected_policy_ref
       AND need.need_kind=selected_need_kind AND need.provider_id=selected_provider_id
       AND COALESCE(need.axis_kind,0)=COALESCE(selected_axis_kind,0)
       AND COALESCE(need.provider_property_numeric_id,0)=COALESCE(selected_provider_property_numeric_id,0)
       AND need.need_revision=selected_need_revision;

    UPDATE execution.semantic_pnf_consumer_external_need
       SET anchor_object_id=selected_anchor.source_object_id,
           label_symbol_id=selected_anchor.label_symbol_id
     WHERE need_id=resolved_need_id;

    INSERT INTO execution.semantic_pnf_consumer_external_need_origin
        (need_id,origin_kind,contract_id,active,priority,minimum_source_epoch)
    VALUES (resolved_need_id,1,NULL,selected_active,selected_priority,NULL)
    ON CONFLICT(need_id) WHERE origin_kind=1 DO UPDATE SET
        active=EXCLUDED.active,priority=EXCLUDED.priority,updated_at=CURRENT_TIMESTAMP;
    PERFORM execution.recompute_numeric_pnf_external_need_from_origins(resolved_need_id);
    RETURN resolved_need_id;
END;
$$;

CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_h9_external_needs_for_consumer(
    selected_run_id BIGINT,selected_document_id BIGINT,selected_consumer_ref TEXT,
    selected_query_ref TEXT,selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
       SET active=FALSE,updated_at=CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_consumer_external_need AS need,
           execution.semantic_pnf_demand AS demand,execution.semantic_pnf_region AS region
     WHERE origin.need_id=need.need_id AND origin.origin_kind=2
       AND demand.demand_id=need.demand_id AND region.region_id=demand.source_region_id
       AND need.consumer_ref=selected_consumer_ref AND need.query_ref=selected_query_ref
       AND need.policy_ref=selected_policy_ref AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    WITH admitted AS MATERIALIZED (
        SELECT DISTINCT admission.contract_id,admission.demand_id,admission.need_kind,
               admission.provider_id,admission.axis_kind,admission.provider_property_numeric_id,
               admission.need_revision,admission.priority,admission.minimum_source_epoch,
               admission.anchor_object_id,admission.label_symbol_id
          FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=admission.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE admission.admitted AND admission.consumer_ref=selected_consumer_ref
           AND admission.query_ref=selected_query_ref AND admission.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id AND region.document_id=selected_document_id
    )
    INSERT INTO execution.semantic_pnf_consumer_external_need
        (demand_id,consumer_ref,query_ref,policy_ref,need_kind,provider_id,axis_kind,
         provider_property_numeric_id,priority,need_revision,active,minimum_source_epoch,
         anchor_object_id,label_symbol_id)
    SELECT demand_id,selected_consumer_ref,selected_query_ref,selected_policy_ref,need_kind,
           provider_id,axis_kind,provider_property_numeric_id,priority,need_revision,TRUE,
           minimum_source_epoch,anchor_object_id,label_symbol_id FROM admitted
    ON CONFLICT DO NOTHING;

    WITH admitted AS MATERIALIZED (
        SELECT DISTINCT admission.contract_id,admission.demand_id,admission.need_kind,
               admission.provider_id,admission.axis_kind,admission.provider_property_numeric_id,
               admission.need_revision,admission.priority,admission.minimum_source_epoch,
               admission.anchor_object_id,admission.label_symbol_id
          FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=admission.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE admission.admitted AND admission.consumer_ref=selected_consumer_ref
           AND admission.query_ref=selected_query_ref AND admission.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id AND region.document_id=selected_document_id
    ), selected_need AS MATERIALIZED (
        SELECT need.need_id,admitted.contract_id,admitted.priority,admitted.minimum_source_epoch,
               admitted.anchor_object_id,admitted.label_symbol_id
          FROM admitted JOIN execution.semantic_pnf_consumer_external_need AS need
            ON need.demand_id=admitted.demand_id AND need.consumer_ref=selected_consumer_ref
           AND need.query_ref=selected_query_ref AND need.policy_ref=selected_policy_ref
           AND need.need_kind=admitted.need_kind AND need.provider_id=admitted.provider_id
           AND COALESCE(need.axis_kind,0)=COALESCE(admitted.axis_kind,0)
           AND COALESCE(need.provider_property_numeric_id,0)=COALESCE(admitted.provider_property_numeric_id,0)
           AND need.need_revision=admitted.need_revision
    )
    INSERT INTO execution.semantic_pnf_consumer_external_need_origin
        (need_id,origin_kind,contract_id,active,priority,minimum_source_epoch)
    SELECT need_id,2,contract_id,TRUE,priority,minimum_source_epoch FROM selected_need
    ON CONFLICT(need_id,contract_id) WHERE origin_kind=2 DO UPDATE SET
        active=TRUE,priority=EXCLUDED.priority,minimum_source_epoch=EXCLUDED.minimum_source_epoch,
        updated_at=CURRENT_TIMESTAMP;

    WITH scoped AS MATERIALIZED (
        SELECT need.need_id,COALESCE(bool_or(origin.active),FALSE) AS any_active,
               min(origin.priority) FILTER (WHERE origin.active) AS min_priority,
               max(origin.minimum_source_epoch) FILTER (WHERE origin.active) AS max_floor
          FROM execution.semantic_pnf_consumer_external_need AS need
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
          LEFT JOIN execution.semantic_pnf_consumer_external_need_origin AS origin ON origin.need_id=need.need_id
         WHERE need.consumer_ref=selected_consumer_ref AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id GROUP BY need.need_id
    ), anchor AS MATERIALIZED (
        SELECT need.need_id,preferred.source_object_id,preferred.label_symbol_id
          FROM execution.semantic_pnf_consumer_external_need AS need
          LEFT JOIN execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS preferred
            ON preferred.demand_id=need.demand_id
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE need.consumer_ref=selected_consumer_ref AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
    )
    UPDATE execution.semantic_pnf_consumer_external_need AS need
       SET active=scoped.any_active,priority=COALESCE(scoped.min_priority,need.priority),
           minimum_source_epoch=scoped.max_floor,
           anchor_object_id=CASE WHEN scoped.any_active THEN anchor.source_object_id ELSE NULL END,
           label_symbol_id=CASE WHEN scoped.any_active THEN anchor.label_symbol_id ELSE NULL END
      FROM scoped,anchor WHERE need.need_id=scoped.need_id AND anchor.need_id=need.need_id;

    PERFORM execution.refresh_numeric_pnf_external_request_observer_state();
    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();

    SELECT count(DISTINCT need.need_id)::BIGINT INTO affected
      FROM execution.semantic_pnf_consumer_external_need AS need
      JOIN execution.semantic_pnf_consumer_external_need_origin AS origin
        ON origin.need_id=need.need_id AND origin.origin_kind=2 AND origin.active
      JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
      JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
     WHERE need.active AND need.anchor_object_id IS NOT NULL AND need.label_symbol_id IS NOT NULL
       AND need.consumer_ref=selected_consumer_ref AND need.query_ref=selected_query_ref
       AND need.policy_ref=selected_policy_ref AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;
    RETURN affected;
END;
$$;

-- Provider planner consumes only the admitted occurrence label. Property work
-- never falls back to discovery: represented candidates are a precondition.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer(
    selected_run_id BIGINT,selected_document_id BIGINT,selected_consumer_ref TEXT,
    selected_query_ref TEXT,selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE need_row RECORD; candidate_row RECORD; attachment_row RECORD;
        request_id_value BIGINT; affected BIGINT := 0;
BEGIN
    FOR need_row IN
        SELECT need.* FROM execution.semantic_pnf_consumer_external_need AS need
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=need.demand_id AND work.consumer_ref=need.consumer_ref
           AND work.query_ref=need.query_ref AND work.policy_ref=need.policy_ref
           AND work.horizon=9 AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE need.active AND need.anchor_object_id IS NOT NULL AND need.label_symbol_id IS NOT NULL
           AND need.consumer_ref=selected_consumer_ref AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               need.demand_id,need.consumer_ref,need.query_ref,need.policy_ref,6::SMALLINT)
         ORDER BY need.priority,need.demand_id,need.need_id
    LOOP
        IF need_row.need_kind=1 THEN
            IF EXISTS (SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS c
                        WHERE c.label_symbol_id=need_row.label_symbol_id) THEN CONTINUE; END IF;
            request_id_value:=execution.ensure_numeric_pnf_external_request(
                need_row.provider_id,1::SMALLINT,need_row.label_symbol_id,NULL,NULL,NULL,
                need_row.need_revision,need_row.priority);
            INSERT INTO execution.semantic_pnf_external_request_member
                (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
            VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
                    need_row.policy_ref,need_row.need_kind) ON CONFLICT DO NOTHING;
            affected:=affected+1;
        ELSIF need_row.need_kind=2 THEN
            FOR candidate_row IN SELECT c.world_entity_id
              FROM execution.semantic_pnf_label_world_candidate AS c
             WHERE c.label_symbol_id=need_row.label_symbol_id
             ORDER BY c.candidate_ordinal,c.world_entity_id
            LOOP
                request_id_value:=execution.ensure_numeric_pnf_external_request(
                    need_row.provider_id,2::SMALLINT,need_row.label_symbol_id,candidate_row.world_entity_id,
                    need_row.provider_property_numeric_id,need_row.axis_kind,
                    need_row.need_revision,need_row.priority);
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
                        need_row.policy_ref,need_row.need_kind) ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        ELSE
            FOR attachment_row IN
                SELECT DISTINCT a.world_entity_id,a.label_symbol_id
                  FROM execution.semantic_pnf_object_token_support AS s
                  JOIN execution.semantic_pnf_mention_world_attachment AS a
                    ON a.token_id=s.token_id AND a.attachment_state=1
                 WHERE s.object_id=need_row.anchor_object_id
                   AND a.label_symbol_id=need_row.label_symbol_id
            LOOP
                request_id_value:=execution.ensure_numeric_pnf_external_request(
                    need_row.provider_id,3::SMALLINT,attachment_row.label_symbol_id,
                    attachment_row.world_entity_id,NULL,NULL,need_row.need_revision,need_row.priority);
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
                        need_row.policy_ref,need_row.need_kind) ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        END IF;
    END LOOP;
    PERFORM execution.refresh_numeric_pnf_external_request_observer_state();
    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();
    RETURN affected;
END;
$$;

COMMIT;
