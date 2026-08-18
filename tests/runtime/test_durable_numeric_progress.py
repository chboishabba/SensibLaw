from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.durable_progress import DurablePhaseRecorder


def _events(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_durable_recorder_persists_stage_and_failure_before_outer_success(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "progress.jsonl"
    recorder = DurablePhaseRecorder(durable_path=journal)

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
                assert journal.exists()
                live = _events(journal)
                assert live[-1]["details"]["current_kernel"] == "numeric_hierarchy"
                raise RuntimeError("boom")

    failed = _events(journal)
    assert failed[-1]["state"] == "failed"
    assert any(
        row.get("state") == "stage_completed"
        and row.get("details", {}).get("completed_stage")
        == "numeric_pnf_compilation"
        for row in failed
    )


def test_durable_recorder_appends_one_record_per_event(tmp_path: Path) -> None:
    journal = tmp_path / "progress.jsonl"
    recorder = DurablePhaseRecorder(durable_path=journal)
    with recorder.phase("document", heartbeat_seconds=None) as phase:
        phase.heartbeat(message="still-running")
        first = _events(journal)
        assert len(first) == 2
        assert first[-1]["message"] == "still-running"
        phase.heartbeat(message="still-running-again")
        second = _events(journal)
        assert len(second) == 3
        assert second[-1]["message"] == "still-running-again"
