from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFER = ROOT / "database/postgres_migrations/196_defer_sparse_frontier_on_hierarchy_build.sql"
AFFECTED = ROOT / "database/postgres_migrations/197_affected_document_frontier_reduction.sql"


def test_hierarchy_build_defers_sparse_frontier_close_trigger() -> None:
    sql = DEFER.read_text(encoding="utf-8")
    guard = "current_setting('sensiblaw.defer_frontier_rebuild', true)"
    reducer = "execution.rebuild_numeric_pnf_parent_frontier"

    assert guard in sql
    assert "= 'on'" in sql
    assert sql.index(guard) < sql.index(reducer)
    assert "RETURN NEW" in sql


def test_ordinary_close_path_keeps_canonical_parent_reducer() -> None:
    sql = DEFER.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close" in sql
    assert "execution.rebuild_numeric_pnf_parent_frontier" in sql
    assert "NEW.closure_state NOT IN (2, 3)" in sql


def test_document_frontier_uses_receipts_as_dirty_key_witnesses() -> None:
    sql = AFFECTED.read_text(encoding="utf-8")

    for required in (
        "semantic_pnf_frontier_reduction_receipt",
        "receipt.reduced_at IS NULL",
        "receipt_graph_revision IS DISTINCT FROM",
        "child_region.closed_at > candidate.reduced_at",
        "child_receipt.reduced_at > candidate.reduced_at",
        "WITH RECURSIVE eligible AS",
        "affected(interface_id) AS",
        "parent.interface_id = child.parent_interface_id",
    ):
        assert required in sql


def test_affected_frontier_remains_bottom_up_and_uses_existing_reducer() -> None:
    sql = AFFECTED.read_text(encoding="utf-8")

    assert "ORDER BY candidate.region_kind" in sql
    assert "candidate.end_char - candidate.start_char" in sql
    assert "execution.rebuild_numeric_pnf_parent_frontier" in sql
    assert "semantic_pnf_interface_export" not in sql
    assert "semantic_pnf_interface_lookup" not in sql


def test_coordinator_does_not_make_parent_pointer_change_a_semantic_dirty_seed() -> None:
    sql = AFFECTED.read_text(encoding="utf-8")
    dirty_block = sql.split("dirty AS (", 1)[1].split("affected(interface_id) AS", 1)[0]

    assert "parent_interface_id IS DISTINCT FROM" not in dirty_block
    assert "parent_interface_id <>" not in dirty_block
