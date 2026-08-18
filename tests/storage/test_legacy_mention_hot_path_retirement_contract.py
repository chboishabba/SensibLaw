from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def _text(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_legacy_mention_and_recurrence_triggers_are_retired() -> None:
    sql = _text("157_retire_legacy_mention_derivation_hot_path.sql")

    assert "DROP TRIGGER IF EXISTS semantic_pnf_sentence_mention_derivation" in sql
    assert "DROP TRIGGER IF EXISTS semantic_pnf_region_recurrence_derivation" in sql
    assert "derive_numeric_sentence_mentions()" in sql
    assert "derive_numeric_region_recurrence()" in sql
    assert "CREATE TRIGGER semantic_pnf_sentence_mention_derivation" not in sql
    assert "CREATE TRIGGER semantic_pnf_region_recurrence_derivation" not in sql


def test_live_anaphor_residue_is_statement_level_and_numeric() -> None:
    sql = _text("157_retire_legacy_mention_derivation_hot_path.sql")

    assert "semantic_pnf_anaphor_projection_constant" in sql
    assert "ensure_semantic_symbol(3::SMALLINT,'PRON')" in sql
    assert "ensure_semantic_symbol(14::SMALLINT,'mention.pronoun')" in sql
    assert "ensure_semantic_symbol(13::SMALLINT,'anaphor_unresolved')" in sql

    assert "REFERENCING OLD TABLE AS prior_region NEW TABLE AS updated_region" in sql
    assert "FOR EACH STATEMENT" in sql
    assert "FOR candidate IN" not in sql
    assert "FOR EACH ROW" not in sql

    # Ordinary projection compares only numeric parser ids. Surface spelling is
    # retained as provenance but never copied into lexical identity constraints.
    assert "token.pos_symbol_id=constant.pronoun_pos_symbol_id" in sql
    assert "surface_lexical_symbol_id" in sql
    assert "NULL,source.lemma_symbol_id,NULL" in sql
    assert "source_object_id" in sql


def test_recurrence_projection_has_no_new_hot_path_replacement() -> None:
    sql = _text("157_retire_legacy_mention_derivation_hot_path.sql")

    assert "semantic_pnf_recurrence_group" not in sql
    assert "semantic_pnf_recurrence_member" not in sql
    assert "project_numeric_sentence_anaphors_setwise" in sql
