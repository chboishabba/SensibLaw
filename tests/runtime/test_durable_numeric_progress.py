from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.durable_progress import DurablePhaseRecorder


def test_durable_recorder_persists_stage_and_failure_before_outer_success(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "progress.json"
    recorder = DurablePhaseRecorder(durable_path=ledger)

    with pytest.raises(RuntimeError, match="boom"):
        with recorder.phase("document", total=1, heartbeat_seconds=None) as phase:
            with phase.stage("numeric_pnf_compilation", advance_outer=False):
                phase.heartbeat(
                    message="numeric_hierarchy",
                    details={
                        "current_kernel": "numeric_hierarchy",
                        "kernel_state": "started",
                    },
                )
                assert ledger.exists()
                live = json.loads(ledger.read_text(encoding="utf-8"))
                assert live["events"][-1]["details"]["current_kernel"] == (
                    "numeric_hierarchy"
                )
                raise RuntimeError("boom")

    failed = json.loads(ledger.read_text(encoding="utf-8"))
    assert failed["events"][-1]["state"] == "failed"
    assert any(
        row.get("state") == "stage_completed"
        and row.get("details", {}).get("completed_stage")
        == "numeric_pnf_compilation"
        for row in failed["events"]
    )


def test_durable_recorder_does_not_require_terminal_write(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.json"
    recorder = DurablePhaseRecorder(durable_path=ledger)
    with recorder.phase("document", heartbeat_seconds=None) as phase:
        phase.heartbeat(message="still-running")
        payload = json.loads(ledger.read_text(encoding="utf-8"))
        assert payload["event_count"] >= 2
        assert payload["events"][-1]["message"] == "still-running"
