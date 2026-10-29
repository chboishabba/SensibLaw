from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/storage/postgres/streaming_spacy_execution.py"


def test_production_parser_projection_defaults_to_direct_packed_fibres() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    signature = source.split("def run_streaming_spacy_execution(", 1)[1].split(
        ") -> PostgresSentenceCarrier:", 1
    )[0]
    assert "projection_mode: str = PRODUCTION_DIRECT" in signature
    worker = source.split("def _worker_drain(", 1)[1].split(
        "def _emit_progress(", 1
    )[0]
    assert "if projection_mode == PRODUCTION_DIRECT:" in worker
    assert "commit_direct_partition(" in worker
    assert "else:\n                        commit_numeric_doc(" in worker


def test_direct_mode_skips_reference_sentence_closure_drain() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    worker = source.split("def _worker_drain(", 1)[1].split(
        "def _emit_progress(", 1
    )[0]
    assert "if projection_mode != PRODUCTION_DIRECT:" in worker
    coordinator = source.split(
        'current_kernel="sentence_closure_coordinator"', 1
    )[1].split('current_kernel="sentence_adjacency"', 1)[0]
    assert "if projection_mode == PRODUCTION_DIRECT:" in coordinator
    assert "remaining_sentence_count = 0" in coordinator


def test_direct_mode_fails_if_parser_observation_rows_exist() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    check = source.split("def _assert_direct_projection_zero(", 1)[1].split(
        "def _refresh_final_numeric_lookup(", 1
    )[0]
    assert "semantic_parser_sentence" in check
    assert "semantic_parser_token" in check
    assert "semantic_parser_entity_span" in check
    assert "counts != (0, 0, 0)" in check
    assert "_assert_direct_projection_zero(" in source


def test_direct_receipt_pins_g1_to_g4_physical_invariants() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '"parser_projection_mode": projection_mode' in source
    assert '"production_parser_token_writes": 0 if projection_mode == PRODUCTION_DIRECT else None' in source
    assert '"sentence_local_database_crossings": 0 if projection_mode == PRODUCTION_DIRECT else None' in source
    assert '"reference_projection_explicit_only": True' in source
