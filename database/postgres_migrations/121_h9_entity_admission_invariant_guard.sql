BEGIN;

-- 121: make the entity-bearing boundary directly auditable and retire stale
-- provider-ready work immediately after 119/120 reconciliation.

CREATE OR REPLACE FUNCTION execution.verify_numeric_pnf_h9_external_admission()
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT NOT EXISTS (
    SELECT 1
      FROM execution.semantic_pnf_consumer_external_need AS need
     WHERE need.active
       AND (
           need.anchor_object_id IS NULL
           OR need.label_symbol_id IS NULL
           OR NOT EXISTS (
               SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 AS bearing
                WHERE bearing.demand_id=need.demand_id
                  AND bearing.source_object_id=need.anchor_object_id
           )
           OR (need.need_kind=2 AND NOT EXISTS (
               SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
                WHERE candidate.label_symbol_id=need.label_symbol_id
           ))
           OR (need.need_kind=3 AND NOT EXISTS (
               SELECT 1 FROM execution.semantic_pnf_h9_attached_world_candidate_v1 AS attached
                WHERE attached.demand_id=need.demand_id
                  AND attached.source_object_id=need.anchor_object_id
                  AND attached.label_symbol_id=need.label_symbol_id
           ))
       )
);
$$;

-- Request membership is historical provenance. Observer-state refresh is the
-- execution projection that turns now-invalid pre-119 requests dormant without
-- deleting their cold transport receipts.
SELECT execution.refresh_numeric_pnf_external_request_observer_state();
SELECT execution.refresh_numeric_pnf_external_request_cache_state();

COMMIT;
