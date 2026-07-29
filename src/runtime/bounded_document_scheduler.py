"""Persistent, bounded work leasing for one active document.

This module does not own semantic state.  It leases ready jobs to a caller-owned
executor, admits completed results through callbacks, and applies memory-aware
backpressure.  Producer jobs may be deferred while reducer, persistence, or
closure-consumer jobs continue draining the frontier.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import Executor, Future, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable, Deque, Generic, Iterable, Mapping, TypeVar

from src.runtime.document_execution_policy import (
    DocumentExecutionPolicy,
    MemoryPressureController,
    PressureDecision,
    PressureState,
    ResourceSnapshot,
    relieve_memory_pressure,
)


JobT = TypeVar("JobT")
ResultT = TypeVar("ResultT")


class WorkClass(StrEnum):
    STRUCTURAL_PRODUCER = "structural_producer"
    SEMANTIC_PRODUCER = "semantic_producer"
    REDUCER = "reducer"
    CLOSURE_CONSUMER = "closure_consumer"
    PERSISTENCE_CONSUMER = "persistence_consumer"

    @property
    def producer(self) -> bool:
        return self in {
            WorkClass.STRUCTURAL_PRODUCER,
            WorkClass.SEMANTIC_PRODUCER,
        }


@dataclass(frozen=True)
class ScheduledJob(Generic[JobT]):
    job_ref: str
    payload: JobT
    work_class: WorkClass
    priority: int = 100
    estimated_output_bytes: int = 0
    criticality: int = 0

    def __post_init__(self) -> None:
        if not self.job_ref:
            raise ValueError("job_ref is required")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.estimated_output_bytes < 0:
            raise ValueError("estimated_output_bytes must be non-negative")

    @property
    def order_key(self) -> tuple[int, int, str]:
        # High criticality first, then explicit priority, then stable identity.
        return (-self.criticality, self.priority, self.job_ref)


@dataclass(frozen=True)
class SchedulerReceipt:
    jobs_submitted: int
    jobs_completed: int
    jobs_deferred: int
    peak_in_flight: int
    peak_queued_bytes: int
    pressure_events: tuple[Mapping[str, object], ...]
    bounded_stop: bool
    final_pressure_state: str

    def to_dict(self) -> dict[str, object]:
        return {
            "jobs_submitted": self.jobs_submitted,
            "jobs_completed": self.jobs_completed,
            "jobs_deferred": self.jobs_deferred,
            "peak_in_flight": self.peak_in_flight,
            "peak_queued_bytes": self.peak_queued_bytes,
            "pressure_events": [dict(row) for row in self.pressure_events],
            "bounded_stop": self.bounded_stop,
            "final_pressure_state": self.final_pressure_state,
        }


@dataclass
class _SchedulerState(Generic[JobT, ResultT]):
    ready: Deque[ScheduledJob[JobT]] = field(default_factory=deque)
    deferred: Deque[ScheduledJob[JobT]] = field(default_factory=deque)
    in_flight: dict[Future[ResultT], ScheduledJob[JobT]] = field(default_factory=dict)
    queued_bytes: int = 0
    submitted: int = 0
    completed: int = 0
    deferred_count: int = 0
    peak_in_flight: int = 0
    peak_queued_bytes: int = 0
    pressure_events: list[dict[str, object]] = field(default_factory=list)


class BoundedDocumentScheduler(Generic[JobT, ResultT]):
    """Lease work continuously while respecting queue and memory bounds."""

    def __init__(
        self,
        *,
        executor: Executor,
        execute: Callable[[JobT], ResultT],
        admit: Callable[[ScheduledJob[JobT], ResultT], Iterable[ScheduledJob[JobT]]],
        sample_resources: Callable[[int, int, int], ResourceSnapshot],
        compact: Callable[[], None],
        policy: DocumentExecutionPolicy,
        checkpoint: Callable[[PressureDecision, ResourceSnapshot], None] | None = None,
    ):
        self.executor = executor
        self.execute = execute
        self.admit = admit
        self.sample_resources = sample_resources
        self.compact = compact
        self.policy = policy
        self.checkpoint = checkpoint
        self.pressure = MemoryPressureController(policy)
        self._state: _SchedulerState[JobT, ResultT] = _SchedulerState()

    def extend(self, jobs: Iterable[ScheduledJob[JobT]]) -> None:
        rows = sorted(jobs, key=lambda row: row.order_key)
        self._state.ready.extend(rows)
        self._state.queued_bytes += sum(row.estimated_output_bytes for row in rows)
        self._state.peak_queued_bytes = max(
            self._state.peak_queued_bytes,
            self._state.queued_bytes,
        )

    def run(self) -> SchedulerReceipt:
        """Run until the frontier drains or pressure becomes unrecoverable."""

        while self._state.ready or self._state.deferred or self._state.in_flight:
            snapshot = self._sample()
            decision, snapshot = relieve_memory_pressure(
                controller=self.pressure,
                snapshot=snapshot,
                compact=self.compact,
                resample=self._sample,
            )
            self._record_pressure(decision, snapshot)
            if decision.checkpoint and self.checkpoint is not None:
                self.checkpoint(decision, snapshot)
            if decision.bounded_stop:
                break

            self._restore_deferred_if_recovered(decision.state)
            self._lease_ready(decision.state)

            if not self._state.in_flight:
                # Producers may be deferred while no consumer is ready.  Rather
                # than spin forever, take another pressure sample; if memory is
                # below the soft limit the next iteration restores producers.
                if self._state.deferred and not self._state.ready:
                    continue
                break

            completed, _ = wait(
                tuple(self._state.in_flight),
                return_when=FIRST_COMPLETED,
            )
            for future in completed:
                scheduled = self._state.in_flight.pop(future)
                result = future.result()
                self._state.completed += 1
                self.extend(self.admit(scheduled, result))

        return SchedulerReceipt(
            jobs_submitted=self._state.submitted,
            jobs_completed=self._state.completed,
            jobs_deferred=self._state.deferred_count,
            peak_in_flight=self._state.peak_in_flight,
            peak_queued_bytes=self._state.peak_queued_bytes,
            pressure_events=tuple(self._state.pressure_events),
            bounded_stop=self.pressure.state is PressureState.BOUNDED_STOP,
            final_pressure_state=self.pressure.state.value,
        )

    def _sample(self) -> ResourceSnapshot:
        return self.sample_resources(
            self._state.queued_bytes,
            len(self._state.ready) + len(self._state.deferred),
            len(self._state.in_flight),
        )

    def _record_pressure(
        self,
        decision: PressureDecision,
        snapshot: ResourceSnapshot,
    ) -> None:
        if decision.state is PressureState.NORMAL and not decision.checkpoint:
            return
        self._state.pressure_events.append(
            {**decision.to_dict(), "snapshot": snapshot.to_dict()}
        )

    def _restore_deferred_if_recovered(self, state: PressureState) -> None:
        if state is not PressureState.NORMAL or not self._state.deferred:
            return
        restored = sorted(self._state.deferred, key=lambda row: row.order_key)
        self._state.deferred.clear()
        self._state.ready.extendleft(reversed(restored))

    def _lease_ready(self, state: PressureState) -> None:
        if not self._state.ready:
            return
        ordered = sorted(self._state.ready, key=lambda row: row.order_key)
        self._state.ready.clear()
        kept: list[ScheduledJob[JobT]] = []

        for scheduled in ordered:
            lease_limit = self.policy.lease_limit(
                in_flight_jobs=len(self._state.in_flight),
                queued_bytes=self._state.queued_bytes,
                pressure_state=state,
                producer=scheduled.work_class.producer,
            )
            if lease_limit < 1:
                if scheduled.work_class.producer and state is not PressureState.NORMAL:
                    self._state.deferred.append(scheduled)
                    self._state.deferred_count += 1
                else:
                    kept.append(scheduled)
                continue

            future = self.executor.submit(self.execute, scheduled.payload)
            self._state.in_flight[future] = scheduled
            self._state.submitted += 1
            self._state.queued_bytes = max(
                0,
                self._state.queued_bytes - scheduled.estimated_output_bytes,
            )
            self._state.peak_in_flight = max(
                self._state.peak_in_flight,
                len(self._state.in_flight),
            )

        self._state.ready.extend(sorted(kept, key=lambda row: row.order_key))


__all__ = [
    "BoundedDocumentScheduler",
    "ScheduledJob",
    "SchedulerReceipt",
    "WorkClass",
]
