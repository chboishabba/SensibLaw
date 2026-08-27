BEGIN;

-- Set-wise candidate transition projection ----------------------------------
--
-- The sparse parent reducer already plans one bounded candidate fibre per
-- parent interface.  Migration 086 made every candidate DELETE/INSERT
-- transition proof-relevant at the execution-audit layer, but implemented that
-- observation with row triggers.  Migration 089 then projected every resulting
-- event into the rebuildable current-state tables with more row triggers.
--
-- Preserve exactly the same append-only observation/event/evidence rows and the
-- same current-state projection, but execute each transition statement as one
-- set operation.  Candidate choice, semantic authority, and reducer ordering do
-- not change here.

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
CREATE TRIGGER semantic_pnf_candidate_observe_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand_candidate
REFERENCING NEW TABLE AS inserted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_insert_batch();

DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_delete
    ON execution.semantic_pnf_demand_candidate;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_observe_delete_batch
    ON execution.semantic_pnf_demand_candidate;
CREATE TRIGGER semantic_pnf_candidate_observe_delete_batch
AFTER DELETE ON execution.semantic_pnf_demand_candidate
REFERENCING OLD TABLE AS deleted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_delete_batch();

-- Current execution state is a rebuildable projection of append-only events.
-- A statement may contain more than one event for one candidate key, so choose
-- the greatest event id before the upsert rather than relying on row order.
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
      FROM inserted_event AS event
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

DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution
    ON execution.semantic_pnf_candidate_execution_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution_batch
    ON execution.semantic_pnf_candidate_execution_event;
CREATE TRIGGER semantic_pnf_project_current_execution_batch
AFTER INSERT ON execution.semantic_pnf_candidate_execution_event
REFERENCING NEW TABLE AS inserted_event
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_execution_batch();

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
      FROM inserted_admissibility AS event
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

DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility
    ON execution.semantic_pnf_candidate_admissibility_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility_batch
    ON execution.semantic_pnf_candidate_admissibility_event;
CREATE TRIGGER semantic_pnf_project_current_admissibility_batch
AFTER INSERT ON execution.semantic_pnf_candidate_admissibility_event
REFERENCING NEW TABLE AS inserted_admissibility
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_admissibility_batch();

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

DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference
    ON execution.semantic_pnf_candidate_preference;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference_batch
    ON execution.semantic_pnf_candidate_preference;
CREATE TRIGGER semantic_pnf_project_current_preference_batch
AFTER INSERT ON execution.semantic_pnf_candidate_preference
REFERENCING NEW TABLE AS inserted_preference
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_preference_batch();

-- Evidence reverse-dependency indexing is also pure projection.  Preserve the
-- same four inserts from migration 091, but amortize them over the whole newly
-- inserted evidence relation instead of running four statements per row.
CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind, source_id, demand_id, dependency_kind)
    SELECT 6,
           evidence.evidence_id,
           evidence.demand_id,
           3
      FROM inserted_evidence AS evidence
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind, source_id, demand_id, dependency_kind)
    SELECT 4,
           evidence.source_region_id,
           evidence.demand_id,
           3
      FROM inserted_evidence AS evidence
     WHERE evidence.source_region_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind, source_id, demand_id, dependency_kind)
    SELECT 5,
           evidence.source_interface_id,
           evidence.demand_id,
           3
      FROM inserted_evidence AS evidence
     WHERE evidence.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_incremental_work_queue
        (source_kind, source_id, demand_id, horizon)
    SELECT 6,
           evidence.evidence_id,
           evidence.demand_id,
           evidence.horizon
      FROM inserted_evidence AS evidence
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_reverse_dependency
    ON execution.semantic_pnf_candidate_evidence;
DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_reverse_dependency_batch
    ON execution.semantic_pnf_candidate_evidence;
CREATE TRIGGER semantic_pnf_candidate_evidence_reverse_dependency_batch
AFTER INSERT ON execution.semantic_pnf_candidate_evidence
REFERENCING NEW TABLE AS inserted_evidence
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency_batch();

COMMENT ON FUNCTION execution.observe_numeric_pnf_candidate_insert_batch() IS
    'Execution-only set-wise observation of one candidate INSERT statement; preserves append-only planner membership/event evidence.';
COMMENT ON FUNCTION execution.observe_numeric_pnf_candidate_delete_batch() IS
    'Execution-only set-wise observation of one candidate DELETE statement; preserves append-only planner supersession history.';
COMMENT ON FUNCTION execution.project_numeric_pnf_current_execution_batch() IS
    'Rebuildable set-wise current-state projection from append-only execution events; carries no semantic authority.';

COMMIT;
