BEGIN;

-- 129: observe object-to-parser-entity occurrence relations without equating
-- objects with entity mentions. This is intentionally an audit surface; H9
-- admission does not consume it until a later migration defines the canonical
-- occurrence support carrier.
CREATE OR REPLACE VIEW execution.semantic_pnf_object_entity_occurrence_audit_v1 AS
WITH cohort AS (
    SELECT DISTINCT support.demand_id,support.object_id
      FROM execution.semantic_pnf_demand_occurrence_support support
      JOIN execution.semantic_pnf_consumer_horizon_work_queue work
        ON work.demand_id=support.demand_id
       AND work.horizon=9 AND work.work_state=1
     WHERE support.support_kind IN (1,2)
), object_tokens AS (
    SELECT cohort.demand_id,cohort.object_id,object.region_id,
           array_agg(DISTINCT support.token_id) AS token_ids,
           min(parser_token.start_char) AS object_start,
           max(parser_token.end_char) AS object_end
      FROM cohort
      JOIN execution.semantic_pnf_object object ON object.object_id=cohort.object_id
      JOIN execution.semantic_pnf_object_token_support support
        ON support.object_id=object.object_id
      JOIN execution.semantic_parser_token parser_token
        ON parser_token.token_id=support.token_id
     GROUP BY cohort.demand_id,cohort.object_id,object.region_id
), entity_mentions AS (
    SELECT mention.mention_id,mention.region_id,mention.start_char,mention.end_char
      FROM execution.semantic_pnf_mention mention
     WHERE mention.mention_kind=1 AND mention.active
), pairs AS (
    SELECT object_tokens.demand_id,object_tokens.object_id,entity_mentions.mention_id,
           EXISTS (
               SELECT 1 FROM execution.semantic_pnf_object_mention_support direct
                WHERE direct.object_id=object_tokens.object_id
                  AND direct.mention_id=entity_mentions.mention_id
           ) AS direct_attachment,
           EXISTS (
               SELECT 1
                 FROM unnest(object_tokens.token_ids) object_token_id
                 JOIN execution.semantic_pnf_mention_token mention_token
                   ON mention_token.token_id=object_token_id
                  AND mention_token.mention_id=entity_mentions.mention_id
           ) AS shared_entity_token,
           entity_mentions.start_char <= object_tokens.object_start
             AND entity_mentions.end_char >= object_tokens.object_end
             AS entity_span_contains_all_object_tokens,
           EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_object_token_support sibling_support
                 JOIN execution.semantic_pnf_mention_token sibling_mention_token
                   ON sibling_mention_token.token_id=sibling_support.token_id
                  AND sibling_mention_token.mention_id=entity_mentions.mention_id
                WHERE sibling_support.object_id<>object_tokens.object_id
           ) AS entity_on_sibling_object
      FROM object_tokens
      LEFT JOIN entity_mentions
        ON entity_mentions.region_id=object_tokens.region_id
), summary AS (
    SELECT object_tokens.demand_id,object_tokens.object_id,
           bool_or(COALESCE(pairs.direct_attachment,FALSE)) AS direct_attachment,
           bool_or(COALESCE(pairs.shared_entity_token,FALSE)) AS shared_entity_token,
           bool_or(COALESCE(pairs.entity_span_contains_all_object_tokens,FALSE))
               AS entity_span_contains_all_object_tokens,
           bool_or(COALESCE(pairs.entity_on_sibling_object,FALSE))
               AS entity_on_sibling_object
      FROM object_tokens
      LEFT JOIN pairs USING(demand_id,object_id)
     GROUP BY object_tokens.demand_id,object_tokens.object_id
)
SELECT summary.*,
       CASE
         WHEN summary.direct_attachment THEN 1
         WHEN summary.shared_entity_token THEN 2
         WHEN summary.entity_span_contains_all_object_tokens THEN 3
         WHEN summary.entity_on_sibling_object THEN 4
         ELSE 5
       END::SMALLINT AS occurrence_relation_kind
  FROM summary;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_object_entity_occurrence_summary_v1 AS
SELECT occurrence_relation_kind,
       count(*)::BIGINT AS object_count,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_object_entity_occurrence_audit_v1
 GROUP BY occurrence_relation_kind;

COMMIT;
