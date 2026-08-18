from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT / "database" / "postgres_migrations"
    / "160_setwise_demand_source_object_anchor.sql"
).read_text(encoding="utf-8")


def test_source_anchor_is_statement_level() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor" in SQL
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert "REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2
    assert "FOR EACH ROW" not in SQL


def test_valid_producer_native_source_object_precedes_lexical_recovery() -> None:
    assert "valid_supplied_object_id" in SQL
    assert "supplied.object_id=demand.source_object_id" in SQL
    assert "supplied.region_id=demand.source_region_id" in SQL
    assert "supplied.active" in SQL
    assert "COALESCE(" in SQL
    assert "demand.valid_supplied_object_id" in SQL


def test_lexical_recovery_remains_ambiguity_safe() -> None:
    assert "count(object.object_id)::BIGINT AS match_count" in SQL
    assert "WHEN lexical_match.match_count=1" in SQL
    assert "THEN lexical_match.matched_object_id" in SQL
    assert "ELSE NULL" in SQL
    assert "object.head_symbol_id=demand.lexical_symbol_id" in SQL
