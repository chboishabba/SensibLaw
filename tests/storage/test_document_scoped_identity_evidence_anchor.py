from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/081_document_scoped_identity_evidence_anchor.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_anchor_scope_is_pushed_down_before_window_partition() -> None:
    source = _source()
    doc_token = source.index("doc_token AS MATERIALIZED")
    run_filter = source.index("token.run_ref = selected_run_ref", doc_token)
    document_filter = source.index(
        "token.document_ref = selected_document_ref", doc_token
    )
    window = source.index("OVER (PARTITION BY token.token_id)")
    assert doc_token < run_filter < window
    assert doc_token < document_filter < window


def test_document_anchor_is_materialized_once_and_shared_by_all_lanes() -> None:
    source = _source()
    assert source.count("doc_anchor AS MATERIALIZED") == 1
    assert "appos_evidence AS" in source
    assert "proper_name_evidence AS" in source
    assert "alias_evidence AS" in source
    assert "UNION ALL\n        SELECT * FROM proper_name_evidence" in source
    assert "UNION ALL\n        SELECT * FROM alias_evidence" in source


def test_refresh_never_joins_global_unparameterized_anchor_view() -> None:
    source = _source()
    assert "semantic_pnf_parser_object_anchor" not in source
    assert "semantic_pnf_global_lookup" not in source


def test_related_document_carriers_are_scoped_before_evidence_generation() -> None:
    source = _source()
    assert "doc_sentence AS MATERIALIZED" in source
    assert "doc_person_entity AS MATERIALIZED" in source
    assert "doc_region AS MATERIALIZED" in source
    assert "region.run_id = selected_run_id" in source
    assert "region.document_id = selected_document_id" in source
    assert "entity.run_ref = selected_run_ref" in source
    assert "entity.document_ref = selected_document_ref" in source


def test_name_ambiguity_count_is_bounded_to_schema_limit() -> None:
    source = _source()
    assert "LEAST(256, count(DISTINCT parser_entity_id))::SMALLINT" in source


def test_no_json_similarity_or_proximity_authority_is_introduced() -> None:
    folded = _source().casefold()
    assert "jsonb" not in folded
    assert "::json" not in folded
    assert "similarity(" not in folded
    assert "paragraph" not in folded
