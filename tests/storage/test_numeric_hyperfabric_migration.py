from pathlib import Path


MIGRATIONS = (
    Path("database/postgres_migrations/040_numeric_pnf_hyperfabric.sql"),
    Path("database/postgres_migrations/041_numeric_parser_sentence_links.sql"),
    Path(
        "database/postgres_migrations/"
        "042_numeric_parser_sentence_link_trigger.sql"
    ),
)


def _source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)


def test_numeric_hyperfabric_schema_contains_no_json_authority() -> None:
    source = _source().casefold()
    assert " json " not in source
    assert " jsonb" not in source
    assert "::json" not in source
    assert "json_build" not in source


def test_numeric_hyperfabric_schema_declares_compact_ids_and_skip_indexes() -> None:
    source = _source()
    for required in (
        "semantic_symbol",
        "symbol_id BIGINT",
        "kind_id SMALLINT",
        "semantic_morph_set",
        "sentence_id BIGINT",
        "token_id BIGINT",
        "head_token_id BIGINT",
        "semantic_pnf_region",
        "semantic_pnf_region_edge",
        "semantic_pnf_interface",
        "semantic_pnf_interface_ancestor",
        "distance_power SMALLINT",
        "semantic_pnf_interface_typed_ancestor",
        "semantic_pnf_object",
        "semantic_pnf_factor",
        "semantic_pnf_hyperedge",
        "semantic_pnf_demand",
        "semantic_pnf_visible_lookup",
        "semantic_pnf_mdl_profile",
        "semantic_pnf_work_item",
    ):
        assert required in source


def test_numeric_parser_representation_excludes_legacy_text_refs() -> None:
    source = _source()
    assert "representation_version = 2" in source
    for legacy_column in (
        "orth_ref IS NULL",
        "lemma_ref IS NULL",
        "pos_ref IS NULL",
        "tag_ref IS NULL",
        "dependency_ref IS NULL",
    ):
        assert legacy_column in source
    assert "assign_numeric_parser_sentence_id" in source


def test_old_decorative_parser_work_triggers_are_removed() -> None:
    source = MIGRATIONS[0].read_text(encoding="utf-8")
    assert "DROP TRIGGER IF EXISTS semantic_parser_sentence_graph_work" in source
    assert "DROP TRIGGER IF EXISTS semantic_parser_document_graph_work" in source
    assert "enqueue_numeric_sentence_region" in source
