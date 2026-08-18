from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT / "database" / "postgres_migrations"
    / "161_anaphor_surface_kind_not_referent_kind.sql"
).read_text(encoding="utf-8")


def test_anaphor_kind_normalization_is_statement_level() -> None:
    assert "REFERENCING NEW TABLE AS inserted_demand" in SQL
    assert "REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2
    assert "FOR EACH ROW" not in SQL


def test_only_accidental_pronoun_referent_constraint_is_removed() -> None:
    assert "anaphor_residual_type_symbol_id" in SQL
    assert "pronoun_object_kind_symbol_id" in SQL
    assert "SET expected_object_kind_symbol_id=NULL" in SQL
    assert "infer person" in SQL


def test_historical_rows_are_repaired_without_global_anaphor_retyping() -> None:
    assert "Repair historical migration-045 rows" in SQL
    assert "demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id" in SQL
    assert "demand.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id" in SQL
