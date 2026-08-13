BEGIN;

-- 123: entity-bearing H9 support comes from strong demand-occurrence provenance,
-- not the legacy demand.source_object_id projection.
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1 AS
SELECT DISTINCT support.demand_id,support.object_id AS source_object_id,
       1::SMALLINT AS anchor_kind
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS support
  JOIN execution.semantic_pnf_object_mention_support AS object_support
    ON object_support.object_id=support.object_id
  JOIN execution.semantic_pnf_mention AS mention
    ON mention.mention_id=object_support.mention_id
   AND mention.mention_kind=1 AND mention.active
UNION
SELECT DISTINCT support.demand_id,support.object_id,2::SMALLINT
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS support
  JOIN execution.semantic_pnf_identity_projection AS identity_projection
    ON identity_projection.source_object_id=support.object_id
UNION
SELECT DISTINCT support.demand_id,support.object_id,3::SMALLINT
  FROM execution.semantic_pnf_demand_strong_occurrence_support_v1 AS support
  JOIN execution.semantic_pnf_object_token_support AS object_token
    ON object_token.object_id=support.object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=object_token.token_id
   AND attachment.attachment_state=1;

COMMIT;
