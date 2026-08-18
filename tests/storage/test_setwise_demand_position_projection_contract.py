from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "169_setwise_demand_position_projection.sql"
).read_text(encoding="utf-8")


def test_legacy_position_row_trigger_is_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_position" in SQL
    assert "FOR EACH ROW" not in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2


def test_only_null_positions_use_region_end_fallback() -> None:
    assert "SET source_start_char=region.end_char" in SQL
    assert "inserted.source_start_char IS NULL" in SQL
    assert "changed.source_start_char IS NULL" in SQL
    assert "demand.source_start_char IS NULL" in SQL


def test_update_projection_is_change_scoped() -> None:
    assert "source_region_id IS DISTINCT FROM prior.source_region_id" in SQL
    assert "source_start_char IS DISTINCT FROM prior.source_start_char" in SQL


def test_upgrade_backfills_null_compatibility_positions() -> None:
    assert "Upgrade parity" in SQL
    assert "region.region_id=demand.source_region_id" in SQL
