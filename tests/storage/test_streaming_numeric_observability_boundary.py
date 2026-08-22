from __future__ import annotations

from pathlib import Path

from src.runtime.numeric_observability import numeric_authority_counts_enabled


ROOT = Path(__file__).resolve().parents[2]
STREAMING = ROOT / "src/storage/postgres/streaming_spacy_execution.py"


def test_streamed_hyperfabric_counts_are_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_AUTHORITY_COUNTS", raising=False)
    assert not numeric_authority_counts_enabled()


def test_streamed_hyperfabric_counts_are_explicitly_gated() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    tail = source.split("summary = execution_summary(", 1)[1]
    assert '"pnf_diagnostic_counts_measured": False' in tail
    assert "if numeric_authority_counts_enabled():" in tail
    assert "counts = hyperfabric_counts(" in tail
    assert '"pnf_diagnostic_counts_measured": True' in tail


def test_numeric_parser_receipt_keeps_existing_non_scan_execution_metrics() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    tail = source.split("parser_receipt: dict[str, Any] = {", 1)[1]
    for marker in (
        '"sentence_count": summary.sentence_count',
        '"token_count": summary.token_count',
        '"pnf_document_interface_id": hierarchy.document_interface_id',
        '"pnf_segmentation_evaluations": hierarchy.segmentation_evaluations',
        '"pnf_visible_index_rows": final_lookup_rows',
    ):
        assert marker in tail


def test_parser_and_post_parser_work_timings_are_explicit_not_wall_inferred() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    worker = source.split("def _worker_drain(", 1)[1].split("def _emit_progress", 1)[0]
    assert "parser_started = monotonic_ns()" in worker
    assert "doc, partition = next(iterator)" in worker
    assert "parser_work_ns += parser_elapsed_ns" in worker
    assert "post_parser_work_ns += monotonic_ns() - post_started" in worker

    receipt = source.split("parser_receipt: dict[str, Any] = {", 1)[1]
    assert '"spacy_parser_work_ns": parser_work_ns' in receipt
    assert '"post_parser_worker_work_ns": post_parser_worker_work_ns' in receipt
    assert '"post_parser_coordinator_ns": coordinator_post_parser_ns' in receipt
    assert '"post_parser_work_ns": post_parser_worker_work_ns' in receipt
    assert '"timing_basis": "aggregate-process-active-work:v1"' in receipt
