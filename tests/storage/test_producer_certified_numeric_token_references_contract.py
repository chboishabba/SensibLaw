from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "src" / "policy" / "numeric_parser_projection_hot_path.py"
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "176_producer_certified_numeric_token_references.sql"
)


NUMERIC_SYMBOL_FKS = (
    "semantic_parser_token_orth_symbol_id_fkey",
    "semantic_parser_token_lemma_symbol_id_fkey",
    "semantic_parser_token_pos_symbol_id_fkey",
    "semantic_parser_token_tag_symbol_id_fkey",
    "semantic_parser_token_dependency_symbol_id_fkey",
)
ORIGIN_FKS = (
    "semantic_parser_token_lemma_origin_id_fkey",
    "semantic_parser_token_pos_origin_id_fkey",
    "semantic_parser_token_tag_origin_id_fkey",
    "semantic_parser_token_dependency_origin_id_fkey",
)


def test_migration_176_replaces_only_measured_numeric_symbol_and_origin_fks() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for constraint in (*NUMERIC_SYMBOL_FKS, *ORIGIN_FKS):
        assert f"DROP CONSTRAINT IF EXISTS {constraint}" in source

    for retained in (
        "semantic_parser_token_sentence_ref_fkey",
        "semantic_parser_token_partition_ref_fkey",
        "semantic_parser_token_run_ref_fkey",
        "semantic_parser_token_morph_set_id_fkey",
        "semantic_parser_token_head_token_id_fkey",
        "semantic_parser_token_orth_ref_fkey",
    ):
        assert f"DROP CONSTRAINT IF EXISTS {retained}" not in source


def test_generic_writers_keep_setwise_authority_validation() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "validate_numeric_parser_reference_set_insert" in source
    assert "validate_numeric_parser_reference_set_update" in source
    assert "REFERENCING NEW TABLE AS inserted_token" in source
    assert "REFERENCING NEW TABLE AS updated_token" in source
    assert "LEFT JOIN execution.semantic_symbol AS authority" in source
    assert "LEFT JOIN execution.semantic_parser_annotation_origin AS authority" in source
    assert "ERRCODE = '23503'" in source


def test_setwise_validation_preserves_fk_key_share_concurrency_semantics() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")

    assert migration.count("FOR KEY SHARE OF authority") == 4
    assert policy.count("FOR KEY SHARE") >= 2


def test_reverse_restrict_semantics_are_preserved_on_authority_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "restrict_numeric_parser_symbol_authority_change" in source
    assert "BEFORE DELETE ON execution.semantic_symbol" in source
    assert "BEFORE UPDATE OF symbol_id ON execution.semantic_symbol" in source
    assert "restrict_numeric_parser_origin_authority_change" in source
    assert "BEFORE DELETE ON execution.semantic_parser_annotation_origin" in source
    assert (
        "BEFORE UPDATE OF origin_id ON execution.semantic_parser_annotation_origin"
        in source
    )
    assert source.count("IF TG_OP = 'UPDATE' THEN\n        RETURN NEW;") == 2


def test_strict_producer_certifies_bounded_reference_sets_before_capability() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "numeric_parser_producer_certified_references_ready" in source
    assert "_producer_certify_numeric_references" in source
    assert "SELECT symbol_id" in source
    assert "SELECT origin_id" in source
    assert "observed_symbols != requested_symbols" in source
    assert "observed_origins != requested_origins" in source
    assert "sensiblaw.producer_certified_numeric_references" in source


def test_producer_capability_is_scoped_to_exactly_the_token_insert() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "_set_producer_reference_capability(cursor, True)" in source
    assert "_set_producer_reference_capability(cursor, False)" in source
    assert source.index("_set_producer_reference_capability(cursor, True)") < source.index(
        "result = original_copy_rows("
    )
    assert source.index("result = original_copy_rows(") < source.index(
        "_set_producer_reference_capability(cursor, False)"
    )


def test_transition_table_update_validation_does_not_use_illegal_update_of_shape() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "AFTER UPDATE ON execution.semantic_parser_token" in source
    assert "REFERENCING NEW TABLE AS updated_token" in source
    assert "AFTER UPDATE OF" not in source
