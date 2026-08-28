BEGIN;

-- C3c: set-wise candidate transition projection ------------------------------
--
-- Preserve the existing append-only candidate observation / execution-event /
-- evidence semantics from migration 086, but stop paying one PL/pgSQL trigger
-- invocation per candidate row and one more trigger invocation per event row.
-- PostgreSQL transition tables let one statement project the complete relation
-- delta in set-wise form.  Current-state tables remain rebuildable projections;
-- event/observation history remains the authority.

CREATE OR REPLACE FUNCTION execution.observe_numeric_pnf_candidate_insert_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_candidate_observation
        (demand_id, target_kind, target_id, observation_kind,
         planning_ordinal, source_interface_id, ancestor_distance,
         index_rank, candidate_score)
    SELECT candidate.demand_id,
           candidate.target_kind,
           candidate.target_id,
           1,
           candidate.ordinal,
           candidate.source_interface_id,
           candidate.ancestor_distance,
           candidate.index_rank,
           candidate.candidate_score
      FROM inserted_candidate AS candidate;

    INSERT INTO execution.semantic_pnf_candidate_execution_event
        (demand_id, target_kind, target_id, event_kind, reason_ref)
    SELECT candidate.demand_id,
           candidate.target_kind,
           candidate.target_id,
           1,
           'planner-active'
      FROM inserted_candidate AS candidate;

    INSERT INTO execution.semantic_pnf_candidate_evidence
        (demand_id, target_kind, target_id, evidence_ref,
         evidence_family, horizon, signed_residual, evidence_kind,
         provenance_ref, source_interface_id)
    SELECT candidate.demand_id,
           candidate.target_kind,
           candidate.target_id,
           'planner-membership:' || candidate.target_kind::TEXT || ':'
               || candidate.target_id::TEXT,
           1,
           3,
           0,
           'candidate_generation',
           'semantic_pnf_demand_candidate',
           candidate.source_interface_id
      FROM inserted_candidate AS candidate
    ON CONFLICT (demand_id, target_kind, target_id, evidence_ref) DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.observe_numeric_pnf_candidate_delete_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_candidate_observation
        (demand_id, target_kind, target_id, observation_kind,
         planning_ordinal, source_interface_id, ancestor_distance,
         index_rank, candidate_score)
    SELECT candidate.demand_id,
           candidate.target_kind,
           candidate.target_id,
           2,
           candidate.ordinal,
           candidate.source_interface_id,
           candidate.ancestor_distance,
           candidate.index_rank,
           candidate.candidate_score
      FROM deleted_candidate AS candidate;

    INSERT INTO execution.semantic_pnf_candidate_execution_event
        (demand_id, target_kind, target_id, event_kind, reason_ref)
    SELECT candidate.demand_id,
           candidate.target_kind,
           candidate.target_id,
           5,
           'planner-replan-superseded'
      FROM deleted_candidate AS candidate;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_insert
    ON execution.semantic_pnf_demand_candidate;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_insert_batch
    ON execution.semantic_pnf_demand_candidate;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_delete
    ON execution.semantic_pnf_demand_candidate;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_delete_batch
    ON execution.semantic_pnf_demand_candidate;

CREATE TRIGGER semantic_pnf_candidate_observe_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand_candidate
REFERENCING NEW TABLE AS inserted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_insert_batch();

CREATE TRIGGER semantic_pnf_candidate_observe_delete_batch
AFTER DELETE ON execution.semantic_pnf_demand_candidate
REFERENCING OLD TABLE AS deleted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_delete_batch();

-- Latest execution state: one set-wise upsert per event-producing statement.
CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_execution_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_execution
        (demand_id, target_kind, target_id, event_id, event_kind,
         active_budget, reason_ref, created_at)
    SELECT DISTINCT ON (event.demand_id, event.target_kind, event.target_id)
           event.demand_id,
           event.target_kind,
           event.target_id,
           event.event_id,
           event.event_kind,
           event.active_budget,
           event.reason_ref,
           event.created_at
      FROM inserted_execution_event AS event
     ORDER BY event.demand_id,
              event.target_kind,
              event.target_id,
              event.event_id DESC
    ON CONFLICT (demand_id, target_kind, target_id) DO UPDATE SET
        event_id = EXCLUDED.event_id,
        event_kind = EXCLUDED.event_kind,
        active_budget = EXCLUDED.active_budget,
        reason_ref = EXCLUDED.reason_ref,
        created_at = EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_execution.event_id
          < EXCLUDED.event_id;

    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_admissibility_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_admissibility
        (demand_id, target_kind, target_id, event_id, event_kind,
         evidence_id, created_at)
    SELECT DISTINCT ON (event.demand_id, event.target_kind, event.target_id)
           event.demand_id,
           event.target_kind,
           event.target_id,
           event.event_id,
           event.event_kind,
           event.evidence_id,
           event.created_at
      FROM inserted_admissibility_event AS event
     ORDER BY event.demand_id,
              event.target_kind,
              event.target_id,
              event.event_id DESC
    ON CONFLICT (demand_id, target_kind, target_id) DO UPDATE SET
        event_id = EXCLUDED.event_id,
        event_kind = EXCLUDED.event_kind,
        evidence_id = EXCLUDED.evidence_id,
        created_at = EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_admissibility.event_id
          < EXCLUDED.event_id;

    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_preference_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_preference
        (demand_id, target_kind, target_id, horizon, revision,
         preferred, margin, evidence_count, preference_id)
    SELECT DISTINCT ON (
               preference.demand_id,
               preference.target_kind,
               preference.target_id,
               preference.horizon
           )
           preference.demand_id,
           preference.target_kind,
           preference.target_id,
           preference.horizon,
           preference.revision,
           preference.preferred,
           preference.margin,
           preference.evidence_count,
           preference.preference_id
      FROM inserted_preference AS preference
     ORDER BY preference.demand_id,
              preference.target_kind,
              preference.target_id,
              preference.horizon,
              preference.preference_id DESC
    ON CONFLICT (demand_id, target_kind, target_id, horizon) DO UPDATE SET
        revision = EXCLUDED.revision,
        preferred = EXCLUDED.preferred,
        margin = EXCLUDED.margin,
        evidence_count = EXCLUDED.evidence_count,
        preference_id = EXCLUDED.preference_id
    WHERE execution.semantic_pnf_candidate_current_preference.preference_id
          < EXCLUDED.preference_id;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution
    ON execution.semantic_pnf_candidate_execution_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution_batch
    ON execution.semantic_pnf_candidate_execution_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility
    ON execution.semantic_pnf_candidate_admissibility_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility_batch
    ON execution.semantic_pnf_candidate_admissibility_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference
    ON execution.semantic_pnf_candidate_preference;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference_batch
    ON execution.semantic_pnf_candidate_preference;

CREATE TRIGGER semantic_pnf_project_current_execution_batch
AFTER INSERT ON execution.semantic_pnf_candidate_execution_event
REFERENCING NEW TABLE AS inserted_execution_event
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_execution_batch();

CREATE TRIGGER semantic_pnf_project_current_admissibility_batch
AFTER INSERT ON execution.semantic_pnf_candidate_admissibility_event
REFERENCING NEW TABLE AS inserted_admissibility_event
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_admissibility_batch();

CREATE TRIGGER semantic_pnf_project_current_preference_batch
AFTER INSERT ON execution.semantic_pnf_candidate_preference
REFERENCING NEW TABLE AS inserted_preference
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_preference_batch();

COMMIT;
