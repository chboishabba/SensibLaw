from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_candidate_lifecycle_is_projected_by_statement() -> None:
    sql = _sql("162_setwise_candidate_lifecycle_projection.sql")

    assert "REFERENCING NEW TABLE AS inserted_candidate" in sql
    assert "REFERENCING OLD TABLE AS deleted_candidate" in sql
    assert sql.count("FOR EACH STATEMENT") == 2
    assert "FOR EACH ROW" not in sql
    for relation in (
        "semantic_pnf_demand_candidate_observation",
        "semantic_pnf_candidate_execution_event",
        "semantic_pnf_candidate_evidence",
    ):
        assert relation in sql


def test_evidence_reverse_dependency_and_wakeup_are_setwise() -> None:
    sql = _sql("163_setwise_evidence_reverse_dependency_wakeup.sql")

    assert "REFERENCING NEW TABLE AS inserted_evidence" in sql
    assert "FOR EACH STATEMENT" in sql
    assert "FOR EACH ROW" not in sql
    assert "SELECT 6,evidence.evidence_id,evidence.demand_id,3" in sql
    assert "SELECT 4,evidence.source_region_id,evidence.demand_id,3" in sql
    assert "SELECT 5,evidence.source_interface_id,evidence.demand_id,3" in sql
    assert "semantic_pnf_incremental_work_queue" in sql


def test_current_state_projection_selects_latest_per_batch_cell() -> None:
    sql = _sql("164_setwise_candidate_current_state_projection.sql")

    assert sql.count("FOR EACH STATEMENT") == 3
    assert "FOR EACH ROW" not in sql
    assert "event.event_id DESC" in sql
    assert "preference.preference_id DESC" in sql
    assert "semantic_pnf_candidate_current_execution.event_id" in sql
    assert "semantic_pnf_candidate_current_admissibility.event_id" in sql
    assert "semantic_pnf_candidate_current_preference.preference_id" in sql
