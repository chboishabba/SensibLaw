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
            worker="document-1",
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
    assert payload["events"][1]["worker"] == "document-1"

    output = tmp_path / "phase_ledger.json"
    recorder.write_json(output)
    persisted = json.loads(output.read_text())
    assert persisted == payload

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines[0]["state"] == "started"
    assert lines[-1]["state"] == "completed"
    assert all(row["schema_version"] == "sl.progress_event.v0_3" for row in lines)


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


def test_inner_stage_throughput_is_independent_of_outer_document_progress() -> None:
    stream = StringIO()
    recorder = PhaseRecorder(stream=stream, json_lines=False)

    with recorder.phase(
        "postgres_demand_planning_compile",
        total=10,
        subject_ref="document:0007",
        heartbeat_seconds=None,
    ) as phase:
        phase.advance(message="documents", details={"document_stage": "document_start"})
        phase.begin_stage(
            "constraint_assessments",
            work_total=100,
            work_unit="assessments",
            details={"factor_count": 40},
        )
        sleep(0.001)
        phase.observe(
            work_completed=25,
            details={"accepted": 4, "rejected": 21},
        )

    event = next(
        row
        for row in recorder.events
        if row.get("message") == "constraint_assessments"
        and row.get("work_completed") == 25
    )
    assert event["completed"] == 1
    assert event["work_total"] == 100
    assert event["work_unit"] == "assessments"
    assert event["work_units_per_second"] > 0
    assert event["work_estimated_remaining_ms"] >= 0
    assert event["details"]["factor_count"] == 40
    assert event["details"]["accepted"] == 4
    assert "work=25/100 assessments" in stream.getvalue()
    assert "constraint_assessments" in stream.getvalue()


def test_heartbeat_preserves_current_inner_stage_and_rate() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("compile_pnf", heartbeat_seconds=None) as phase:
        phase.begin_stage(
            "closure_executor_evaluation",
            work_total=8,
            work_unit="jobs",
        )
        sleep(0.001)
        phase.observe(work_completed=3)
        phase.heartbeat()

    heartbeat = next(event for event in recorder.events if event["state"] == "heartbeat")
    assert heartbeat["message"] == "closure_executor_evaluation"
    assert heartbeat["work_completed"] == 3
    assert heartbeat["work_total"] == 8
    assert heartbeat["work_units_per_second"] > 0
    assert heartbeat["details"]["heartbeat"] is True
