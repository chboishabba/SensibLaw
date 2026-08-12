BEGIN;

-- Runtime history is append-only in ordinary operation.  Document/run retraction
-- may still delete rows through FK cascades; what is forbidden is rewriting the
-- meaning of an existing evidence/execution/admissibility event in place.
CREATE OR REPLACE FUNCTION execution.reject_numeric_pnf_runtime_history_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; write a corrective event instead', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_append_only
    ON execution.semantic_pnf_candidate_evidence;
CREATE TRIGGER semantic_pnf_candidate_evidence_append_only
BEFORE UPDATE ON execution.semantic_pnf_candidate_evidence
FOR EACH ROW EXECUTE FUNCTION execution.reject_numeric_pnf_runtime_history_update();

DROP TRIGGER IF EXISTS semantic_pnf_candidate_execution_append_only
    ON execution.semantic_pnf_candidate_execution_event;
CREATE TRIGGER semantic_pnf_candidate_execution_append_only
BEFORE UPDATE ON execution.semantic_pnf_candidate_execution_event
FOR EACH ROW EXECUTE FUNCTION execution.reject_numeric_pnf_runtime_history_update();

DROP TRIGGER IF EXISTS semantic_pnf_candidate_admissibility_append_only
    ON execution.semantic_pnf_candidate_admissibility_event;
CREATE TRIGGER semantic_pnf_candidate_admissibility_append_only
BEFORE UPDATE ON execution.semantic_pnf_candidate_admissibility_event
FOR EACH ROW EXECUTE FUNCTION execution.reject_numeric_pnf_runtime_history_update();

DROP TRIGGER IF EXISTS semantic_pnf_candidate_preference_append_only
    ON execution.semantic_pnf_candidate_preference;
CREATE TRIGGER semantic_pnf_candidate_preference_append_only
BEFORE UPDATE ON execution.semantic_pnf_candidate_preference
FOR EACH ROW EXECUTE FUNCTION execution.reject_numeric_pnf_runtime_history_update();

DROP TRIGGER IF EXISTS semantic_pnf_candidate_observation_append_only
    ON execution.semantic_pnf_demand_candidate_observation;
CREATE TRIGGER semantic_pnf_candidate_observation_append_only
BEFORE UPDATE ON execution.semantic_pnf_demand_candidate_observation
FOR EACH ROW EXECUTE FUNCTION execution.reject_numeric_pnf_runtime_history_update();

-- Reopening Q -> P is independent of whether the latest planner pass still has
-- a row in its ephemeral frontier.  The durable execution event is the active
-- carrier authority; current_planner_member remains visible for diagnostics.
CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_state_v1 AS
SELECT universe.demand_id,
       universe.target_kind,
       universe.target_id,
       TRUE AS represented_possible,
       COALESCE(execution_state.event_kind IN (1, 3), FALSE) AS active,
       COALESCE(execution_state.event_kind IN (2, 4, 5), FALSE)
           AS execution_residual,
       current_candidate.demand_id IS NOT NULL AS current_planner_member,
       COALESCE(admissibility.event_kind = 1, FALSE) AS refuted,
       NOT COALESCE(admissibility.event_kind = 1, FALSE) AS admissible,
       execution_state.reason_ref AS execution_reason_ref,
       admissibility.evidence_id AS admissibility_evidence_id
  FROM execution.semantic_pnf_candidate_universe AS universe
  LEFT JOIN execution.semantic_pnf_demand_candidate AS current_candidate
    ON current_candidate.demand_id = universe.demand_id
   AND current_candidate.target_kind = universe.target_kind
   AND current_candidate.target_id = universe.target_id
  LEFT JOIN execution.semantic_pnf_candidate_latest_execution AS execution_state
    ON execution_state.demand_id = universe.demand_id
   AND execution_state.target_kind = universe.target_kind
   AND execution_state.target_id = universe.target_id
  LEFT JOIN execution.semantic_pnf_candidate_latest_admissibility AS admissibility
    ON admissibility.demand_id = universe.demand_id
   AND admissibility.target_kind = universe.target_kind
   AND admissibility.target_id = universe.target_id;

-- One consumer-facing assessment surface: the candidate fibre is invariant;
-- changing H3 -> H6 -> H9 only changes cumulative evidence/preference columns.
CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_horizon_state_v1 AS
SELECT evidence.demand_id,
       evidence.target_kind,
       evidence.target_id,
       evidence.horizon,
       state.represented_possible,
       state.active,
       state.execution_residual,
       state.current_planner_member,
       state.refuted,
       state.admissible,
       evidence.signed_residual,
       evidence.phase,
       evidence.evidence_count,
       COALESCE(preference.preferred, FALSE) AS preferred,
       preference.margin AS preference_margin,
       preference.evidence_count AS preference_evidence_count
  FROM execution.semantic_pnf_candidate_evidence_horizon_v1 AS evidence
  JOIN execution.semantic_pnf_candidate_state_v1 AS state
    ON state.demand_id = evidence.demand_id
   AND state.target_kind = evidence.target_kind
   AND state.target_id = evidence.target_id
  LEFT JOIN execution.semantic_pnf_candidate_latest_preference AS preference
    ON preference.demand_id = evidence.demand_id
   AND preference.target_kind = evidence.target_kind
   AND preference.target_id = evidence.target_id
   AND preference.horizon = evidence.horizon;

COMMIT;
