from __future__ import annotations

import pytest

from src.pnf.streaming_fixed_point import CoverageNotice, ObservationDelta
from src.policy import bounded_operational_execution as bounded
from src.policy.closure_liveness_execution import (
    ClosureLifecycleState,
    ClosureLivenessError,
    LivenessBoundedStreamingSemanticOwner,
)
from src.runtime.stage_timing import StageTimingLedger


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


def test_bounded_compiler_uses_liveness_owner() -> None:
    assert bounded.BoundedStreamingSemanticOwner is LivenessBoundedStreamingSemanticOwner


def test_final_partial_batch_drains_and_certifies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_FRONTIER_BATCH_SIZE", "2")
    monkeypatch.setattr(bounded, "current_process_rss_bytes", lambda: 16 * 1024 * 1024)
    monkeypatch.setattr(
        bounded,
        "current_process_tree_rss_bytes",
        lambda: 16 * 1024 * 1024,
    )
    events: list[dict[str, object]] = []
    document_ref = "document:final-drain"
    deltas = _deltas(document_ref, 5)

    build, metrics = bounded.bounded_streaming_semantic_build(
        document_ref=document_ref,
        source_ref="source:final-drain",
        observation_deltas=deltas,
        base_factors=(),
        timings=StageTimingLedger(document_ref=document_ref),
        closure_workers=2,
        owner_partitions=2,
        progress_observer=lambda payload: events.append(dict(payload)),
    )

    lifecycle = build["closure_lifecycle"]
    assert lifecycle["state"] == ClosureLifecycleState.COMPLETED.value
    assert lifecycle["producer_exhausted"] is True
    assert lifecycle["blocking_counts"] == {
        "pending_jobs": 0,
        "in_flight_jobs": 0,
        "dirty_groups": 0,
        "boundary_obligations": 0,
        "open_required_coverage_barriers": 0,
    }
    assert lifecycle["materialization_count"] == 1
    assert metrics["closure_job_count"] == len(deltas)
    assert build["bounded_execution"]["scheduler_receipt"]["jobs_completed"] == len(
        deltas
    )
    assert [row["state"] for row in lifecycle["events"]][-2:] == [
        ClosureLifecycleState.CERTIFYING.value,
        ClosureLifecycleState.COMPLETED.value,
    ]
    assert any(event.get("jobs_completed") == len(deltas) for event in events)


def test_exhausted_frontier_with_hidden_obligation_fails_finitely() -> None:
    document_ref = "document:hidden-obligation"
    owner = LivenessBoundedStreamingSemanticOwner(
        document_ref=document_ref,
        partition_count=1,
    )
    owner.add_boundary_obligations(("boundary:still-open",))
    owner.admit_coverage_notice(
        CoverageNotice(
            document_ref=document_ref,
            scope_ref="document-global",
            barrier="document",
            state="complete",
            evidence_refs=("evidence:test",),
        )
    )

    with pytest.raises(ClosureLivenessError) as captured:
        owner.fixed_point_certificate()

    diagnostic = captured.value.diagnostic
    assert diagnostic["state"] == ClosureLifecycleState.FAILED.value
    assert diagnostic["producer_exhausted"] is True
    assert diagnostic["blocking_counts"]["boundary_obligations"] == 1
    assert diagnostic["blocking_counts"]["pending_jobs"] == 0
    assert diagnostic["blocking_counts"]["in_flight_jobs"] == 0
