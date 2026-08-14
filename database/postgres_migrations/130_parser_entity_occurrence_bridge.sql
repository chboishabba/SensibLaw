BEGIN;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parser_entity_surface_label (
    entity_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_parser_entity_span(entity_id) ON DELETE CASCADE,
    label_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    entity_type_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_parser_entity_surface_labels()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    WITH ordered AS MATERIALIZED (
        SELECT entity.entity_id,entity.entity_type_symbol_id,
               token.token_id,token.start_char,token.end_char,
               symbol.symbol_text,
               lag(token.end_char) OVER (
                   PARTITION BY entity.entity_id
                   ORDER BY token.start_char,token.token_id
               ) AS previous_end
          FROM execution.semantic_parser_entity_span AS entity
          JOIN execution.semantic_parser_token AS token
            ON token.run_ref=entity.run_ref
           AND token.document_ref=entity.document_ref
           AND token.sentence_ref=entity.sentence_ref
           AND token.start_char>=entity.start_char
           AND token.end_char<=entity.end_char
           AND token.representation_version=2
          JOIN execution.semantic_symbol AS symbol
            ON symbol.symbol_id=token.orth_symbol_id
         WHERE entity.representation_version=2
           AND entity.entity_id IS NOT NULL
           AND entity.entity_type_symbol_id IS NOT NULL
    ), surfaces AS MATERIALIZED (
        SELECT entity_id,min(entity_type_symbol_id) AS entity_type_symbol_id,
               string_agg(
                   CASE
                     WHEN previous_end IS NULL THEN symbol_text
                     ELSE repeat(' ',greatest((start_char-previous_end)::INTEGER,0))
                          || symbol_text
                   END,
                   '' ORDER BY start_char,token_id
               ) AS surface_text
          FROM ordered
         GROUP BY entity_id
    ), upserted AS (
        INSERT INTO execution.semantic_pnf_parser_entity_surface_label
            (entity_id,label_symbol_id,entity_type_symbol_id,updated_at)
        SELECT surface.entity_id,
               execution.ensure_semantic_symbol(1::SMALLINT,surface.surface_text),
               surface.entity_type_symbol_id,CURRENT_TIMESTAMP
          FROM surfaces AS surface
         WHERE surface.surface_text<>''
        ON CONFLICT(entity_id) DO UPDATE SET
            label_symbol_id=EXCLUDED.label_symbol_id,
            entity_type_symbol_id=EXCLUDED.entity_type_symbol_id,
            updated_at=CURRENT_TIMESTAMP
        RETURNING 1
    )
    SELECT count(*) INTO affected FROM upserted;
    RETURN affected;
END;
$$;

SELECT execution.refresh_numeric_pnf_parser_entity_surface_labels();

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS
SELECT DISTINCT strong.demand_id,strong.object_id,
       entity.entity_id,entity.entity_type_symbol_id,label.label_symbol_id
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS strong
  JOIN execution.semantic_pnf_object_token_support AS object_token
    ON object_token.object_id=strong.object_id
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=object_token.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_entity_span AS entity
    ON entity.representation_version=2
   AND entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_pnf_parser_entity_surface_label AS label
    ON label.entity_id=entity.entity_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 AS
SELECT occurrence.demand_id,
       min(occurrence.object_id) AS source_object_id,
       min(occurrence.entity_id) AS entity_id,
       min(occurrence.label_symbol_id) AS label_symbol_id,
       min(occurrence.entity_type_symbol_id) AS entity_type_symbol_id
  FROM execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS occurrence
 GROUP BY occurrence.demand_id
HAVING count(DISTINCT occurrence.entity_id)=1;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_attached_world_candidate_v1 AS
SELECT DISTINCT strong.demand_id,strong.object_id AS source_object_id,
       attachment.label_symbol_id,attachment.world_entity_id
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS strong
  JOIN execution.semantic_pnf_object_token_support AS object_token
    ON object_token.object_id=strong.object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=object_token.token_id
   AND attachment.attachment_state=1;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1 AS
SELECT anchor.demand_id,anchor.source_object_id,1::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 AS anchor
UNION
SELECT attached.demand_id,attached.source_object_id,3::SMALLINT
  FROM execution.semantic_pnf_h9_attached_world_candidate_v1 AS attached;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1 AS
SELECT anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       1::SMALLINT AS anchor_kind,100::SMALLINT AS anchor_strength
  FROM execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 AS anchor
UNION
SELECT attached.demand_id,attached.source_object_id,attached.label_symbol_id,
       3::SMALLINT,300::SMALLINT
  FROM execution.semantic_pnf_h9_attached_world_candidate_v1 AS attached;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS
WITH anchors AS MATERIALIZED (
    SELECT * FROM execution.semantic_pnf_h9_entity_label_anchor_v1
), cardinality AS MATERIALIZED (
    SELECT demand_id,
           count(DISTINCT (source_object_id,label_symbol_id)) AS anchor_count
      FROM anchors
     GROUP BY demand_id
)
SELECT DISTINCT ON (anchor.demand_id)
       anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       anchor.anchor_kind,anchor.anchor_strength
  FROM anchors AS anchor
  JOIN cardinality USING(demand_id)
 WHERE cardinality.anchor_count=1
 ORDER BY anchor.demand_id,anchor.anchor_strength DESC,anchor.anchor_kind;

DROP VIEW IF EXISTS execution.semantic_pnf_h9_external_admission_summary_v1;
DROP VIEW IF EXISTS execution.semantic_pnf_h9_external_admission_v1;
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
           EXISTS (SELECT 1 FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 s WHERE s.demand_id=h9.demand_id) AS has_strong_occurrence,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 b WHERE b.demand_id=h9.demand_id) AS entity_bearing,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_label_world_candidate c WHERE c.label_symbol_id=anchor.label_symbol_id) AS has_world_candidate,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_h9_attached_world_candidate_v1 a WHERE a.demand_id=h9.demand_id AND a.label_symbol_id=anchor.label_symbol_id) AS has_attached_world_candidate,
           execution.numeric_pnf_consumer_stop_at_horizon(h9.demand_id,h9.consumer_ref,h9.query_ref,h9.policy_ref,6::SMALLINT) AS consumer_sufficient,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_frontier_resolution p WHERE p.demand_id=h9.demand_id AND p.outcome_state=2 AND p.candidate_count=1) AS deductively_resolved
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
         WHEN NOT has_strong_occurrence OR NOT entity_bearing OR anchor_object_id IS NULL OR label_symbol_id IS NULL THEN FALSE
         WHEN need_kind=2 AND NOT has_world_candidate THEN FALSE
         WHEN need_kind=3 AND NOT has_attached_world_candidate THEN FALSE
         ELSE TRUE
       END AS admitted,
       CASE
         WHEN contract_id IS NULL THEN 10
         WHEN consumer_sufficient THEN 15
         WHEN deductively_resolved THEN 16
         WHEN NOT has_strong_occurrence THEN 11
         WHEN NOT entity_bearing THEN 12
         WHEN anchor_object_id IS NULL OR label_symbol_id IS NULL THEN 13
         WHEN need_kind=2 AND NOT has_world_candidate THEN 14
         WHEN need_kind=3 AND NOT has_attached_world_candidate THEN 14
         WHEN need_kind=1 THEN 1 WHEN need_kind=2 THEN 2 WHEN need_kind=3 THEN 3
       END::SMALLINT AS admission_reason
  FROM matched;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1 AS
SELECT consumer_ref,query_ref,policy_ref,admission_reason,admitted,
       count(*)::BIGINT AS admission_rows,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_h9_external_admission_v1
 GROUP BY consumer_ref,query_ref,policy_ref,admission_reason,admitted;

UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
        WHERE bearing.demand_id=need.demand_id
          AND bearing.source_object_id=need.anchor_object_id
   );

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
  FROM state
 WHERE state.need_id=need.need_id;

SELECT execution.refresh_numeric_pnf_external_request_observer_state();
SELECT execution.refresh_numeric_pnf_external_request_cache_state();

COMMIT;
