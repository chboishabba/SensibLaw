from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/141_defer_parentless_interface_ancestor_refresh.sql"
HIERARCHY = ROOT / "src/storage/postgres/numeric_hierarchy_planner.py"
SENTENCE = ROOT / "src/storage/postgres/numeric_sentence_admission.py"


def test_parent_is_checked_before_ancestor_tables_are_touched() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    parent_lookup = sql.index("SELECT parent_interface_id")
    parentless_return = sql.index("IF parent_id IS NULL")
    ancestor_delete = sql.index("DELETE FROM execution.semantic_pnf_interface_ancestor")
    typed_delete = sql.index("DELETE FROM execution.semantic_pnf_interface_typed_ancestor")

    assert parent_lookup < parentless_return < ancestor_delete < typed_delete


def test_document_hierarchy_retains_authoritative_full_ancestor_rebuild() -> None:
    source = HIERARCHY.read_text(encoding="utf-8")
    assert "SELECT execution.rebuild_pnf_document_ancestors(%s, %s)" in source
    assert "SELECT execution.refresh_pnf_visible_lookup(%s, %s)" in source


def test_sentence_admission_still_calls_compatible_refresh_api() -> None:
    # Migration 141 is intentionally an implementation-compatible physical
    # optimization.  It changes no Python semantic call sites, making rollback
    # and parity testing straightforward.
    source = SENTENCE.read_text(encoding="utf-8")
    assert "SELECT execution.rebuild_pnf_interface_ancestors(%s)" in source
