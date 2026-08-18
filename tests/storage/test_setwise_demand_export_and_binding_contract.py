from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "170_setwise_demand_export_and_binding.sql"
).read_text(encoding="utf-8")


def test_legacy_demand_and_interface_row_triggers_are_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_export" in SQL
    assert "DROP TRIGGER IF EXISTS semantic_pnf_interface_demand_binding" in SQL
    assert "FOR EACH ROW" not in SQL
    assert SQL.count("FOR EACH STATEMENT") == 3


def test_inserted_demands_publish_exports_and_both_lookup_families() -> None:
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert "semantic_pnf_interface_export" in SQL
    assert "SELECT demand.source_interface_id,5,3,demand.demand_id" in SQL
    assert "SELECT demand.source_interface_id,5,demand.residual_type_symbol_id" in SQL
    assert "SELECT demand.source_interface_id,3,demand.lexical_symbol_id" in SQL


def test_update_publication_matches_legacy_source_interface_boundary() -> None:
    assert "source_interface_id\n                   IS DISTINCT FROM prior.source_interface_id" in SQL
    assert "specialized demand projections own lexical/type changes" in SQL


def test_interface_batch_binds_unbound_region_demands() -> None:
    assert "REFERENCING NEW TABLE AS inserted_interface" in SQL
    assert "demand.source_region_id=interface.region_id" in SQL
    assert "demand.source_interface_id IS NULL" in SQL
