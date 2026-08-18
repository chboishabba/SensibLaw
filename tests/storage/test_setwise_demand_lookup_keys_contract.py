from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT / "database" / "postgres_migrations" / "159_setwise_demand_lookup_keys.sql"
).read_text(encoding="utf-8")


def test_lookup_key_projection_uses_transition_tables() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_lookup_keys" in SQL
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert "REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2
    assert "FOR EACH ROW" not in SQL


def test_all_live_lookup_key_families_are_preserved() -> None:
    for projection in (
        "expected_factor_type_symbol_id",
        "expected_object_kind_symbol_id",
        "lexical_symbol_id",
        "residual_type_symbol_id",
    ):
        assert projection in SQL

    for key_kind in ("1::SMALLINT", "2::SMALLINT", "3::SMALLINT", "5::SMALLINT"):
        assert key_kind in SQL


def test_update_rebuild_is_limited_to_changed_demands() -> None:
    assert "WITH changed AS MATERIALIZED" in SQL
    assert "DELETE FROM execution.semantic_pnf_demand_lookup_key" in SQL
    assert "IS DISTINCT FROM" in SQL
    assert "ON CONFLICT DO NOTHING" in SQL
