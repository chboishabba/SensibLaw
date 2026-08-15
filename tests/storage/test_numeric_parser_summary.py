from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "src/storage/postgres/numeric_parser_summary.py"
STREAMING = ROOT / "src/storage/postgres/streaming_spacy_execution.py"


def test_numeric_summary_uses_partition_ledger_for_large_cardinalities() -> None:
    source = SUMMARY.read_text(encoding="utf-8")

    assert "sum(partition.sentence_count)" in source
    assert "sum(partition.token_count)" in source
    assert "sum(partition.entity_count)" in source
    assert "count(partition.partition_ref)" in source
    assert "FROM execution.semantic_parser_sentence" not in source
    assert "FROM execution.semantic_parser_token" not in source
    assert "FROM execution.semantic_parser_entity_span" not in source


def test_numeric_summary_counts_deduplicated_boundary_obligations_exactly() -> None:
    source = SUMMARY.read_text(encoding="utf-8")

    assert "FROM execution.semantic_parser_boundary_obligation" in source
    assert "sum(partition.boundary_obligation_count)" not in source


def test_streaming_numeric_path_uses_compact_summary_not_legacy_summary() -> None:
    source = STREAMING.read_text(encoding="utf-8")

    assert (
        "from src.storage.postgres.numeric_parser_summary import numeric_execution_summary"
        in source
    )
    assert "summary = numeric_execution_summary(" in source
    assert "execution_summary," not in source
