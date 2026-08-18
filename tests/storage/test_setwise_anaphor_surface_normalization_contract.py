from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "168_setwise_anaphor_surface_normalization.sql"
).read_text(encoding="utf-8")


def test_legacy_anaphor_row_trigger_is_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_anaphor_surface_normalisation" in SQL
    assert "FOR EACH ROW" not in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2


def test_surface_spelling_is_preserved_but_identity_key_is_cleared() -> None:
    assert "surface_lexical_symbol_id=COALESCE" in SQL
    assert "lexical_symbol_id=NULL" in SQL
    assert "anaphor_residual_type_symbol_id" in SQL


def test_derived_export_and_lookup_identity_keys_are_repaired() -> None:
    assert "UPDATE execution.semantic_pnf_interface_export" in SQL
    assert "SET key_symbol_id=NULL" in SQL
    assert "DELETE FROM execution.semantic_pnf_interface_lookup" in SQL
    assert "lookup.key_kind=3" in SQL


def test_normalization_runs_after_ordinary_statement_projections() -> None:
    assert "CREATE TRIGGER zzz_semantic_pnf_anaphor_surface_insert_batch" in SQL
    assert "CREATE TRIGGER zzz_semantic_pnf_anaphor_surface_update_batch" in SQL
    assert "corrective UPDATE" in SQL
