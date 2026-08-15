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
