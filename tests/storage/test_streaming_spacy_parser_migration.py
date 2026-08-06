from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT / "database/postgres_migrations/038_typed_spacy_parser_execution.sql"
BYTE_COORDINATES = (
    ROOT / "database/postgres_migrations/039_typed_spacy_byte_coordinates.sql"
)
GRAPH_WORK = (
    ROOT / "database/postgres_migrations/039_typed_spacy_sentence_graph_jobs.sql"
)


def test_parser_authority_is_fully_typed() -> None:
    sql = PARSER.read_text(encoding="utf-8")
    expected = (
        "semantic_parser_source",
        "semantic_parser_partition",
        "semantic_parser_attempt",
        "semantic_parser_symbol",
        "semantic_parser_sentence",
        "semantic_parser_token",
        "semantic_parser_token_morphology",
        "semantic_parser_entity_span",
        "semantic_parser_boundary_obligation",
        "semantic_parser_artifact",
        "semantic_parser_partition_receipt",
        "semantic_parser_document_coverage",
        "semantic_parser_outbox",
    )
    for table in expected:
        assert "execution." + table in sql
    lowered = sql.casefold()
    assert " json " not in lowered
    assert " jsonb " not in lowered
    assert "payload" not in lowered


def test_parser_partitions_record_char_and_byte_coordinates() -> None:
    sql = BYTE_COORDINATES.read_text(encoding="utf-8")
    for column in (
        "char_count",
        "owner_start_byte",
        "owner_end_byte",
        "context_start_byte",
        "context_end_byte",
    ):
        assert column in sql
    assert "semantic_parser_source_run_document_idx" in sql


def test_sentence_work_is_immediate_but_document_work_is_coverage_gated() -> None:
    sql = GRAPH_WORK.read_text(encoding="utf-8")
    assert "AFTER INSERT ON execution.semantic_parser_sentence" in sql
    assert "'mention_licensing'" in sql
    assert "'operator_composition'" in sql
    assert "'dependency_projection'" in sql
    assert "AFTER UPDATE OF state ON execution.semantic_parser_document_coverage" in sql
    assert "NEW.state <> 'complete'" in sql
    assert "'document_closure'" in sql
    assert "parser_coverage_required" in sql
