from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pnf.streaming_fixed_point import ObservationDelta
from src.policy import bounded_operational_execution as bounded
from src.policy import operational_corpus_compilation as operational
from src.runtime.stage_timing import StageTimingLedger


def _delta(document_ref: str = "document:test") -> ObservationDelta:
    observation_ref = "observation:test:0"
    return ObservationDelta(
        document_ref=document_ref,
        batch_ref="batch:test:0",
        scope_ref=f"document-sentence:{document_ref}:0",
        sequence_no=0,
        parser_contract="parser:test:v1",
        observation_refs=(observation_ref,),
        observations=(
            {
                "observation_ref": observation_ref,
                "observation_type": "parser.token",
                "token": {
                    "index": 0,
                    "text": "must",
                    "lemma": "must",
                    "start": 0,
                    "end": 4,
                    "dep": "ROOT",
                    "head_index": 0,
                    "pos": "AUX",
                },
            },
        ),
        token_start=0,
        token_end=1,
        char_start=0,
        char_end=4,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _deltas(document_ref: str, count: int) -> tuple[ObservationDelta, ...]:
    return tuple(
        ObservationDelta(
            document_ref=document_ref,
            batch_ref=f"batch:{sequence_no}",
            scope_ref=f"document-sentence:{document_ref}:{sequence_no}",
            sequence_no=sequence_no,
            parser_contract="parser:test:v1",
            observation_refs=(f"observation:{sequence_no}",),
            observations=(
                {
                    "observation_ref": f"observation:{sequence_no}",
                    "observation_type": "parser.token",
                    "token": {
                        "index": sequence_no,
                        "text": "must",
                        "lemma": "must",
                        "start": sequence_no * 5,
                        "end": sequence_no * 5 + 4,
                        "dep": "ROOT",
                        "head_index": sequence_no,
                        "pos": "AUX",
                    },
                },
            ),
            token_start=sequence_no,
            token_end=sequence_no + 1,
            char_start=sequence_no * 5,
            char_end=sequence_no * 5 + 4,
            token_count=1,
            coverage_barrier="sentence",
            coverage_complete=True,
        )
        for sequence_no in range(count)
    )


def test_policy_package_installs_one_bounded_execution_strategy() -> None:
    assert operational._streaming_semantic_build is (
        bounded.bounded_streaming_semantic_build
    )
    assert operational._serial_streaming_semantic_build is not (
        operational._streaming_semantic_build
    )
    assert bounded.install_bounded_operational_execution() is False


def test_empty_frontier_preserves_fixed_point_artifact_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bounded, "current_process_rss_bytes", lambda: 16 * 1024 * 1024)
    monkeypatch.setattr(
        bounded,
        "current_process_tree_rss_bytes",
        lambda: 16 * 1024 * 1024,
    )
    build, metrics = bounded.bounded_streaming_semantic_build(
        document_ref="document:empty",
        source_ref="source:empty",
        observation_deltas=(),
        base_factors=(),
        timings=StageTimingLedger(document_ref="document:empty"),
        closure_workers=2,
        owner_partitions=2,
    )

    assert build["fixed_point_certificate"]["local_fixed_point"] == "reached"
    assert build["bounded_execution"]["scheduler_receipt"]["bounded_stop"] is False
    assert build["bounded_execution"]["retention_mode"] == "production_compact"
    assert metrics["closure_job_count"] == 0
    assert metrics["materialized_factor_count"] == 0


def test_unrecoverable_pressure_writes_resumable_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "10")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "12")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_RECOVERY_MEMORY_MIB", "8")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_COMPACTION_ATTEMPTS", "1")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_MINIMUM_RECOVERY_MIB", "1")
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setattr(bounded, "current_process_rss_bytes", lambda: 13 * 1024 * 1024)
    monkeypatch.setattr(
        bounded,
        "current_process_tree_rss_bytes",
        lambda: 13 * 1024 * 1024,
    )

    with pytest.raises(bounded.DocumentResourceLimitError) as captured:
        bounded.bounded_streaming_semantic_build(
            document_ref="document:pressure",
            source_ref="source:pressure",
            observation_deltas=(_delta("document:pressure"),),
            base_factors=(),
            timings=StageTimingLedger(document_ref="document:pressure"),
            closure_workers=1,
            owner_partitions=1,
        )

    checkpoint = captured.value.checkpoint
    assert checkpoint["resource_limit_reached"] is True
    assert checkpoint["state"] == "bounded_stop"
    assert checkpoint["checkpoint_retained"] is True
    assert checkpoint["pending_job_refs"]
    assert checkpoint["in_flight_job_refs"] == []

    paths = list(tmp_path.glob("*.resource-checkpoint.json"))
    assert len(paths) == 1
    durable = json.loads(paths[0].read_text(encoding="utf-8"))
    assert durable["state"] == "bounded_stop"
    assert durable["pending_job_refs"] == checkpoint["pending_job_refs"]


def test_frontier_batches_lease_before_all_deltas_are_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_FRONTIER_BATCH_SIZE", "1")
    monkeypatch.setattr(bounded, "current_process_rss_bytes", lambda: 16 * 1024 * 1024)
    monkeypatch.setattr(
        bounded,
        "current_process_tree_rss_bytes",
        lambda: 16 * 1024 * 1024,
    )
    events: list[dict[str, object]] = []
    deltas = _deltas("document:batched", 3)

    build, metrics = bounded.bounded_streaming_semantic_build(
        document_ref="document:batched",
        source_ref="source:batched",
        observation_deltas=deltas,
        base_factors=(),
        timings=StageTimingLedger(document_ref="document:batched"),
        closure_workers=1,
        owner_partitions=1,
        progress_observer=lambda payload: events.append(dict(payload)),
    )

    first_completed = next(
        event for event in events if event.get("jobs_completed", 0) == 1
    )
    assert first_completed["deltas_admitted"] == 1
    assert metrics["closure_job_count"] == len(deltas)
    assert build["bounded_execution"]["scheduler_receipt"]["jobs_completed"] == len(
        deltas
    )
    assert {
        event["current_kernel"] for event in events if "current_kernel" in event
    } >= {
        "observation_delta_admission",
        "ready_frontier_construction",
        "scheduled_job_submission",
        "closure_receipt_reduction",
    }


def test_bounded_frontier_preserves_serial_factor_and_certificate_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_FRONTIER_BATCH_SIZE", "1")
    monkeypatch.setattr(bounded, "current_process_rss_bytes", lambda: 16 * 1024 * 1024)
    monkeypatch.setattr(
        bounded,
        "current_process_tree_rss_bytes",
        lambda: 16 * 1024 * 1024,
    )
    deltas = _deltas("document:parity", 3)
    serial_build, _ = operational._serial_streaming_semantic_build(
        document_ref="document:parity",
        source_ref="source:parity",
        observation_deltas=deltas,
        base_factors=(),
        timings=StageTimingLedger(document_ref="document:parity"),
        closure_workers=1,
        owner_partitions=1,
    )
    bounded_build, _ = bounded.bounded_streaming_semantic_build(
        document_ref="document:parity",
        source_ref="source:parity",
        observation_deltas=deltas,
        base_factors=(),
        timings=StageTimingLedger(document_ref="document:parity"),
        closure_workers=1,
        owner_partitions=1,
    )

    assert (
        bounded_build["materialized_reduction"]
        == serial_build["materialized_reduction"]
    )
    assert (
        bounded_build["fixed_point_certificate"]["local_fixed_point"]
        == serial_build["fixed_point_certificate"]["local_fixed_point"]
        == "reached"
    )
