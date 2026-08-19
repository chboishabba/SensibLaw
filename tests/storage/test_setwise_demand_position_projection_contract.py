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
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 1
    assert SQL.count("FOR EACH ROW") == 1
    assert (
        "BEFORE UPDATE OF source_region_id, source_start_char\n"
        "ON execution.semantic_pnf_demand"
    ) in SQL
    assert "project_numeric_pnf_updated_demand_positions" not in SQL


def test_only_null_positions_use_region_end_fallback() -> None:
    assert "SET source_start_char=region.end_char" in SQL
    assert "inserted.source_start_char IS NULL" in SQL
    assert "demand.source_start_char IS NULL" in SQL
    assert "IF NEW.source_start_char IS NULL THEN" in SQL
    assert "INTO NEW.source_start_char" in SQL


def test_update_normalizer_is_change_scoped_and_acyclic() -> None:
    assert "NEW.source_region_id IS DISTINCT FROM OLD.source_region_id" in SQL
    assert "NEW.source_start_char IS DISTINCT FROM OLD.source_start_char" in SQL

    start = SQL.index(
        "CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_demand_position()"
    )
    end = SQL.index("$$;", start) + len("$$;")
    normalizer = SQL[start:end]
    assert "UPDATE execution.semantic_pnf_demand" not in normalizer
    assert "RETURN NEW" in normalizer


def test_upgrade_backfills_null_compatibility_positions() -> None:
    assert "Upgrade parity" in SQL
    assert "region.region_id=demand.source_region_id" in SQL
