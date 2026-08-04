from __future__ import annotations

from pathlib import Path

import pytest

from src.pnf.streaming_fixed_point import CoverageNotice, ObservationDelta
from src.policy import bounded_operational_execution as bounded
from src.policy.closure_liveness_execution import (
    ClosureLifecycleState,
    ClosureLivenessError,
    FinalizationPhase,
    LivenessBoundedStreamingSemanticOwner,
)
from src.policy.reference_backed_finalization import (
    ReferenceBackedFinalizationOwner,
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


def _build(
    *,
    document_ref: str,
    count: int,
    events: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    return bounded.bounded_streaming_semantic_build(
        document_ref=document_ref,
        source_ref=f"source:{document_ref}",
        observation_deltas=_deltas(document_ref, count),
        base_factors=(),
        timings=StageTimingLedger(document_ref=document_ref),
        closure_workers=2,
        owner_partitions=2,
        progress_observer=(
            (lambda payload: events.append(dict(payload)))
            if events is not None
            else None
        ),
    )


def test_bounded_compiler_uses_reference_backed_liveness_owner() -> None:
    assert bounded.BoundedStreamingSemanticOwner is ReferenceBackedFinalizationOwner
    assert issubclass(
        bounded.BoundedStreamingSemanticOwner,
        LivenessBoundedStreamingSemanticOwner,
    )


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

    build, metrics = _build(document_ref=document_ref, count=5, events=events)

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
    assert lifecycle["finalization_contract"] == {
        "contract": "indexed-settled-owner-reductions:v1",
        "full_proposal_rereduction_count": 0,
        "full_state_traversal_count": 1,
    }
    assert metrics["closure_job_count"] == 5
    assert build["bounded_execution"]["scheduler_receipt"]["jobs_completed"] == 5
    assert [row["state"] for row in lifecycle["events"]][-2:] == [
        ClosureLifecycleState.CERTIFYING.value,
        ClosureLifecycleState.COMPLETED.value,
    ]
    assert any(event.get("jobs_completed") == 5 for event in events)


def test_finalization_is_reference_backed_and_process_isolated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_FINALIZATION_BATCH_SIZE", "2")
    document_ref = "document:phased-finalization"

    build, _metrics = _build(document_ref=document_ref, count=5)

    lifecycle = build["closure_lifecycle"]
    completed_phases = {
        event["phase"]
        for event in lifecycle["finalization_events"]
        if event["completed"]
    }
    assert FinalizationPhase.MATERIALIZE_FACTOR_REDUCTIONS.value in completed_phases
    assert FinalizationPhase.MATERIALIZE_RESIDUALS.value in completed_phases
    assert FinalizationPhase.ASSEMBLE_REDUCTION.value in completed_phases
    assert FinalizationPhase.BUILD_CONVERGENT_LEDGER.value in completed_phases
    assert FinalizationPhase.BUILD_FIXED_POINT_CERTIFICATE.value in completed_phases
    assert FinalizationPhase.RELEASE_OWNER_STATE.value in completed_phases
    assert FinalizationPhase.SERIALIZE_CLOSURE_RECEIPT.value in completed_phases
    assert build["reference_backed"] is True
    assert build["compact_execution_evidence"] is True
    assert build["serializer_report"]["received_owner_object"] is False
    assert build["serializer_report"]["reference_only"] is True
    assert build["materialized_reduction"]["factors"]["record_count"] >= 0
    assert not isinstance(build["proposals"], list)

    finalization_root = (
        tmp_path / "closure-finalization" / "document_phased-finalization"
    )
    assert (finalization_root / "materialized-reduction.manifest.json").is_file()
    assert (finalization_root / "materialized-factors.jsonl").is_file()
    assert (finalization_root / "materialized-residuals.jsonl").is_file()
    assert (finalization_root / "convergent-ledger.json").is_file()
    assert (finalization_root / "fixed-point-certificate.json").is_file()
    assert (finalization_root / "closure-reference-receipt.spec.json").is_file()
    assert (finalization_root / "closure-receipt.json").is_file()
    assert (
        finalization_root / "closure-reference-serializer-report.json"
    ).is_file()


def test_identical_replay_preserves_reference_manifest_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    document_ref = "document:resume-finalization"

    first, _ = _build(document_ref=document_ref, count=3)
    second, _ = _build(document_ref=document_ref, count=3)

    assert (
        first["materialized_reduction"]["graph_ref"]
        == second["materialized_reduction"]["graph_ref"]
    )
    assert (
        first["family_manifests"]["factors"]["ordered_digest"]
        == second["family_manifests"]["factors"]["ordered_digest"]
    )
    assert (
        first["family_manifests"]["proposals"]["ordered_digest"]
        == second["family_manifests"]["proposals"]["ordered_digest"]
    )


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
