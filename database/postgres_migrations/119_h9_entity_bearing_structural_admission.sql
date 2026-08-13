BEGIN;

-- 119: external work begins at a structurally represented entity occurrence,
-- never at a bare lexical symbol. The previous contract compiler admitted any
-- H9 residual carrying lexical_symbol_id, which allowed grammatical/common-word
-- demands to reach Wikidata label discovery.
--
-- Invariants:
--   * entity-bearing != external work required;
--   * discovery requires an entity-bearing source object and occurrence label;
--   * property enrichment additionally requires an already represented world
--     candidate for that exact label;
--   * identity alignment requires an attached represented world candidate;
--   * no stopword, capitalization, regex, fuzzy, or lexical-semantic heuristic;
--   * absence of an anchor/candidate leaves the H9 semantic residual untouched.

ALTER TABLE execution.semantic_pnf_consumer_external_need
    ADD COLUMN IF NOT EXISTS anchor_object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS label_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS semantic_pnf_external_need_anchor_idx
    ON execution.semantic_pnf_consumer_external_need
       (anchor_object_id,label_symbol_id,active,need_id);

-- Entity-bearing is occurrence-structural. Parser NER may span several tokens;
-- such a mention is still entity-bearing even when this schema cannot yet emit
-- one exact phrase SymbolId for provider lookup.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1 AS
SELECT DISTINCT demand.demand_id,demand.source_object_id,
       1::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_mention_support AS object_support
    ON object_support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention AS mention
    ON mention.mention_id=object_support.mention_id
   AND mention.mention_kind=1
   AND mention.active
 WHERE demand.source_object_id IS NOT NULL
UNION
SELECT DISTINCT demand.demand_id,demand.source_object_id,
       2::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_identity_projection AS identity_projection
    ON identity_projection.source_object_id=demand.source_object_id
 WHERE demand.source_object_id IS NOT NULL
UNION
SELECT DISTINCT demand.demand_id,demand.source_object_id,
       3::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_token_support AS object_support
    ON object_support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=object_support.token_id
   AND attachment.attachment_state=1
 WHERE demand.source_object_id IS NOT NULL;

-- Provider labels must come from the represented occurrence, not from
-- demand.lexical_symbol_id. An already attached world candidate carries its
-- exact label. Otherwise a parser-entity or admitted-identity anchor is exposed
-- only when the source object has a single supported token; its orth SymbolId
-- preserves occurrence spelling/case. Multi-token entities remain residual.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1 AS
WITH attached AS (
    SELECT DISTINCT demand.demand_id,demand.source_object_id,
           attachment.label_symbol_id,
           3::SMALLINT AS anchor_kind,
           300::SMALLINT AS anchor_strength
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object_token_support AS object_support
        ON object_support.object_id=demand.source_object_id
      JOIN execution.semantic_pnf_mention_world_attachment AS attachment
        ON attachment.token_id=object_support.token_id
       AND attachment.attachment_state=1
     WHERE demand.source_object_id IS NOT NULL
), single_token_source AS (
    SELECT demand.demand_id,demand.source_object_id,
           min(object_support.token_id) AS token_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_object_token_support AS object_support
        ON object_support.object_id=demand.source_object_id
     WHERE demand.source_object_id IS NOT NULL
     GROUP BY demand.demand_id,demand.source_object_id
    HAVING count(DISTINCT object_support.token_id)=1
), admitted_identity AS (
    SELECT DISTINCT source.demand_id,source.source_object_id,
           token.orth_symbol_id AS label_symbol_id,
           2::SMALLINT AS anchor_kind,
           200::SMALLINT AS anchor_strength
      FROM single_token_source AS source
      JOIN execution.semantic_pnf_identity_projection AS identity_projection
        ON identity_projection.source_object_id=source.source_object_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=source.token_id
       AND token.representation_version=2
     WHERE token.orth_symbol_id IS NOT NULL
), parser_entity AS (
    SELECT DISTINCT source.demand_id,source.source_object_id,
           token.orth_symbol_id AS label_symbol_id,
           1::SMALLINT AS anchor_kind,
           100::SMALLINT AS anchor_strength
      FROM single_token_source AS source
      JOIN execution.semantic_pnf_object_mention_support AS object_support
        ON object_support.object_id=source.source_object_id
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.mention_id=object_support.mention_id
       AND mention.mention_kind=1
       AND mention.active
      JOIN execution.semantic_pnf_mention_token AS mention_token
        ON mention_token.mention_id=mention.mention_id
       AND mention_token.token_id=source.token_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=source.token_id
       AND token.representation_version=2
     WHERE token.orth_symbol_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_mention_token AS other_token
            WHERE other_token.mention_id=mention.mention_id
              AND other_token.token_id<>source.token_id
       )
)
SELECT * FROM attached
UNION
SELECT * FROM admitted_identity
UNION
SELECT * FROM parser_entity;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS
SELECT DISTINCT ON (anchor.demand_id)
       anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       anchor.anchor_kind,anchor.anchor_strength
  FROM execution.semantic_pnf_h9_entity_label_anchor_v1 AS anchor
 ORDER BY anchor.demand_id,anchor.anchor_strength DESC,
          anchor.label_symbol_id,anchor.source_object_id;

-- Contract-match observatory. It starts from H9 residual work, not from external
-- needs, so rejected demands remain visible and explain why no provider work was
-- created. admission_reason:
--   1 admitted_discovery
--   2 admitted_property
--   3 admitted_identity
--  10 no_contract
--  11 no_source_object
--  12 no_entity_anchor
--  13 no_label_anchor
--  14 no_world_candidate
--  15 consumer_already_sufficient
--  16 deductively_resolved
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
           anchor.anchor_object_id,anchor.label_symbol_id,anchor.anchor_kind,
           EXISTS (
               SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
                WHERE bearing.demand_id=h9.demand_id
           ) AS entity_bearing,
           EXISTS (
               SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
                WHERE candidate.label_symbol_id=anchor.label_symbol_id
           ) AS has_world_candidate,
           execution.numeric_pnf_consumer_stop_at_horizon(
               h9.demand_id,h9.consumer_ref,h9.query_ref,h9.policy_ref,6::SMALLINT
           ) AS consumer_sufficient,
           EXISTS (
               SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS proof
                WHERE proof.demand_id=h9.demand_id
                  AND proof.outcome_state=2 AND proof.candidate_count=1
           ) AS deductively_resolved
      FROM h9
      LEFT JOIN execution.semantic_pnf_consumer_world_axis_contract_current_v1 AS contract
        ON contract.consumer_ref=h9.consumer_ref
       AND contract.query_ref=h9.query_ref
       AND contract.policy_ref=h9.policy_ref
       AND contract.active
       AND (contract.expected_target_kind IS NULL
            OR contract.expected_target_kind=h9.expected_target_kind)
       AND (contract.expected_factor_type_symbol_id IS NULL
            OR contract.expected_factor_type_symbol_id=h9.expected_factor_type_symbol_id)
       AND (contract.expected_object_kind_symbol_id IS NULL
            OR contract.expected_object_kind_symbol_id=h9.expected_object_kind_symbol_id)
       AND (contract.lexical_symbol_id IS NULL
            OR contract.lexical_symbol_id=h9.lexical_symbol_id)
       AND (contract.role_symbol_id IS NULL
            OR contract.role_symbol_id=h9.role_symbol_id)
       AND (contract.residual_type_symbol_id IS NULL
            OR contract.residual_type_symbol_id=h9.residual_type_symbol_id)
      LEFT JOIN LATERAL (
          SELECT preferred.source_object_id AS anchor_object_id,
                 preferred.label_symbol_id,preferred.anchor_kind
            FROM execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS preferred
           WHERE preferred.demand_id=h9.demand_id
      ) AS anchor ON TRUE
)
SELECT matched.*,
       CASE
           WHEN matched.contract_id IS NULL THEN FALSE
           WHEN matched.consumer_sufficient OR matched.deductively_resolved THEN FALSE
           WHEN matched.source_object_id IS NULL THEN FALSE
           WHEN NOT matched.entity_bearing THEN FALSE
           WHEN matched.label_symbol_id IS NULL THEN FALSE
           WHEN matched.need_kind=2 AND NOT matched.has_world_candidate THEN FALSE
           WHEN matched.need_kind=3 AND NOT matched.has_world_candidate THEN FALSE
           ELSE TRUE
       END AS admitted,
       CASE
           WHEN matched.contract_id IS NULL THEN 10
           WHEN matched.consumer_sufficient THEN 15
           WHEN matched.deductively_resolved THEN 16
           WHEN matched.source_object_id IS NULL THEN 11
           WHEN NOT matched.entity_bearing THEN 12
           WHEN matched.label_symbol_id IS NULL THEN 13
           WHEN matched.need_kind IN (2,3) AND NOT matched.has_world_candidate THEN 14
           WHEN matched.need_kind=1 THEN 1
           WHEN matched.need_kind=2 THEN 2
           WHEN matched.need_kind=3 THEN 3
       END::SMALLINT AS admission_reason
  FROM matched;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1 AS
SELECT consumer_ref,query_ref,policy_ref,admission_reason,admitted,
       count(*)::BIGINT AS admission_rows,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_h9_external_admission_v1
 GROUP BY consumer_ref,query_ref,policy_ref,admission_reason,admitted;

-- Existing contract-derived needs from the pre-119 lexical admission rule are
-- intentionally invalidated. They are historical control receipts, not truth.
-- Recompilation through the function below reactivates only structurally
-- admitted intersections. Manual origins are independently retained, but an
-- invalid manual origin is also made inactive to preserve the global invariant.
UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND need.need_kind IN (1,2,3);

UPDATE execution.semantic_pnf_consumer_external_need AS need
   SET active=FALSE,anchor_object_id=NULL,label_symbol_id=NULL
 WHERE need.need_kind IN (1,2,3);

-- Compile the current H9 residual through structural admission. Contract origin
-- rows are rebuilt exactly for one document/consumer fibre. Need identity stays
-- provider/axis/revision based; the selected occurrence anchor is a rebuildable
-- execution projection attached to that semantic need.
CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_h9_external_needs_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
       SET active=FALSE,updated_at=CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_consumer_external_need AS need,
           execution.semantic_pnf_demand AS demand,
           execution.semantic_pnf_region AS region
     WHERE origin.need_id=need.need_id
       AND origin.origin_kind=2
       AND demand.demand_id=need.demand_id
       AND region.region_id=demand.source_region_id
       AND need.consumer_ref=selected_consumer_ref
       AND need.query_ref=selected_query_ref
       AND need.policy_ref=selected_policy_ref
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    WITH admitted AS MATERIALIZED (
        SELECT DISTINCT admission.contract_id,admission.demand_id,
               admission.need_kind,admission.provider_id,admission.axis_kind,
               admission.provider_property_numeric_id,admission.need_revision,
               admission.priority,admission.minimum_source_epoch,
               admission.anchor_object_id,admission.label_symbol_id
          FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=admission.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE admission.admitted
           AND admission.consumer_ref=selected_consumer_ref
           AND admission.query_ref=selected_query_ref
           AND admission.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
    )
    INSERT INTO execution.semantic_pnf_consumer_external_need
        (demand_id,consumer_ref,query_ref,policy_ref,need_kind,provider_id,
         axis_kind,provider_property_numeric_id,priority,need_revision,active,
         minimum_source_epoch,anchor_object_id,label_symbol_id)
    SELECT admitted.demand_id,selected_consumer_ref,selected_query_ref,
           selected_policy_ref,admitted.need_kind,admitted.provider_id,
           admitted.axis_kind,admitted.provider_property_numeric_id,
           admitted.priority,admitted.need_revision,TRUE,
           admitted.minimum_source_epoch,admitted.anchor_object_id,
           admitted.label_symbol_id
      FROM admitted
    ON CONFLICT DO NOTHING;

    WITH admitted AS MATERIALIZED (
        SELECT DISTINCT admission.contract_id,admission.demand_id,
               admission.need_kind,admission.provider_id,admission.axis_kind,
               admission.provider_property_numeric_id,admission.need_revision,
               admission.priority,admission.minimum_source_epoch,
               admission.anchor_object_id,admission.label_symbol_id
          FROM execution.semantic_pnf_h9_external_admission_v1 AS admission
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=admission.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE admission.admitted
           AND admission.consumer_ref=selected_consumer_ref
           AND admission.query_ref=selected_query_ref
           AND admission.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
    ), selected_need AS MATERIALIZED (
        SELECT need.need_id,admitted.contract_id,admitted.priority,
               admitted.minimum_source_epoch,admitted.anchor_object_id,
               admitted.label_symbol_id
          FROM admitted
          JOIN execution.semantic_pnf_consumer_external_need AS need
            ON need.demand_id=admitted.demand_id
           AND need.consumer_ref=selected_consumer_ref
           AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref
           AND need.need_kind=admitted.need_kind
           AND need.provider_id=admitted.provider_id
           AND COALESCE(need.axis_kind,0)=COALESCE(admitted.axis_kind,0)
           AND COALESCE(need.provider_property_numeric_id,0)=
               COALESCE(admitted.provider_property_numeric_id,0)
           AND need.need_revision=admitted.need_revision
    )
    INSERT INTO execution.semantic_pnf_consumer_external_need_origin
        (need_id,origin_kind,contract_id,active,priority,minimum_source_epoch)
    SELECT selected_need.need_id,2,selected_need.contract_id,TRUE,
           selected_need.priority,selected_need.minimum_source_epoch
      FROM selected_need
    ON CONFLICT(need_id,contract_id) WHERE origin_kind=2
    DO UPDATE SET active=TRUE,priority=EXCLUDED.priority,
                  minimum_source_epoch=EXCLUDED.minimum_source_epoch,
                  updated_at=CURRENT_TIMESTAMP;

    -- Rebuild need liveness and anchor projection exactly for this fibre.
    WITH scoped_need AS MATERIALIZED (
        SELECT need.need_id,
               COALESCE(bool_or(origin.active),FALSE) AS any_active,
               min(origin.priority) FILTER (WHERE origin.active) AS min_priority,
               max(origin.minimum_source_epoch) FILTER (WHERE origin.active) AS max_floor
          FROM execution.semantic_pnf_consumer_external_need AS need
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
          LEFT JOIN execution.semantic_pnf_consumer_external_need_origin AS origin
            ON origin.need_id=need.need_id
         WHERE need.consumer_ref=selected_consumer_ref
           AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
         GROUP BY need.need_id
    ), preferred AS MATERIALIZED (
        SELECT need.need_id,anchor.source_object_id,anchor.label_symbol_id
          FROM execution.semantic_pnf_consumer_external_need AS need
          LEFT JOIN execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS anchor
            ON anchor.demand_id=need.demand_id
          JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
          JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
         WHERE need.consumer_ref=selected_consumer_ref
           AND need.query_ref=selected_query_ref
           AND need.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
    )
    UPDATE execution.semantic_pnf_consumer_external_need AS need
       SET active=scoped_need.any_active,
           priority=COALESCE(scoped_need.min_priority,need.priority),
           minimum_source_epoch=scoped_need.max_floor,
           anchor_object_id=CASE WHEN scoped_need.any_active THEN preferred.source_object_id ELSE NULL END,
           label_symbol_id=CASE WHEN scoped_need.any_active THEN preferred.label_symbol_id ELSE NULL END
      FROM scoped_need,preferred
     WHERE need.need_id=scoped_need.need_id
       AND preferred.need_id=need.need_id;

    PERFORM execution.refresh_numeric_pnf_external_request_observer_state();
    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();

    SELECT count(DISTINCT need.need_id)::BIGINT INTO affected
      FROM execution.semantic_pnf_consumer_external_need AS need
      JOIN execution.semantic_pnf_consumer_external_need_origin AS origin
        ON origin.need_id=need.need_id AND origin.origin_kind=2 AND origin.active
      JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=need.demand_id
      JOIN execution.semantic_pnf_region AS region ON region.region_id=demand.source_region_id
     WHERE need.active
       AND need.anchor_object_id IS NOT NULL
       AND need.label_symbol_id IS NOT NULL
       AND need.consumer_ref=selected_consumer_ref
       AND need.query_ref=selected_query_ref
       AND need.policy_ref=selected_policy_ref
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;
    RETURN affected;
END;
$$;

-- Planner replacement: provider labels are only the admitted occurrence label.
-- Property enrichment never creates discovery work as a fallback; if the world
-- candidate fibre disappears between compile and plan, it remains unresolved.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE external_need RECORD; candidate_row RECORD; attachment_row RECORD;
        request_id_value BIGINT; affected BIGINT := 0;
BEGIN
    FOR external_need IN
        SELECT need_row.*
          FROM execution.semantic_pnf_consumer_external_need AS need_row
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=need_row.demand_id
           AND work.consumer_ref=need_row.consumer_ref
           AND work.query_ref=need_row.query_ref
           AND work.policy_ref=need_row.policy_ref
           AND work.horizon=9 AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=need_row.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE need_row.active
           AND need_row.anchor_object_id IS NOT NULL
           AND need_row.label_symbol_id IS NOT NULL
           AND need_row.consumer_ref=selected_consumer_ref
           AND need_row.query_ref=selected_query_ref
           AND need_row.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
               need_row.policy_ref,6::SMALLINT
           )
         ORDER BY need_row.priority,need_row.demand_id,need_row.need_id
    LOOP
        IF external_need.need_kind=1 THEN
            IF EXISTS (
                SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS cached
                 WHERE cached.label_symbol_id=external_need.label_symbol_id
            ) THEN
                CONTINUE;
            END IF;
            request_id_value := execution.ensure_numeric_pnf_external_request(
                external_need.provider_id,1::SMALLINT,external_need.label_symbol_id,NULL,
                NULL,NULL,external_need.need_revision,external_need.priority
            );
            INSERT INTO execution.semantic_pnf_external_request_member
                (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
            VALUES (request_id_value,external_need.demand_id,
                    external_need.consumer_ref,external_need.query_ref,
                    external_need.policy_ref,external_need.need_kind)
            ON CONFLICT DO NOTHING;
            affected:=affected+1;
        ELSIF external_need.need_kind=2 THEN
            FOR candidate_row IN
                SELECT candidate.world_entity_id
                  FROM execution.semantic_pnf_label_world_candidate AS candidate
                 WHERE candidate.label_symbol_id=external_need.label_symbol_id
                 ORDER BY candidate.candidate_ordinal,candidate.world_entity_id
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    external_need.provider_id,2::SMALLINT,external_need.label_symbol_id,
                    candidate_row.world_entity_id,
                    external_need.provider_property_numeric_id,
                    external_need.axis_kind,external_need.need_revision,
                    external_need.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,external_need.demand_id,
                        external_need.consumer_ref,external_need.query_ref,
                        external_need.policy_ref,external_need.need_kind)
                ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        ELSE
            FOR attachment_row IN
                SELECT DISTINCT attachment.world_entity_id,attachment.label_symbol_id
                  FROM execution.semantic_pnf_object_token_support AS support
                  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
                    ON attachment.token_id=support.token_id
                 WHERE support.object_id=external_need.anchor_object_id
                   AND attachment.label_symbol_id=external_need.label_symbol_id
                   AND attachment.attachment_state=1
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    external_need.provider_id,3::SMALLINT,attachment_row.label_symbol_id,
                    attachment_row.world_entity_id,NULL,NULL,
                    external_need.need_revision,external_need.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,external_need.demand_id,
                        external_need.consumer_ref,external_need.query_ref,
                        external_need.policy_ref,external_need.need_kind)
                ON CONFLICT DO NOTHING;
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
