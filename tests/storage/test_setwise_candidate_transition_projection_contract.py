from pathlib import Path


MIGRATION = Path("database/postgres_migrations/207_setwise_candidate_transition_projection.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_candidate_observers_use_transition_tables_not_row_triggers() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_candidate" in sql
    assert "REFERENCING OLD TABLE AS deleted_candidate" in sql
    assert "FOR EACH STATEMENT" in sql
    assert "FOR EACH ROW EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_insert" not in sql
    assert "FOR EACH ROW EXECUTE FUNCTION execution.observe_numeric_pnf_candidate_delete" not in sql


def test_candidate_history_semantics_are_preserved_setwise() -> None:
    sql = _sql()
    assert "semantic_pnf_demand_candidate_observation" in sql
    assert "semantic_pnf_candidate_execution_event" in sql
    assert "'planner-active'" in sql
    assert "'planner-replan-superseded'" in sql
    assert "semantic_pnf_candidate_evidence" in sql
    assert "ON CONFLICT (demand_id, target_kind, target_id, evidence_ref) DO NOTHING" in sql


def test_current_state_projection_is_statement_setwise_and_latest_wins() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_execution_event" in sql
    assert "REFERENCING NEW TABLE AS inserted_admissibility_event" in sql
    assert "REFERENCING NEW TABLE AS inserted_preference" in sql
    assert "DISTINCT ON (event.demand_id, event.target_kind, event.target_id)" in sql
    assert "event.event_id DESC" in sql
    assert "< EXCLUDED.event_id" in sql
    assert "< EXCLUDED.preference_id" in sql


def test_migration_does_not_redefine_candidate_planning_semantics() -> None:
    sql = _sql()
    assert "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids" not in sql
    assert "DELETE FROM execution.semantic_pnf_demand_candidate" not in sql
