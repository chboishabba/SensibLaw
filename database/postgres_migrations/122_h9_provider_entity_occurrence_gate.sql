BEGIN;

-- 122: a locally admitted identity projection is semantic evidence, not by
-- itself an entity occurrence suitable for external discovery.  The live GWB
-- audit exposed ordinary lexical objects such as "read" and "meeting" through
-- that branch.  Provider admission therefore requires either a parser entity
-- mention or an occurrence-attached world candidate.
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
SELECT DISTINCT demand.demand_id,demand.source_object_id,3::SMALLINT
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_token_support AS support
    ON support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=support.token_id AND attachment.attachment_state=1
 WHERE demand.source_object_id IS NOT NULL;

-- Reconcile existing origins against the stricter occurrence boundary.  The
-- receipts and historical request memberships remain immutable; only active
-- observer projections are withdrawn.
UPDATE execution.semantic_pnf_consumer_external_need_origin AS origin
   SET active=FALSE,updated_at=CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_consumer_external_need AS need
 WHERE origin.need_id=need.need_id
   AND origin.active
   AND NOT EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
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
