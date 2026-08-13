from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT / "database/postgres_migrations/038_typed_spacy_parser_execution.sql"
BYTE_COORDINATES = (
    ROOT / "database/postgres_migrations/039_typed_spacy_byte_coordinates.sql"
)
GRAPH_WORK = (
    ROOT / "database/postgres_migrations/039_typed_spacy_sentence_graph_jobs.sql"
)
CONSTRAINTS = (
    ROOT / "database/postgres_migrations/039_typed_spacy_parser_constraints.sql"
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


def test_parser_partition_order_is_document_scoped() -> None:
    sql = PARSER.read_text(encoding="utf-8")
    assert "UNIQUE (run_ref, document_ref, sequence_no)" in sql
    assert "(run_ref, document_ref, state, sequence_no)" in sql
    assert "UNIQUE (run_ref, sequence_no)" not in sql


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


def test_dependency_heads_are_relationally_enforced() -> None:
    sql = CONSTRAINTS.read_text(encoding="utf-8")
    assert "semantic_parser_token_head_token_ref_fkey" in sql
    assert "REFERENCES execution.semantic_parser_token(token_ref)" in sql
    assert "DEFERRABLE INITIALLY DEFERRED" in sql


def test_boundary_repairs_have_document_scoped_order_and_covering_evidence() -> None:
    sql = CONSTRAINTS.read_text(encoding="utf-8")
    assert "assign_parser_repair_sequence" in sql
    assert "partition.document_ref = NEW.document_ref" in sql
    assert "BEFORE INSERT ON execution.semantic_parser_partition" in sql
    assert "validate_parser_boundary_resolution" in sql
    assert "sentence.start_char <= NEW.suspected_start_char" in sql
    assert "sentence.end_char >= NEW.suspected_end_char" in sql
    assert "BEFORE UPDATE OF state" in sql


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
