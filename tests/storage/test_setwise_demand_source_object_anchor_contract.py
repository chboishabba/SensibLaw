from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "160_setwise_demand_source_object_anchor.sql"
).read_text(encoding="utf-8")


def _update_normalizer_sql() -> str:
    start = SQL.index(
        "CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_demand_source_object()"
    )
    end = SQL.index("$$;", start) + len("$$;")
    return SQL[start:end]


def test_source_anchor_keeps_setwise_insert_but_dependency_gates_updates() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_source_object_anchor" in SQL
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 1

    assert (
        "BEFORE UPDATE OF source_region_id, lexical_symbol_id, source_object_id\n"
        "ON execution.semantic_pnf_demand"
    ) in SQL
    assert SQL.count("FOR EACH ROW") == 1
    assert "REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand" not in SQL
    assert "project_numeric_pnf_demand_source_objects_updated" not in SQL


def test_update_source_anchor_normalizes_new_without_self_updating_demand() -> None:
    normalizer = _update_normalizer_sql()
    assert "NEW.source_object_id := resolved_object_id" in normalizer
    assert "RETURN NEW" in normalizer
    assert "UPDATE execution.semantic_pnf_demand" not in normalizer


def test_update_source_anchor_only_runs_for_actual_source_coordinate_changes() -> None:
    assert "NEW.source_region_id IS DISTINCT FROM OLD.source_region_id" in SQL
    assert "NEW.lexical_symbol_id IS DISTINCT FROM OLD.lexical_symbol_id" in SQL
    assert "NEW.source_object_id IS DISTINCT FROM OLD.source_object_id" in SQL


def test_valid_producer_native_source_object_precedes_lexical_recovery() -> None:
    assert "valid_supplied_object_id" in SQL
    assert "supplied.object_id=demand.source_object_id" in SQL
    assert "supplied.region_id=demand.source_region_id" in SQL
    assert "supplied.active" in SQL
    assert "COALESCE(" in SQL
    assert "demand.valid_supplied_object_id" in SQL

    normalizer = _update_normalizer_sql()
    supplied_lookup = normalizer.index("NEW.source_object_id IS NOT NULL")
    lexical_lookup = normalizer.index(
        "resolved_object_id IS NULL AND NEW.lexical_symbol_id IS NOT NULL"
    )
    assert supplied_lookup < lexical_lookup


def test_lexical_recovery_remains_ambiguity_safe() -> None:
    assert "count(object.object_id)::BIGINT AS match_count" in SQL
    assert "WHEN lexical_match.match_count=1" in SQL
    assert "THEN lexical_match.matched_object_id" in SQL
    assert "ELSE NULL" in SQL
    assert "object.head_symbol_id=demand.lexical_symbol_id" in SQL

    normalizer = _update_normalizer_sql()
    assert "SELECT count(object.object_id)::BIGINT" in normalizer
    assert "IF lexical_match_count=1 THEN" in normalizer
    assert "resolved_object_id := lexical_matched_object_id" in normalizer
