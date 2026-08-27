from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "postgres_migrations"
    / "201_setwise_candidate_transition_projection.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_candidate_observation_uses_statement_transition_tables() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_candidate" in sql
    assert "REFERENCING OLD TABLE AS deleted_candidate" in sql
    assert "FOR EACH ROW" not in sql
    assert sql.count("FOR EACH STATEMENT") >= 6


def test_append_only_candidate_history_is_preserved() -> None:
    sql = _sql()
    assert "INSERT INTO execution.semantic_pnf_demand_candidate_observation" in sql
    assert "INSERT INTO execution.semantic_pnf_candidate_execution_event" in sql
    assert "INSERT INTO execution.semantic_pnf_candidate_evidence" in sql
    assert "DELETE FROM execution.semantic_pnf_candidate_execution_event" not in sql
    assert "DELETE FROM execution.semantic_pnf_demand_candidate_observation" not in sql
    assert "DELETE FROM execution.semantic_pnf_candidate_evidence" not in sql
    assert "TRUNCATE execution.semantic_pnf_candidate" not in sql


def test_current_state_projection_selects_latest_inserted_event_per_key() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_event" in sql
    assert (
        "SELECT DISTINCT ON (event.demand_id, event.target_kind, event.target_id)"
        in sql
    )
    assert "event.event_id DESC" in sql
    assert (
        "execution.semantic_pnf_candidate_current_execution.event_id\n"
        "          < EXCLUDED.event_id"
        in sql
    )


def test_admissibility_and_preference_projections_are_statement_local() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_admissibility" in sql
    assert "REFERENCING NEW TABLE AS inserted_preference" in sql
    assert "preference.preference_id DESC" in sql
    assert (
        "execution.semantic_pnf_candidate_current_preference.preference_id\n"
        "          < EXCLUDED.preference_id"
        in sql
    )


def test_evidence_reverse_dependencies_are_batched_without_authority_change() -> None:
    sql = _sql()
    assert "REFERENCING NEW TABLE AS inserted_evidence" in sql
    assert "INSERT INTO execution.semantic_pnf_reverse_dependency" in sql
    assert "INSERT INTO execution.semantic_pnf_incremental_work_queue" in sql
    assert "SELECT 6," in sql
    assert "SELECT 4," in sql
    assert "SELECT 5," in sql


def test_migration_does_not_redefine_canonical_frontier_reducer() -> None:
    sql = _sql()
    assert "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier" not in sql
    assert "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers" not in sql
    assert "semantic_pnf_demand_candidate AS candidate" not in sql
