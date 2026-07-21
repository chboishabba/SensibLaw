"""Measured bidirectional execution for coordinated semantic owners."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from time import monotonic_ns
from typing import Any, Sequence

from src.pnf.streaming_coordination import CoordinatedStreamingSemanticOwner
from src.pnf.streaming_fixed_point import ClosureExecutor, ObservationDelta, SolverReceipt


@dataclass(frozen=True)
class StreamExecutionResult:
    receipts: tuple[SolverReceipt, ...]
    owner_observation_admission_ms: int
    closure_executor_ms: int
    owner_proposal_reduction_ms: int
    accepted_delta_count: int
    deferred_delta_count: int
    backpressure_pause_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_refs": [row.receipt_ref for row in self.receipts],
            "owner_observation_admission_ms": self.owner_observation_admission_ms,
            "closure_executor_ms": self.closure_executor_ms,
            "owner_proposal_reduction_ms": self.owner_proposal_reduction_ms,
            "accepted_delta_count": self.accepted_delta_count,
            "deferred_delta_count": self.deferred_delta_count,
            "backpressure_pause_count": self.backpressure_pause_count,
        }


def _execute_batch(
    *,
    owner: CoordinatedStreamingSemanticOwner,
    executor: ClosureExecutor,
    workers: int,
) -> tuple[list[SolverReceipt], int, int]:
    jobs = owner.drain_ready_jobs()
    if not jobs:
        return [], 0, 0

    def timed_execute(job: Any) -> SolverReceipt:
        started = monotonic_ns()
        receipt = executor.execute(job)
        elapsed_ms = max(0, (monotonic_ns() - started) // 1_000_000)
        return replace(
            receipt,
            metrics={
                **dict(receipt.metrics),
                "executor_elapsed_ms": elapsed_ms,
            },
        )

    receipts: list[SolverReceipt] = []
    closure_ms = 0
    reduction_ms = 0
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="semantic-closure",
    ) as pool:
        futures: dict[Future[SolverReceipt], str] = {
            pool.submit(timed_execute, job): job.job_ref for job in jobs
        }
        for future in as_completed(futures):
            receipt = future.result()
            closure_ms += int(receipt.metrics.get("executor_elapsed_ms", 0))
            started = monotonic_ns()
            owner.admit_solver_receipt(receipt)
            owner.reduce_dirty_groups()
            reduction_ms += max(
                0,
                (monotonic_ns() - started) // 1_000_000,
            )
            receipts.append(receipt)
    return receipts, closure_ms, reduction_ms


def _timed_release(owner: CoordinatedStreamingSemanticOwner) -> tuple[tuple[str, ...], int]:
    started = monotonic_ns()
    released = owner.release_deferred_deltas()
    return released, max(0, (monotonic_ns() - started) // 1_000_000)


def execute_continuous_stream(
    *,
    owner: CoordinatedStreamingSemanticOwner,
    deltas: Sequence[ObservationDelta],
    executor: ClosureExecutor,
    workers: int,
) -> StreamExecutionResult:
    """Interleave parser admission, solver execution, reduction, and queue release."""

    if workers < 1:
        raise ValueError("workers must be positive")
    receipts: list[SolverReceipt] = []
    admission_ms = 0
    closure_ms = 0
    reduction_ms = 0
    accepted = 0
    deferred = 0
    pauses = 0

    for delta in deltas:
        started = monotonic_ns()
        admission = owner.offer_observation_delta(delta)
        admission_ms += max(0, (monotonic_ns() - started) // 1_000_000)
        accepted += int(admission.state == "accepted")
        deferred += int(admission.state == "deferred")
        pauses += int(admission.snapshot.paused)
        if (
            admission.state == "deferred"
            or owner.backpressure_snapshot().paused
            or len(owner._pending_jobs) >= workers
        ):
            rows, executor_elapsed, reduction_elapsed = _execute_batch(
                owner=owner,
                executor=executor,
                workers=workers,
            )
            receipts.extend(rows)
            closure_ms += executor_elapsed
            reduction_ms += reduction_elapsed
            _released, release_ms = _timed_release(owner)
            admission_ms += release_ms

    while True:
        prior = (
            len(owner._pending_jobs),
            len(owner._in_flight_jobs),
            len(owner._deferred_deltas),
            len(owner._dirty_groups),
        )
        rows, executor_elapsed, reduction_elapsed = _execute_batch(
            owner=owner,
            executor=executor,
            workers=workers,
        )
        receipts.extend(rows)
        closure_ms += executor_elapsed
        reduction_ms += reduction_elapsed
        started = monotonic_ns()
        owner.reduce_dirty_groups()
        reduction_ms += max(0, (monotonic_ns() - started) // 1_000_000)
        _released, release_ms = _timed_release(owner)
        admission_ms += release_ms
        current = (
            len(owner._pending_jobs),
            len(owner._in_flight_jobs),
            len(owner._deferred_deltas),
            len(owner._dirty_groups),
        )
        if current == (0, 0, 0, 0):
            break
        if current == prior:
            break

    ordered = tuple(
        sorted(
            {row.receipt_ref: row for row in receipts}.values(),
            key=lambda row: row.receipt_ref,
        )
    )
    return StreamExecutionResult(
        receipts=ordered,
        owner_observation_admission_ms=admission_ms,
        closure_executor_ms=closure_ms,
        owner_proposal_reduction_ms=reduction_ms,
        accepted_delta_count=accepted,
        deferred_delta_count=deferred,
        backpressure_pause_count=pauses,
    )


__all__ = ["StreamExecutionResult", "execute_continuous_stream"]
