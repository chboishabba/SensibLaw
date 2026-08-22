from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "168_setwise_anaphor_surface_normalization.sql"
).read_text(encoding="utf-8")


def _normalizer_function_sql() -> str:
    start = SQL.index(
        "CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_surface()"
    )
    end = SQL.index("$$;", start) + len("$$;")
    return SQL[start:end]


def test_anaphor_surface_normalization_is_acyclic_before_row() -> None:
    assert "BEFORE INSERT ON execution.semantic_pnf_demand" in SQL
    assert (
        "BEFORE UPDATE OF residual_type_symbol_id, lexical_symbol_id\n"
        "ON execution.semantic_pnf_demand"
    ) in SQL
    assert SQL.count("FOR EACH ROW") == 2
    assert "FOR EACH STATEMENT" not in SQL
    assert "REFERENCING NEW TABLE" not in SQL
    assert "REFERENCING OLD TABLE" not in SQL

    normalizer = _normalizer_function_sql()
    assert "NEW.surface_lexical_symbol_id := COALESCE" in normalizer
    assert "NEW.lexical_symbol_id := NULL" in normalizer
    assert "UPDATE execution.semantic_pnf_demand" not in normalizer
    assert "RETURN NEW" in normalizer


def test_surface_spelling_is_preserved_but_identity_key_is_cleared() -> None:
    assert "surface_lexical_symbol_id=COALESCE" in SQL
    assert "lexical_symbol_id=NULL" in SQL
    assert "anaphor_residual_type_symbol_id" in SQL


def test_derived_export_and_lookup_identity_keys_are_repaired() -> None:
    assert "UPDATE execution.semantic_pnf_interface_export" in SQL
    assert "SET key_symbol_id=NULL" in SQL
    assert "DELETE FROM execution.semantic_pnf_interface_lookup" in SQL
    assert "lookup.key_kind=3" in SQL


def test_old_statement_self_update_triggers_are_retired() -> None:
    for trigger_name in (
        "zzz_semantic_pnf_anaphor_surface_insert_batch",
        "zzz_semantic_pnf_anaphor_surface_update_batch",
    ):
        assert f"DROP TRIGGER IF EXISTS {trigger_name}" in SQL
        assert f"CREATE TRIGGER {trigger_name}" not in SQL


def test_update_normalizer_only_runs_for_relevant_coordinate_changes() -> None:
    assert (
        "NEW.residual_type_symbol_id IS DISTINCT FROM OLD.residual_type_symbol_id"
        in SQL
    )
    assert "NEW.lexical_symbol_id IS DISTINCT FROM OLD.lexical_symbol_id" in SQL
