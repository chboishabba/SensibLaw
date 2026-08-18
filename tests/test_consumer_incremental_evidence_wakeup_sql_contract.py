from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M139 = ROOT / "database/postgres_migrations/139_consumer_incremental_evidence_wakeup.sql"


def _sql() -> str:
    return M139.read_text(encoding="utf-8")


def test_evidence_insert_wakes_registered_consumer_dependencies_only() -> None:
    sql = _sql()
    assert "semantic_pnf_consumer_reverse_dependency" in sql
    assert "semantic_pnf_consumer_horizon_work_queue" in sql
    assert "dependency.source_kind=changed_source.source_kind" in sql
    assert "dependency.source_id=changed_source.source_id" in sql
    assert "SELECT DISTINCT" in sql
    assert "minimum_horizon" in sql


def test_wakeup_uses_numeric_evidence_region_and_interface_coordinates() -> None:
    sql = _sql()
    assert "(6::SMALLINT,NEW.evidence_id)" in sql
    assert "(4::SMALLINT,NEW.source_region_id)" in sql
    assert "(5::SMALLINT,NEW.source_interface_id)" in sql
    assert "symbol_text" not in sql
    assert "regexp" not in sql.casefold()
    assert " LIKE " not in sql.upper()


def test_wakeup_reopens_execution_projection_without_semantic_refutation() -> None:
    sql = _sql()
    assert "work_state=1" in sql
    assert "completed_at=NULL" in sql
    assert "semantic_pnf_candidate_admissibility" not in sql
    assert "semantic_pnf_frontier_resolution" not in sql
    assert "signed_residual" not in sql


def test_wakeup_is_automatic_on_new_evidence() -> None:
    sql = _sql()
    assert "AFTER INSERT ON execution.semantic_pnf_candidate_evidence" in sql
    assert "wake_numeric_pnf_consumers_on_evidence_insert" in sql
