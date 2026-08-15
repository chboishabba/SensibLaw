from __future__ import annotations

from io import StringIO
import json
from time import sleep

import pytest

from src.runtime.document_stage_metrics import stage_measure_declaration
from src.runtime.progress import PhaseRecorder


def test_phase_recorder_emits_durable_timing_and_reuse_events(tmp_path) -> None:
    stream = StringIO()
    recorder = PhaseRecorder(stream=stream, json_lines=True)

    with recorder.phase(
        "compile_pnf", total=2, phase_unit="documents", details={"workers": 2}
    ) as phase:
        sleep(0.001)
        phase.advance(
            subject_ref="document:a",
            reused=True,
            details={"worker": "document-1"},
            processed_tokens=12,
            worker="document-1",
        )
        phase.advance(
            subject_ref="document:b", reused=False, details={"worker": "document-2"}
        )

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
    assert all(row["schema_version"] == "sl.progress_event.v0_5" for row in lines)


def test_failed_phase_records_error_without_hiding_exception() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with pytest.raises(ValueError, match="bad projection"):
        with recorder.phase("project_legal_ir"):
            raise ValueError("bad projection")

    event = recorder.events[-1]
    assert event["state"] == "failed"
    assert event["details"]["error_type"] == "ValueError"
    assert recorder.to_dict()["phase_summary"]["project_legal_ir"]["failed"] == 1


def test_phase_heartbeat_reports_estimate_while_no_units_finish() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase(
        "compile_pnf", total=2, phase_unit="documents", heartbeat_seconds=0.001
    ) as phase:
        phase.advance(subject_ref="document:a")
        sleep(0.003)

    heartbeat = next(
        event for event in recorder.events if event["state"] == "heartbeat"
    )
    assert heartbeat["completed"] == 1
    assert heartbeat["estimated_remaining_ms"] >= 0
    assert "active_stage" not in heartbeat


def test_active_stage_reports_whole_run_estimate() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", total=3, heartbeat_seconds=None) as phase:
        phase.advance(subject_ref="document:a")
        with phase.stage(
            "parser", measures={"tokens": {"completed": 50, "total": 100}}
        ):
            sleep(0.001)
            phase.observe(measures={"tokens": 75})
            event = recorder.events[-1]
            assert event["estimated_run_remaining_ms"] >= 0
            assert event["estimated_run_completion_at"]


def test_outer_heartbeat_reports_active_context_without_inner_stage() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase(
        "postgres_local_compile",
        total=2,
        phase_unit="documents",
        heartbeat_seconds=None,
    ) as phase:
        phase.heartbeat(
            subject_ref="document:active",
            message="active document",
            worker="worker:1",
            details={"relative_path": "active.txt"},
        )

    heartbeat = next(
        event for event in recorder.events if event["state"] == "heartbeat"
    )
    assert heartbeat["completed"] == 0
    assert heartbeat["subject_ref"] == "document:active"
    assert heartbeat["message"] == "active document"
    assert heartbeat["worker"] == "worker:1"
    assert heartbeat["details"]["relative_path"] == "active.txt"
    assert "active_stage" not in heartbeat
    assert "measures" not in heartbeat


def test_direct_inner_observation_without_stage_is_rejected() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", heartbeat_seconds=None) as phase:
        with pytest.raises(
            RuntimeError, match="cannot observe inner work without an active stage"
        ):
            phase.observe(measures={"tokens": 1})


def test_last_completion_label_never_becomes_active_stage() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", total=8, heartbeat_seconds=None) as phase:
        phase.advance(message="coordinate_validation")
        phase.heartbeat()

    heartbeat = next(
        event for event in recorder.events if event["state"] == "heartbeat"
    )
    assert heartbeat["completed"] == 1
    assert "active_stage" not in heartbeat
    assert heartbeat.get("message") != "coordinate_validation"


def test_named_measure_vector_is_independent_of_outer_progress() -> None:
    stream = StringIO()
    recorder = PhaseRecorder(stream=stream, json_lines=False)

    with recorder.phase(
        "postgres_demand_planning_compile",
        total=10,
        phase_unit="documents",
        subject_ref="document:0007",
        heartbeat_seconds=None,
    ) as phase:
        phase.advance(message="reused_document")
        phase.begin_stage(
            "constraint_assessment",
            measures=stage_measure_declaration(
                "constraint_assessment",
                totals={
                    "factors_scanned": 40,
                    "constraints_evaluated": 100,
                    "assessments_emitted": 100,
                },
            ),
        )
        sleep(0.001)
        phase.observe(
            measures={
                "factors_scanned": 20,
                "constraints_evaluated": 25,
                "assessments_emitted": 25,
                "satisfied": 4,
                "violated": 3,
                "undetermined": 18,
            }
        )
        phase.heartbeat()
        phase.complete_stage()

    heartbeat = next(
        row
        for row in recorder.events
        if row.get("state") == "heartbeat"
        and row.get("active_stage") == "constraint_assessment"
    )
    assert heartbeat["completed"] == 1
    assert heartbeat["measures"]["constraints_evaluated"]["total"] == 100
    assert heartbeat["measures"]["constraints_evaluated"]["per_second"] > 0
    assert heartbeat["measures"]["satisfied"]["completed"] == 4
    assert "constraints_evaluated=25/100 constraints" in stream.getvalue()
    assert "active_stage=constraint_assessment" in stream.getvalue()


def test_stage_lifecycle_cannot_overlap_or_leak_at_phase_finish() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    phase_context = recorder.phase("compile_pnf", heartbeat_seconds=None)
    phase = phase_context.__enter__()
    phase.begin_stage("parser_annotation", measures={"tokens": {"unit": "tokens"}})
    with pytest.raises(RuntimeError, match="still active"):
        phase.begin_stage("coordinate_validation")
    with pytest.raises(RuntimeError, match="cannot finish phase"):
        phase_context.__exit__(None, None, None)
    phase.complete_stage()
    phase.finish(state="completed")


def test_stage_completion_may_close_exactly_one_outer_boundary() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", total=8, heartbeat_seconds=None) as phase:
        phase.begin_stage("canonical_normalization")
        phase.complete_stage(advance_outer=True)
        phase.begin_stage("parser_annotation")
        phase.complete_stage(advance_outer=True)

    completed = [
        event for event in recorder.events if event["state"] == "stage_completed"
    ]
    assert [event["completed"] for event in completed] == [1, 2]
    assert all("active_stage" not in event for event in completed)


def test_stage_context_open_observe_and_close() -> None:
    recorder = PhaseRecorder(stream=StringIO(), json_lines=True)
    with recorder.phase("document_compile", total=2, heartbeat_seconds=None) as phase:
        with phase.stage(
            "parser_annotation",
            measures=stage_measure_declaration("parser_annotation"),
        ) as stage:
            stage.observe(
                measures={
                    "fibres": {
                        "completed": 1,
                        "total": 2,
                        "unit": "fibres",
                    },
                    "tokens": {"completed": 11, "unit": "tokens"},
                },
                details={"document_stage": "parser_annotation"},
            )

    states = [event["state"] for event in recorder.events]
    assert states == [
        "started",
        "stage_started",
        "running",
        "stage_completed",
        "completed",
    ]
    assert recorder.events[2]["active_stage"] == "parser_annotation"
    assert recorder.events[2]["measures"]["fibres"]["total"] == 2
    assert recorder.events[3]["completed"] == 1
