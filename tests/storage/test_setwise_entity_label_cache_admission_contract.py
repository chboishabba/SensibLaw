from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "166_setwise_entity_label_cache_admission.sql"
).read_text(encoding="utf-8")


def test_legacy_row_trigger_is_retired() -> None:
    assert "DROP TRIGGER IF EXISTS semantic_pnf_identity_admission_refresh_label_cache" in SQL
    assert "FOR EACH ROW" not in SQL
    assert SQL.count("FOR EACH STATEMENT") == 2


def test_insert_and_update_use_transition_tables() -> None:
    assert "REFERENCING NEW TABLE AS inserted_admission" in SQL
    assert (
        "REFERENCING OLD TABLE AS prior_admission NEW TABLE AS updated_admission"
        in SQL
    )
    assert "admission_state IS DISTINCT FROM prior.admission_state" in SQL


def test_cache_projection_is_cell_local_and_rebuildable() -> None:
    assert "SELECT DISTINCT" in SQL
    assert "object.head_symbol_id AS label_symbol_id" in SQL
    assert "witness.target_entity_id AS canonical_entity_id" in SQL
    assert "witness.authority_class" in SQL
    assert "admission.admission_state=2" in SQL
    assert "count(admission.witness_id)" in SQL
    assert "max(admission.witness_id)" in SQL


def test_zero_support_deletes_and_positive_support_upserts() -> None:
    assert "support.admitted_support_count=0" in SQL
    assert "support.admitted_support_count>0" in SQL
    assert "ON CONFLICT(label_symbol_id,canonical_entity_id,authority_class) DO UPDATE" in SQL
