from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT / "database" / "postgres_migrations"
    / "161_anaphor_surface_kind_not_referent_kind.sql"
).read_text(encoding="utf-8")


def _normalizer_function_sql() -> str:
    start = SQL.index(
        "CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind()"
    )
    end = SQL.index("$$;", start) + len("$$;")
    return SQL[start:end]


def test_anaphor_kind_normalization_is_before_row_not_recursive_after_update() -> None:
    assert "BEFORE INSERT ON execution.semantic_pnf_demand" in SQL
    assert (
        "BEFORE UPDATE OF residual_type_symbol_id, expected_object_kind_symbol_id\n"
        "ON execution.semantic_pnf_demand"
    ) in SQL
    assert SQL.count("FOR EACH ROW") == 2
    assert "FOR EACH STATEMENT" not in SQL
    assert "REFERENCING NEW TABLE" not in SQL
    assert "REFERENCING OLD TABLE" not in SQL

    normalizer = _normalizer_function_sql()
    assert "NEW.expected_object_kind_symbol_id := NULL" in normalizer
    assert "UPDATE execution.semantic_pnf_demand" not in normalizer
    assert "RETURN NEW" in normalizer


def test_update_normalizer_only_runs_when_relevant_coordinates_change() -> None:
    assert (
        "NEW.residual_type_symbol_id IS DISTINCT FROM OLD.residual_type_symbol_id"
        in SQL
    )
    assert (
        "NEW.expected_object_kind_symbol_id\n"
        "             IS DISTINCT FROM OLD.expected_object_kind_symbol_id"
    ) in SQL
    assert "NEW.expected_object_kind_symbol_id IS NOT NULL" in SQL


def test_only_accidental_pronoun_referent_constraint_is_removed() -> None:
    assert "anaphor_residual_type_symbol_id" in SQL
    assert "pronoun_object_kind_symbol_id" in SQL
    assert "NEW.expected_object_kind_symbol_id := NULL" in SQL
    assert "infer person" in SQL


def test_historical_rows_are_repaired_without_global_anaphor_retyping() -> None:
    assert "Repair historical migration-045 rows" in SQL
    assert (
        "demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id"
        in SQL
    )
    assert (
        "demand.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id"
        in SQL
    )
    assert "SET expected_object_kind_symbol_id=NULL" in SQL


def test_migration_drops_old_after_self_update_trigger_spellings() -> None:
    for trigger_name in (
        "semantic_pnf_anaphor_referent_kind_insert",
        "semantic_pnf_zz_anaphor_referent_kind_insert",
        "semantic_pnf_anaphor_referent_kind_update",
        "semantic_pnf_zz_anaphor_referent_kind_update",
    ):
        assert f"DROP TRIGGER IF EXISTS {trigger_name}" in SQL
