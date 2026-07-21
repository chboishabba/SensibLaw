from __future__ import annotations

from io import StringIO
import json
from time import sleep

from src.runtime.progress import PhaseRecorder


def test_phase_recorder_emits_durable_timing_and_reuse_events(tmp_path) -> None:
    stream = StringIO()
    recorder = PhaseRecorder(stream=stream, json_lines=True)

    with recorder.phase("compile_pnf", total=2, details={"workers": 2}) as phase:
        sleep(0.001)
        phase.advance(
            subject_ref="document:a",
            reused=True,
            details={"worker": "document-1"},
            processed_tokens=12,
        )
        phase.advance(subject_ref="document:b", reused=False, details={"worker": "document-2"})

    payload = recorder.to_dict()
    assert payload["schema_version"] == "sl.phase_ledger.v0_1"
    assert payload["event_count"] == 4
    assert payload["phase_summary"]["compile_pnf"]["failed"] == 0
    assert payload["events"][-1]["elapsed_ms"] >= 0
    assert payload["events"][-1]["details"]["reused_units"] == 1
    assert payload["events"][1]["throughput_units_per_second"] > 0
    assert payload["events"][1]["estimated_remaining_ms"] >= 0
    assert payload["events"][1]["estimated_completion_at"]
    assert payload["events"][1]["processed_tokens"] == 12
    assert payload["events"][1]["tokens_per_second"] > 0

    output = tmp_path / "phase_ledger.json"
    recorder.write_json(output)
    persisted = json.loads(output.read_text())
    assert persisted == payload

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines[0]["state"] == "started"
    assert lines[-1]["state"] == "completed"
    assert all(row["schema_version"] == "sl.progress_event.v0_2" for row in lines)


def test_failed_phase_records_error_without_hiding_exception() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    try:
        with recorder.phase("project_legal_ir"):
            raise ValueError("bad projection")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")

    event = recorder.events[-1]
    assert event["state"] == "failed"
    assert event["details"]["error_type"] == "ValueError"
    assert recorder.to_dict()["phase_summary"]["project_legal_ir"]["failed"] == 1


def test_phase_heartbeat_reports_estimate_while_no_units_finish() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("compile_pnf", total=2, heartbeat_seconds=0.001) as phase:
        phase.advance(subject_ref="document:a")
        sleep(0.003)

    heartbeat = next(event for event in recorder.events if event["state"] == "heartbeat")
    assert heartbeat["completed"] == 1
    assert heartbeat["estimated_remaining_ms"] >= 0
