from __future__ import annotations

from pathlib import Path


def test_semantic_execution_outbox_is_database_enforced() -> None:
    migration = Path(
        "database/postgres_migrations/027_semantic_execution_outbox_triggers.sql"
    ).read_text(encoding="utf-8")

    assert "AFTER INSERT ON execution.semantic_delta_admission" in migration
    assert "semantic.delta.admitted.v1" in migration
    assert "AFTER UPDATE OF state ON execution.semantic_publication" in migration
    assert "semantic.publication.committed.v1" in migration
    assert migration.count("ON CONFLICT (event_ref) DO NOTHING") == 2
