from pathlib import Path

from tools.audit_pg_migration_runtime import audit_migrations


ROOT = Path(__file__).resolve().parents[2]


def test_composed_postgres_chain_has_no_runtime_owner_collision() -> None:
    report = audit_migrations(
        (ROOT / "database" / "postgres_migrations").glob("*.sql")
    )

    assert report["fatal"] == []
