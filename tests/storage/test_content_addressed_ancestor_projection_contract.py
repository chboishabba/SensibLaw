from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/144_content_address_document_ancestor_projection.sql"


def test_parent_relation_fingerprint_guards_recursive_rebuild() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    fingerprint = sql.index("parent_relation_sha256")
    equality_guard = sql.index("IF previous_parent_digest = current_parent_digest")
    ancestor_delete = sql.index("DELETE FROM execution.semantic_pnf_interface_ancestor")
    recursive_chain = sql.index("WITH RECURSIVE chain(")

    assert fingerprint < equality_guard < ancestor_delete < recursive_chain


def test_fingerprint_covers_interface_identity_and_parent_identity_in_order() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "interface.interface_id::TEXT || ':'" in sql
    assert "COALESCE(interface.parent_interface_id::TEXT, '-')" in sql
    assert "',' ORDER BY interface.interface_id" in sql
    assert "digest(" in sql
    assert "'sha256'" in sql


def test_projection_state_is_execution_freshness_not_semantic_receipt() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "execution freshness key" in sql
    assert "semantic receipts never consume it" in sql
    assert "ON CONFLICT (run_ref, document_ref) DO UPDATE" in sql
