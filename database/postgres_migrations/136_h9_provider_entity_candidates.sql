BEGIN;

-- 136: H9 consumes canonical provider candidates supported by one or more
-- quality-valid parser observations. Candidate multiplicity remains explicit;
-- only one distinct provider candidate may become the anchor for a demand.

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS
SELECT DISTINCT strong.demand_id,strong.object_id,
       candidate.provider_entity_candidate_id AS entity_id,
       candidate.entity_type_symbol_id,candidate.label_symbol_id
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 strong
  JOIN execution.semantic_pnf_object_token_support object_token
    ON object_token.object_id=strong.object_id
  JOIN execution.semantic_parser_token token
    ON token.token_id=object_token.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_provider_entity_candidate_current_v1 candidate
    ON candidate.run_ref=token.run_ref
   AND candidate.document_ref=token.document_ref
   AND candidate.sentence_ref=token.sentence_ref
   AND candidate.start_char<=token.start_char
   AND candidate.end_char>=token.end_char;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 AS
SELECT occurrence.demand_id,
       min(occurrence.object_id) AS source_object_id,
       min(occurrence.entity_id) AS entity_id,
       min(occurrence.label_symbol_id) AS label_symbol_id,
       min(occurrence.entity_type_symbol_id) AS entity_type_symbol_id
  FROM execution.semantic_pnf_demand_parser_entity_occurrence_v1 occurrence
 GROUP BY occurrence.demand_id
HAVING count(DISTINCT occurrence.entity_id)=1;

-- Existing bearing/label views are re-declared so live PostgreSQL upgrades do
-- not depend on planner/view invalidation order.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1 AS
SELECT anchor.demand_id,anchor.source_object_id,1::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 anchor
UNION
SELECT attached.demand_id,attached.source_object_id,3::SMALLINT
  FROM execution.semantic_pnf_h9_attached_world_candidate_v1 attached;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1 AS
SELECT anchor.demand_id,anchor.source_object_id,anchor.label_symbol_id,
       1::SMALLINT AS anchor_kind,100::SMALLINT AS anchor_strength
  FROM execution.semantic_pnf_h9_unique_parser_entity_anchor_v1 anchor
UNION
SELECT attached.demand_id,attached.source_object_id,attached.label_symbol_id,
       3::SMALLINT,300::SMALLINT
  FROM execution.semantic_pnf_h9_attached_world_candidate_v1 attached;

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
  FROM anchors anchor
  JOIN cardinality USING(demand_id)
 WHERE cardinality.anchor_count=1
 ORDER BY anchor.demand_id,anchor.anchor_strength DESC,anchor.anchor_kind;

-- Withdraw stale external origins when the current provider-candidate fibre no
-- longer supplies their anchor. History is retained.
UPDATE execution.semantic_pnf_consumer_external_need_origin origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_h9_entity_bearing_v1 bearing
        WHERE bearing.demand_id=need.demand_id
          AND bearing.source_object_id=need.anchor_object_id
   );

WITH state AS MATERIALIZED (
    SELECT need.need_id,COALESCE(bool_or(origin.active),FALSE) AS any_active,
           min(origin.priority) FILTER (WHERE origin.active) AS min_priority,
           max(origin.minimum_source_epoch) FILTER (WHERE origin.active) AS max_floor
      FROM execution.semantic_pnf_consumer_external_need need
      LEFT JOIN execution.semantic_pnf_consumer_external_need_origin origin
        ON origin.need_id=need.need_id
     GROUP BY need.need_id
)
UPDATE execution.semantic_pnf_consumer_external_need need
   SET active=state.any_active,
       priority=COALESCE(state.min_priority,need.priority),
       minimum_source_epoch=state.max_floor
  FROM state
 WHERE state.need_id=need.need_id;

SELECT execution.refresh_numeric_pnf_external_request_observer_state();
SELECT execution.refresh_numeric_pnf_external_request_cache_state();

COMMIT;
