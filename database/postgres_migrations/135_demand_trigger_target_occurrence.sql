BEGIN;

-- 135: demand occurrence provenance has distinct semantic roles.
--
-- Historical demand rows were created before trigger and target occurrences
-- were distinguished. They are intentionally NOT backfilled from lexical
-- symbols, object heads, dependency neighbours, or region proximity. Missing
-- target provenance is an unresolved state and cannot authorize H9 provider
-- work.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_occurrence_provenance (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    occurrence_role SMALLINT NOT NULL CHECK (occurrence_role IN (1,2,3)),
    token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    object_id BIGINT
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE SET NULL,
    ordinal SMALLINT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    producer_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(demand_id,occurrence_role,token_id,ordinal)
);

-- occurrence_role:
--   1 trigger  token whose parser/factor relation caused the demand to exist
--   2 target   token/object the unresolved semantic question is actually about
--   3 evidence other producer-licensed support token
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_occurrence_role_idx
    ON execution.semantic_pnf_demand_occurrence_provenance
       (occurrence_role,token_id,demand_id);
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_target_object_idx
    ON execution.semantic_pnf_demand_occurrence_provenance
       (object_id,demand_id)
    WHERE occurrence_role=2 AND object_id IS NOT NULL;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_trigger_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=1;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_target_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=2;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_evidence_occurrence_v1 AS
SELECT provenance.demand_id,provenance.token_id,provenance.object_id,
       provenance.ordinal,provenance.producer_ref
  FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
 WHERE provenance.occurrence_role=3;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_occurrence_provenance_audit_v1 AS
SELECT demand.demand_id,
       count(*) FILTER (WHERE provenance.occurrence_role=1)::BIGINT
           AS trigger_occurrence_count,
       count(*) FILTER (WHERE provenance.occurrence_role=2)::BIGINT
           AS target_occurrence_count,
       count(*) FILTER (WHERE provenance.occurrence_role=3)::BIGINT
           AS evidence_occurrence_count,
       CASE
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=2)=1 THEN 1
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=2)>1 THEN 2
         WHEN count(*) FILTER (WHERE provenance.occurrence_role=1)>0 THEN 11
         ELSE 10
       END::SMALLINT AS provenance_state
  FROM execution.semantic_pnf_demand AS demand
  LEFT JOIN execution.semantic_pnf_demand_occurrence_provenance AS provenance
    ON provenance.demand_id=demand.demand_id
 GROUP BY demand.demand_id;

-- H9-specific structural support. The older generic strong-occurrence view is
-- retained for non-H9 audit/compatibility. World-entity work is licensed only
-- by producer-authored target occurrences that also carry the exact PNF object
-- created for that target token.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_h9_target_support_v1 AS
SELECT target.demand_id,target.token_id,target.object_id,
       target.ordinal,target.producer_ref
  FROM execution.semantic_pnf_demand_target_occurrence_v1 AS target
 WHERE target.object_id IS NOT NULL;

-- Rewire the primary raw and quality-gated parser-entity occurrence bridges to
-- the semantic target token. Trigger/evidence occurrences are deliberately not
-- eligible for world-entity admission.
CREATE OR REPLACE VIEW execution.semantic_pnf_demand_parser_entity_occurrence_v1 AS
SELECT DISTINCT target.demand_id,target.object_id,
       entity.entity_id,entity.entity_type_symbol_id,label.label_symbol_id
  FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=target.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_provider_entity_span_v1 AS entity
    ON entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_pnf_parser_entity_surface_label AS label
    ON label.entity_id=entity.entity_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_demand_raw_parser_entity_occurrence_v1 AS
SELECT DISTINCT target.demand_id,target.object_id,entity.entity_id,
       entity.entity_type_symbol_id,quality.quality_state
  FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
  JOIN execution.semantic_parser_token AS token
    ON token.token_id=target.token_id
   AND token.representation_version=2
  JOIN execution.semantic_parser_entity_span AS entity
    ON entity.representation_version=2
   AND entity.run_ref=token.run_ref
   AND entity.document_ref=token.document_ref
   AND entity.sentence_ref=token.sentence_ref
   AND entity.start_char<=token.start_char
   AND entity.end_char>=token.end_char
  JOIN execution.semantic_parser_entity_span_quality_v1 AS quality
    ON quality.entity_id=entity.entity_id;

-- Historical/current provider origins whose demand lacks exact producer target
-- provenance are withdrawn, never deleted. This does not resolve or refute the
-- demand; it only removes permission to cross the external boundary.
UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_demand_h9_target_support_v1 AS target
        WHERE target.demand_id=need.demand_id
          AND target.object_id=need.anchor_object_id
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
