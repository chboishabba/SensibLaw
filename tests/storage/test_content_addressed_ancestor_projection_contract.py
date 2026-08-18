from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/144_content_address_document_ancestor_projection.sql"


def test_exact_parent_relation_guards_recursive_rebuild() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    relation_state = sql.index("parent_relation TEXT NOT NULL")
    equality_guard = sql.index(
        "IF previous_parent_relation = current_parent_relation"
    )
    ancestor_delete = sql.index("DELETE FROM execution.semantic_pnf_interface_ancestor")
    recursive_chain = sql.index("WITH RECURSIVE chain(")

    assert relation_state < equality_guard < ancestor_delete < recursive_chain


def test_parent_relation_covers_interface_and_parent_identity_exactly_in_order() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "interface.interface_id::TEXT || ':'" in sql
    assert "COALESCE(interface.parent_interface_id::TEXT, '-')" in sql
    assert "',' ORDER BY interface.interface_id" in sql
    assert "digest(" not in sql
    assert "parent_relation_sha256" not in sql


def test_projection_state_is_execution_cache_not_semantic_identity() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "DB-local execution cache only" in sql
    assert "never portable semantic identity" in sql
    assert "ON CONFLICT (run_ref, document_ref) DO UPDATE" in sql
