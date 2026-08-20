from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database/postgres_migrations/174_operation_aware_pnf_work_claim_index.sql"
)
STORE = ROOT / "src/storage/postgres/numeric_hyperfabric_store.py"


def test_work_claim_query_is_operation_scoped() -> None:
    source = STORE.read_text(encoding="utf-8")
    claim = source.split("def claim_work(", 1)[1].split("def _load_sentence_tokens", 1)[0]

    assert "run_ref = %s" in claim
    assert "operation_id = %s" in claim
    assert "state_id = %s" in claim
    assert "ORDER BY priority, work_id" in claim
    assert "FOR UPDATE SKIP LOCKED" in claim


def test_ready_index_matches_work_claim_prefix_and_order() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "semantic_pnf_work_operation_ready_idx" in sql
    assert "(run_ref, operation_id, state_id, priority, work_id)" in sql
    assert "WHERE state_id IN (1, 2)" in sql
    assert "DROP INDEX" not in sql


def test_index_change_does_not_modify_work_or_semantic_state() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    body = sql.upper()

    assert "CREATE INDEX IF NOT EXISTS" in body
    assert "UPDATE EXECUTION.SEMANTIC_PNF_WORK_ITEM" not in body
    assert "INSERT INTO EXECUTION.SEMANTIC_PNF_WORK_ITEM" not in body
    assert "DELETE FROM EXECUTION.SEMANTIC_PNF_WORK_ITEM" not in body
