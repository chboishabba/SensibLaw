BEGIN;

-- A demand teardown cascades to its live candidates.  At the candidate AFTER
-- DELETE boundary the parent demand is already absent, so that cleanup is not
-- a planner supersession and cannot be appended to demand-keyed lifecycle
-- history.  Keep ordinary planner replacement append-only while ignoring only
-- those cascade rows whose demand no longer exists.
CREATE OR REPLACE FUNCTION execution.observe_numeric_pnf_candidate_delete_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_candidate_observation
        (demand_id,target_kind,target_id,observation_kind,
         planning_ordinal,source_interface_id,ancestor_distance,
         index_rank,candidate_score)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,2,
           candidate.ordinal,candidate.source_interface_id,
           candidate.ancestor_distance,candidate.index_rank,
           candidate.candidate_score
      FROM deleted_candidate AS candidate
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id=candidate.demand_id;

    INSERT INTO execution.semantic_pnf_candidate_execution_event
        (demand_id,target_kind,target_id,event_kind,reason_ref)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,
           5,'planner-replan-superseded'
      FROM deleted_candidate AS candidate
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id=candidate.demand_id;

    RETURN NULL;
END;
$$;

COMMIT;
