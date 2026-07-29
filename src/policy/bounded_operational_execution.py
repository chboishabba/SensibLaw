"""Bounded execution strategy for the canonical operational document compiler.

This module does not define a second compiler.  It installs one execution-only
strategy into :mod:`src.policy.operational_corpus_compilation`: the existing
``_streaming_semantic_build`` seam is routed through the indexed bounded owner
and a persistent, bounded closure executor.  Semantic identities, reducers,
fixed-point certificates, and the outward artifact contract remain canonical.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
from time import monotonic_ns
from typing import Any, Mapping, Sequence

from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
from src.pnf.streaming_fixed_point import CoverageNotice, PythonClosureExecutor
from src.pnf.streaming_operator_executor import (
    STREAMING_OPERATOR_DECLARATION_REF,
    operator_streaming_declaration,
    solve_operator_job,
)
from src.runtime.bounded_document_scheduler import (
    BoundedDocumentScheduler,
    ScheduledJob,
    WorkClass,
)
from src.runtime.document_execution_policy import (
    DocumentExecutionPolicy,
    DocumentRetentionPolicy,
    ResourceSnapshot,
    RetentionMode,
    current_process_rss_bytes,
)

_INSTALL_MARKER = "_bounded_streaming_execution_installed"
MIB = 1024 * 1024


class DocumentResourceLimitError(RuntimeError):
    """The document frontier was checkpointed after unrecoverable pressure."""

    def __init__(self, checkpoint: Mapping[str, Any]):
        self.checkpoint = dict(checkpoint)
        super().__init__(
            "document execution reached bounded_stop after memory pressure "
            "could not be relieved"
        )


def _integer_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if result < 1:
        raise ValueError(f"{name} must be positive")
    return result


def execution_policy_from_environment(*, worker_budget: int) -> DocumentExecutionPolicy:
    """Resolve bounded execution controls without changing compiler signatures."""

    soft_mib = _integer_env("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", 5 * 1024)
    hard_mib = _integer_env("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", 6 * 1024)
    if hard_mib <= soft_mib:
        raise ValueError(
            "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB must exceed the soft limit"
        )
    recovery_mib = _integer_env(
        "SENSIBLAW_DOCUMENT_RECOVERY_MEMORY_MIB",
        max(1, int(soft_mib * 0.9)),
    )
    return DocumentExecutionPolicy(
        worker_budget=max(1, worker_budget),
        max_in_flight_jobs=_integer_env(
            "SENSIBLAW_DOCUMENT_MAX_IN_FLIGHT",
            max(2, worker_budget * 2),
        ),
        queue_limit_bytes=_integer_env(
            "SENSIBLAW_DOCUMENT_QUEUE_LIMIT_MIB", 64
        )
        * MIB,
        soft_memory_limit_bytes=soft_mib * MIB,
        hard_memory_limit_bytes=hard_mib * MIB,
        recovery_target_bytes=recovery_mib * MIB,
        max_compaction_attempts=_integer_env(
            "SENSIBLAW_DOCUMENT_COMPACTION_ATTEMPTS", 3
        ),
        minimum_recovery_bytes=_integer_env(
            "SENSIBLAW_DOCUMENT_MINIMUM_RECOVERY_MIB", 64
        )
        * MIB,
    )


def retention_policy_from_environment() -> DocumentRetentionPolicy:
    raw = os.environ.get(
        "SENSIBLAW_DOCUMENT_RETENTION_MODE",
        RetentionMode.PRODUCTION_COMPACT.value,
    )
    try:
        mode = RetentionMode(raw)
    except ValueError as error:
        allowed = ", ".join(value.value for value in RetentionMode)
        raise ValueError(
            f"SENSIBLAW_DOCUMENT_RETENTION_MODE must be one of: {allowed}"
        ) from error
    return DocumentRetentionPolicy(mode=mode)


def _resident_bytes(pid: int) -> int:
    try:
        pages = int(
            Path(f"/proc/{pid}/statm")
            .read_text(encoding="ascii")
            .split()[1]
        )
        return pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        return 0


def _child_pids(pid: int) -> tuple[int, ...]:
    children_path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        direct = tuple(
            int(value)
            for value in children_path.read_text(encoding="ascii").split()
        )
    except (OSError, ValueError):
        return ()
    descendants: list[int] = []
    frontier = list(direct)
    seen: set[int] = set()
    while frontier:
        child = frontier.pop()
        if child in seen:
            continue
        seen.add(child)
        descendants.append(child)
        frontier.extend(_child_pids(child))
    return tuple(descendants)


def current_process_tree_rss_bytes() -> int:
    pid = os.getpid()
    return _resident_bytes(pid) + sum(
        _resident_bytes(child) for child in _child_pids(pid)
    )


def _checkpoint_path(document_ref: str) -> Path | None:
    root = os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
    if not root:
        return None
    safe_ref = "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in document_ref
    )
    return Path(root) / f"{safe_ref}.resource-checkpoint.json"


def _write_checkpoint(document_ref: str, payload: Mapping[str, Any]) -> None:
    path = _checkpoint_path(document_ref)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _estimated_job_output_bytes(job: Any) -> int:
    # Input refs and token dictionaries are the best bounded estimate available
    # before an operator runs.  This is deliberately conservative and feeds
    # backpressure only; it is not a semantic measurement.
    payload = dict(job.input_payload or {})
    delta = dict(payload.get("observation_delta") or {})
    observations = tuple(delta.get("observations") or ())
    return max(1_024, len(job.input_refs) * 96 + len(observations) * 512)


def bounded_streaming_semantic_build(
    *,
    document_ref: str,
    source_ref: str,
    observation_deltas: Sequence[Any],
    base_factors: Sequence[Any],
    timings: Any,
    closure_workers: int,
    owner_partitions: int,
    progress_observer: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Canonical streaming build with bounded retention and closure leasing."""

    # Import lazily so installing this strategy cannot create a second module
    # authority or an import cycle while src.policy is initialising.
    from src.policy import operational_corpus_compilation as operational

    policy = execution_policy_from_environment(worker_budget=closure_workers)
    retention = retention_policy_from_environment()
    owner = BoundedStreamingSemanticOwner(
        document_ref=document_ref,
        partition_count=owner_partitions,
        retention=retention,
    )
    declaration = operator_streaming_declaration()
    owner.register_declarations((declaration,))
    for delta in observation_deltas:
        owner.admit_observation_delta(delta)

    all_observation_refs = tuple(
        sorted(
            {
                ref
                for delta in observation_deltas
                for ref in delta.observation_refs
            }
        )
    )
    with timings.stage("base_proposal_reduction") as stage:
        base_proposals = tuple(
            operational._base_proposal_from_factor(
                document_ref=document_ref,
                source_ref=source_ref,
                factor=factor,
            )
            for factor in base_factors
        )
        owner.admit_proposals(base_proposals, stage="base")
        owner.reduce_dirty_groups()
        base_reduction = owner.materialized_reduction
        stage.record(
            input_nodes=len(base_proposals),
            output_nodes=len(base_reduction.factors),
            input_edges=len(base_proposals),
            output_edges=len(base_reduction.factors),
            proposals_generated=len(base_proposals),
            duplicates_collapsed=base_reduction.deduplicated_count,
            alternatives_retained=len(base_reduction.factors),
            residuals_emitted=len(base_reduction.residuals),
        )

    closure = PythonClosureExecutor(
        {STREAMING_OPERATOR_DECLARATION_REF: solve_operator_job}
    )
    ready_jobs = owner.drain_ready_jobs(limit=policy.max_in_flight_jobs)
    # Return leased jobs to pending state; the bounded scheduler is the sole
    # authority that marks each job in flight as it is submitted.
    for job in ready_jobs:
        owner._in_flight_jobs.pop(job.job_ref, None)
        owner._pending_jobs[job.job_ref] = job

    receipts: list[Any] = []
    completed_input_refs = 0
    completed_proposals = 0
    pressure_checkpoints: list[dict[str, Any]] = []
    reduction_elapsed_ms = 0

    def sample_resources(
        queued_bytes: int,
        pending_jobs: int,
        in_flight_jobs: int,
    ) -> ResourceSnapshot:
        return ResourceSnapshot(
            rss_bytes=current_process_rss_bytes(),
            process_tree_rss_bytes=current_process_tree_rss_bytes(),
            queued_bytes=queued_bytes,
            pending_jobs=pending_jobs,
            in_flight_jobs=in_flight_jobs,
            dirty_groups=len(owner._dirty_groups),
        )

    def checkpoint(decision: Any, snapshot: ResourceSnapshot) -> None:
        row = {
            "document_ref": document_ref,
            "resource_limit_reached": bool(decision.bounded_stop),
            "state": decision.state.value,
            "checkpoint_retained": True,
            "decision": decision.to_dict(),
            "resources": snapshot.to_dict(),
            "retention": owner.retention_counts(),
            "pending_job_refs": sorted(owner._pending_jobs),
            "in_flight_job_refs": sorted(owner._in_flight_jobs),
            "completed_job_signature_count": len(
                owner._completed_job_signatures
            ),
        }
        pressure_checkpoints.append(row)
        _write_checkpoint(document_ref, row)

    def admit(scheduled: ScheduledJob[Any], receipt: Any):
        nonlocal completed_input_refs, completed_proposals, reduction_elapsed_ms
        reduction_started = monotonic_ns()
        owner.admit_solver_receipt(receipt)
        owner.reduce_dirty_groups()
        reduction_elapsed_ms += max(
            0, (monotonic_ns() - reduction_started) // 1_000_000
        )
        receipts.append(receipt)
        completed_input_refs += len(receipt.input_refs)
        completed_proposals += len(receipt.proposals)
        snapshot = sample_resources(0, len(owner._pending_jobs), len(owner._in_flight_jobs))
        if progress_observer is not None:
            progress_observer(
                {
                    "jobs_completed": len(receipts),
                    "input_refs_processed": completed_input_refs,
                    "proposals_emitted": completed_proposals,
                    "pending_jobs": len(owner._pending_jobs),
                    "in_flight_jobs": len(owner._in_flight_jobs),
                    "dirty_groups": len(owner._dirty_groups),
                    "rss_bytes": snapshot.rss_bytes,
                    "process_tree_rss_bytes": snapshot.process_tree_rss_bytes,
                    "retained_jobs": owner.retention_counts()["jobs"],
                    "retained_receipts": owner.retention_counts()["receipts"],
                }
            )
        return ()

    scheduled_jobs = tuple(
        ScheduledJob(
            job_ref=job.job_ref,
            payload=job,
            work_class=WorkClass.CLOSURE_CONSUMER,
            priority=job.priority,
            criticality=max(0, 1_000 - job.priority),
            estimated_output_bytes=_estimated_job_output_bytes(job),
        )
        for job in sorted(owner._pending_jobs.values(), key=lambda row: (row.priority, row.job_ref))
    )
    owner._pending_jobs.clear()

    with timings.stage("composition_generation") as stage:
        stage.record(
            input_nodes=len(all_observation_refs),
            output_nodes=len(scheduled_jobs),
            details={
                "owner_partitions": owner_partitions,
                "closure_workers": closure_workers,
                "bounded_leasing": True,
                "max_in_flight_jobs": policy.max_in_flight_jobs,
                "queue_limit_bytes": policy.queue_limit_bytes,
            },
        )

    with timings.stage(
        "closure_executor_evaluation",
        backend_ref=closure.backend_ref,
        details={
            "workers": closure_workers,
            "admission_and_reduction_overlap": True,
            "bounded_leasing": True,
        },
    ) as closure_stage:
        with ThreadPoolExecutor(
            max_workers=policy.worker_budget,
            thread_name_prefix="semantic-closure-bounded",
        ) as pool:
            scheduler = BoundedDocumentScheduler(
                executor=pool,
                execute=closure.execute,
                admit=admit,
                sample_resources=sample_resources,
                compact=owner.compact_retained_history,
                policy=policy,
                checkpoint=checkpoint,
            )
            scheduler.extend(scheduled_jobs)
            scheduler_receipt = scheduler.run()
        closure_stage.record(
            input_nodes=completed_input_refs,
            output_nodes=completed_proposals,
            proposals_generated=completed_proposals,
            details={
                "job_count": len(scheduled_jobs),
                "scheduler": scheduler_receipt.to_dict(),
            },
        )

    if scheduler_receipt.bounded_stop:
        final_checkpoint = pressure_checkpoints[-1] if pressure_checkpoints else {
            "document_ref": document_ref,
            "resource_limit_reached": True,
            "state": "bounded_stop",
            "checkpoint_retained": False,
            "scheduler": scheduler_receipt.to_dict(),
        }
        raise DocumentResourceLimitError(final_checkpoint)

    materialized = owner.materialized_reduction
    timings.append(
        stage="composition_proposal_reduction",
        elapsed_ms=reduction_elapsed_ms,
        input_nodes=len(base_proposals) + completed_proposals,
        output_nodes=len(materialized.factors),
        input_edges=len(base_proposals) + completed_proposals,
        output_edges=len(materialized.factors),
        alternatives_retained=len(materialized.factors),
        residuals_emitted=len(materialized.residuals),
        details={
            "overlaps_with": "closure_executor_evaluation",
            "streamed_receipt_count": len(receipts),
            "indexed_owner_reduction": True,
        },
    )

    owner.admit_coverage_notice(
        CoverageNotice(
            document_ref=document_ref,
            scope_ref="document-global",
            barrier="document",
            state="complete",
            evidence_refs=tuple(delta.delta_ref for delta in observation_deltas),
        )
    )
    certificate = owner.fixed_point_certificate()
    if not certificate.local_fixed_point_reached:
        raise ValueError(
            "bounded streaming semantic owner did not reach a local fixed point"
        )

    scopes = sorted({delta.scope_ref for delta in observation_deltas})
    # Preserve the established artifact contract for persistence.  Compact mode
    # removes completed execution history before this one final serialization.
    build = {
        **owner.to_dict(),
        "region_boundary_summaries": [
            owner.region_boundary_summary(scope).to_dict() for scope in scopes
        ],
        "fixed_point_certificate": certificate.to_dict(),
        "declarations": [declaration.to_dict()],
        "closure_backend": closure.backend_ref,
        "streaming_bidirectional": True,
        "logical_owner_granularity": "document_scope_factor_family",
        "eventual_consistency": "convergent_append_only",
        "materialized_view_authority": "deterministic_candidate_projection",
        "bounded_execution": {
            "policy": {
                "worker_budget": policy.worker_budget,
                "max_in_flight_jobs": policy.max_in_flight_jobs,
                "queue_limit_bytes": policy.queue_limit_bytes,
                "soft_memory_limit_bytes": policy.soft_memory_limit_bytes,
                "hard_memory_limit_bytes": policy.hard_memory_limit_bytes,
                "recovery_target_bytes": policy.recovery_target,
            },
            "retention_mode": retention.mode.value,
            "scheduler_receipt": scheduler_receipt.to_dict(),
            "retention_counts": owner.retention_counts(),
            "pressure_checkpoints": pressure_checkpoints,
        },
    }
    metrics: dict[str, Any] = {
        "observation_delta_count": len(observation_deltas),
        "observation_count": len(all_observation_refs),
        "observation_refs": all_observation_refs,
        "base_proposal_count": len(base_proposals),
        "base_proposal_refs": tuple(row.proposal_ref for row in base_proposals),
        "base_factor_count": len(base_reduction.factors),
        "base_factor_refs": tuple(row.factor_ref for row in base_reduction.factors),
        "base_residual_count": len(base_reduction.residuals),
        "closure_job_count": len(scheduled_jobs),
        "derived_proposal_count": completed_proposals,
        "derived_proposal_refs": tuple(
            sorted(
                proposal.proposal_ref
                for receipt in receipts
                for proposal in receipt.proposals
            )
        ),
        "materialized_factor_count": len(materialized.factors),
        "materialized_factor_refs": tuple(
            row.factor_ref for row in materialized.factors
        ),
        "materialized_residual_count": len(materialized.residuals),
        "scheduler_receipt": scheduler_receipt.to_dict(),
        "retention_counts": owner.retention_counts(),
    }
    return build, metrics


def install_bounded_operational_execution() -> bool:
    """Idempotently install the bounded strategy on the canonical compiler."""

    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False
    operational._serial_streaming_semantic_build = operational._streaming_semantic_build
    operational._streaming_semantic_build = bounded_streaming_semantic_build
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = [
    "DocumentResourceLimitError",
    "bounded_streaming_semantic_build",
    "current_process_tree_rss_bytes",
    "execution_policy_from_environment",
    "install_bounded_operational_execution",
    "retention_policy_from_environment",
]
