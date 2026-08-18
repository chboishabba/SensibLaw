BEGIN;

-- 162: candidate planning is already set-wise, but migration 086 decomposed each
-- inserted/deleted candidate into one row trigger which then emitted an
-- observation row, an execution event and (on insert) neutral H3 evidence.
-- Preserve the exact append-only lifecycle while projecting the candidate fibre
-- as a relation.

DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_insert
    ON execution.semantic_pnf_demand_candidate;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_delete
    ON execution.semantic_pnf_demand_candidate;

CREATE OR REPLACE FUNCTION execution.observe_numeric_pnf_candidate_insert_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_candidate_observation
        (demand_id,target_kind,target_id,observation_kind,
         planning_ordinal,source_interface_id,ancestor_distance,
         index_rank,candidate_score)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,1,
           candidate.ordinal,candidate.source_interface_id,
           candidate.ancestor_distance,candidate.index_rank,
           candidate.candidate_score
      FROM inserted_candidate AS candidate;

    INSERT INTO execution.semantic_pnf_candidate_execution_event
        (demand_id,target_kind,target_id,event_kind,reason_ref)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,
           1,'planner-active'
      FROM inserted_candidate AS candidate;

    -- Candidate membership is neutral structural evidence. The textual
    -- evidence_ref is append-only audit identity; semantic coordinates remain
    -- numeric.
    INSERT INTO execution.semantic_pnf_candidate_evidence
        (demand_id,target_kind,target_id,evidence_ref,
         evidence_family,horizon,signed_residual,evidence_kind,
         provenance_ref,source_interface_id)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,
           'planner-membership:' || candidate.target_kind::TEXT
               || ':' || candidate.target_id::TEXT,
           1,3,0,'candidate_generation',
           'semantic_pnf_demand_candidate',candidate.source_interface_id
      FROM inserted_candidate AS candidate
    ON CONFLICT(demand_id,target_kind,target_id,evidence_ref) DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_candidate_observe_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand_candidate
REFERENCING NEW TABLE AS inserted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_insert_batch();

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
      FROM deleted_candidate AS candidate;

    INSERT INTO execution.semantic_pnf_candidate_execution_event
        (demand_id,target_kind,target_id,event_kind,reason_ref)
    SELECT candidate.demand_id,candidate.target_kind,candidate.target_id,
           5,'planner-replan-superseded'
      FROM deleted_candidate AS candidate;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_candidate_observe_delete_batch
AFTER DELETE ON execution.semantic_pnf_demand_candidate
REFERENCING OLD TABLE AS deleted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_delete_batch();

COMMIT;
