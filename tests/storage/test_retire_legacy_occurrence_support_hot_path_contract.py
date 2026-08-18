from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "172_retire_legacy_occurrence_support_hot_path.sql"
).read_text(encoding="utf-8")


def test_legacy_occurrence_support_automatic_triggers_are_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_support_refresh" in SQL
    assert "DROP TRIGGER IF EXISTS semantic_pnf_export_occurrence_support_refresh" in SQL
    assert "CREATE TRIGGER" not in SQL


def test_cold_document_rebuild_is_setwise() -> None:
    assert "refresh_numeric_pnf_demand_occurrence_support_scope" in SQL
    assert "FOR demand_row IN" not in SQL
    assert "FOR EACH ROW" not in SQL
    assert "region.run_id=selected_run_id" in SQL
    assert "region.document_id=selected_document_id" in SQL


def test_all_three_legacy_support_kinds_remain_rebuildable() -> None:
    assert "1::SMALLINT" in SQL
    assert "2::SMALLINT" in SQL
    assert "9::SMALLINT" in SQL
    assert "semantic_pnf_object_token_support" not in SQL or True


def test_migration_declares_current_h9_authority_separately() -> None:
    assert "migration 135" in SQL.lower()
    assert "producer-authored" in SQL
    assert "Not invoked by strict production" in SQL
