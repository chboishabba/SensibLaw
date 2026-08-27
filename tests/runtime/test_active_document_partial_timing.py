import json
from pathlib import Path

from src.runtime.active_document_resources import ActiveDocumentResourceGuard


def test_resource_guard_appends_timeout_surviving_partial_timing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_ALL", "1")
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "8192")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "16384")

    guard = ActiveDocumentResourceGuard(document_ref="document:test")
    first = guard.checkpoint(
        stage="parser_annotation",
        current_kernel="parser_fibre_execution",
        active_batch_size=100,
        persisted_counts={"tokens": 1000},
    )
    second = guard.checkpoint(
        stage="parser_annotation",
        current_kernel="parser_fibre_execution",
        active_batch_size=100,
        persisted_counts={"tokens": 2000},
    )

    assert first["partial_timing"]["acceptance_eligible"] is False
    assert first["partial_timing"]["semantic_authority_effect"] == "none"
    assert second["partial_timing"]["sample_ordinal"] == 2
    assert (
        second["partial_timing"]["observed_monotonic_ns"]
        >= first["partial_timing"]["observed_monotonic_ns"]
    )

    path = tmp_path / "document_test.partial-timing.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[-1]["persisted_counts"]["tokens"] == 2000
    assert rows[-1]["partial_timing"]["partial_run_evidence"] is True
