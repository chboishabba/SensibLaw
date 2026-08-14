BEGIN;

-- 132: supersede migration 129's region-level sibling diagnostic. A sibling
-- object elsewhere in the same region is not proof of the same textual
-- occurrence. Audit the exact parser occurrence instead, using numeric token and
-- entity-span coordinates. This matches the production admission bridge in 130.
DROP VIEW IF EXISTS execution.semantic_pnf_h9_object_entity_occurrence_summary_v1;
DROP VIEW IF EXISTS execution.semantic_pnf_object_entity_occurrence_audit_v1;

CREATE VIEW execution.semantic_pnf_object_entity_occurrence_audit_v1 AS
WITH cohort AS (
    SELECT DISTINCT support.demand_id,support.object_id
      FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS support
      JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
        ON work.demand_id=support.demand_id
       AND work.horizon=9 AND work.work_state=1
), direct AS (
    SELECT DISTINCT cohort.demand_id,cohort.object_id
      FROM cohort
      JOIN execution.semantic_pnf_object_mention_support AS object_mention
        ON object_mention.object_id=cohort.object_id
      JOIN execution.semantic_pnf_mention AS mention
        ON mention.mention_id=object_mention.mention_id
       AND mention.mention_kind=1 AND mention.active
), parser_span AS (
    SELECT DISTINCT cohort.demand_id,cohort.object_id,entity.entity_id
      FROM cohort
      JOIN execution.semantic_pnf_object_token_support AS object_token
        ON object_token.object_id=cohort.object_id
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
), aggregate AS (
    SELECT cohort.demand_id,cohort.object_id,
           EXISTS (
               SELECT 1 FROM direct
                WHERE direct.demand_id=cohort.demand_id
                  AND direct.object_id=cohort.object_id
           ) AS direct_attachment,
           count(DISTINCT parser_span.entity_id)::BIGINT AS parser_entity_count
      FROM cohort
      LEFT JOIN parser_span
        ON parser_span.demand_id=cohort.demand_id
       AND parser_span.object_id=cohort.object_id
     GROUP BY cohort.demand_id,cohort.object_id
)
SELECT aggregate.*,
       CASE
         WHEN direct_attachment THEN 1
         WHEN parser_entity_count=1 THEN 2
         WHEN parser_entity_count>1 THEN 3
         ELSE 4
       END::SMALLINT AS occurrence_relation_kind
  FROM aggregate;

CREATE VIEW execution.semantic_pnf_h9_object_entity_occurrence_summary_v1 AS
SELECT occurrence_relation_kind,
       count(*)::BIGINT AS object_count,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_object_entity_occurrence_audit_v1
 GROUP BY occurrence_relation_kind;

COMMIT;
