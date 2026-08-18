from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/145_sparse_frontier_dirty_closure.sql"
POLICY = ROOT / "src/policy/sparse_root_publication_execution.py"


def test_overlapping_fibres_are_not_canonical_parent_reductions() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "selected_kind IN (2, 4, 9)" in sql
    trigger = sql.split(
        "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers",
        1,
    )[0]
    assert "NEW.region_kind IN (2, 4, 9)" in trigger
    assert "RETURN NEW" in trigger


def test_document_frontier_reduction_is_seeded_only_by_missing_or_stale_receipts() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    reducer = sql.split(
        "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers",
        1,
    )[1]
    assert "semantic_pnf_frontier_dirty" in reducer
    assert "receipt.interface_id IS NULL" in reducer
    assert "receipt.graph_revision IS DISTINCT FROM interface.graph_revision" in reducer
    assert "region.region_kind NOT IN (1, 2, 4, 9)" in reducer


def test_canonical_rebuild_dirties_only_its_parent_interface() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    enqueue = sql.split(
        "CREATE OR REPLACE FUNCTION execution.enqueue_numeric_pnf_parent_frontier",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier(",
        1,
    )[0]
    assert "interface.parent_interface_id" in enqueue
    assert "ON CONFLICT (interface_id) DO UPDATE" in enqueue
    assert "reason_interface_id" in enqueue


def test_sparse_root_policy_reuses_exact_hierarchy_root_count() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "summary.visible_index_rows" in source
    assert "root_rows = _ROOT_VISIBLE_ROWS.pop" in source
    assert "if root_rows is None:" in source
    assert "return canonical_final_refresh(" in source
    assert "return root_rows" in source


def test_sparse_root_policy_has_no_nonroot_lookup_publication() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "refresh_pnf_global_lookup_interfaces" not in source
    assert "semantic_pnf_global_lookup" not in source
    assert "connect(" not in source
