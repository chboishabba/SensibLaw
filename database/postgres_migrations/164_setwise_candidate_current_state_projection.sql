BEGIN;

-- 164: rebuildable current-state tables are exact hot projections of append-only
-- event history. Migration 089 maintained them with one row trigger per event.
-- Project each inserted event relation once, selecting the greatest event/
-- preference id per logical current-state cell in case a batch contains more
-- than one update for the same candidate.

DROP TRIGGER IF EXISTS semantic_pnf_project_current_execution
    ON execution.semantic_pnf_candidate_execution_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_admissibility
    ON execution.semantic_pnf_candidate_admissibility_event;
DROP TRIGGER IF EXISTS semantic_pnf_project_current_preference
    ON execution.semantic_pnf_candidate_preference;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_execution_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_execution
        (demand_id,target_kind,target_id,event_id,event_kind,
         active_budget,reason_ref,created_at)
    SELECT DISTINCT ON (event.demand_id,event.target_kind,event.target_id)
           event.demand_id,event.target_kind,event.target_id,
           event.event_id,event.event_kind,event.active_budget,event.reason_ref,
           event.created_at
      FROM inserted_execution_event AS event
     ORDER BY event.demand_id,event.target_kind,event.target_id,event.event_id DESC
    ON CONFLICT(demand_id,target_kind,target_id) DO UPDATE SET
        event_id=EXCLUDED.event_id,
        event_kind=EXCLUDED.event_kind,
        active_budget=EXCLUDED.active_budget,
        reason_ref=EXCLUDED.reason_ref,
        created_at=EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_execution.event_id
          < EXCLUDED.event_id;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_project_current_execution_batch
AFTER INSERT ON execution.semantic_pnf_candidate_execution_event
REFERENCING NEW TABLE AS inserted_execution_event
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_execution_batch();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_admissibility_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_admissibility
        (demand_id,target_kind,target_id,event_id,event_kind,evidence_id,created_at)
    SELECT DISTINCT ON (event.demand_id,event.target_kind,event.target_id)
           event.demand_id,event.target_kind,event.target_id,
           event.event_id,event.event_kind,event.evidence_id,event.created_at
      FROM inserted_admissibility_event AS event
     ORDER BY event.demand_id,event.target_kind,event.target_id,event.event_id DESC
    ON CONFLICT(demand_id,target_kind,target_id) DO UPDATE SET
        event_id=EXCLUDED.event_id,
        event_kind=EXCLUDED.event_kind,
        evidence_id=EXCLUDED.evidence_id,
        created_at=EXCLUDED.created_at
    WHERE execution.semantic_pnf_candidate_current_admissibility.event_id
          < EXCLUDED.event_id;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_project_current_admissibility_batch
AFTER INSERT ON execution.semantic_pnf_candidate_admissibility_event
REFERENCING NEW TABLE AS inserted_admissibility_event
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_admissibility_batch();

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_current_preference_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_candidate_current_preference
        (demand_id,target_kind,target_id,horizon,revision,preferred,margin,
         evidence_count,preference_id)
    SELECT DISTINCT ON (
               preference.demand_id,preference.target_kind,
               preference.target_id,preference.horizon
           )
           preference.demand_id,preference.target_kind,preference.target_id,
           preference.horizon,preference.revision,preference.preferred,
           preference.margin,preference.evidence_count,
           preference.preference_id
      FROM inserted_preference AS preference
     ORDER BY preference.demand_id,preference.target_kind,
              preference.target_id,preference.horizon,
              preference.preference_id DESC
    ON CONFLICT(demand_id,target_kind,target_id,horizon) DO UPDATE SET
        revision=EXCLUDED.revision,
        preferred=EXCLUDED.preferred,
        margin=EXCLUDED.margin,
        evidence_count=EXCLUDED.evidence_count,
        preference_id=EXCLUDED.preference_id
    WHERE execution.semantic_pnf_candidate_current_preference.preference_id
          < EXCLUDED.preference_id;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_project_current_preference_batch
AFTER INSERT ON execution.semantic_pnf_candidate_preference
REFERENCING NEW TABLE AS inserted_preference
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_current_preference_batch();

COMMIT;
