from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/143_defer_open_document_interface_ancestors.sql"
TRIGGER_MIGRATION = ROOT / "database/postgres_migrations/043_numeric_pnf_ancestor_refresh.sql"
ADJACENCY_MIGRATION = ROOT / "database/postgres_migrations/056_numeric_pnf_adjacent_executor.sql"


def test_targeted_ancestor_build_waits_for_closed_document() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    closed_probe = sql.index("document_region.closure_state = 3")
    open_return = sql.index("IF NOT document_is_closed")
    ancestor_delete = sql.index("DELETE FROM execution.semantic_pnf_interface_ancestor")

    assert closed_probe < open_return < ancestor_delete


def test_document_close_remains_authoritative_full_projection_boundary() -> None:
    sql = TRIGGER_MIGRATION.read_text(encoding="utf-8")

    assert "NEW.region_kind = 10" in sql
    assert "NEW.closure_state = 3" in sql
    assert "PERFORM execution.rebuild_pnf_document_ancestors" in sql


def test_post_document_adjacent_interfaces_retain_targeted_refresh() -> None:
    sql = ADJACENCY_MIGRATION.read_text(encoding="utf-8")

    assert "PERFORM execution.rebuild_pnf_interface_ancestors(selected_pair_interface_id)" in sql
