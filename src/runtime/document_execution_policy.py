"""Resource-aware execution policy for one active document.

The policy is deliberately semantic-neutral.  It controls how many ready jobs may
be leased and when producer work should be deferred, compacted, or stopped.  A
soft memory limit is backpressure, not failure: producers pause, consumers and
reducers drain, retained diagnostics are compacted, and memory is sampled again.
Only sustained pressure that cannot be relieved reaches ``bounded_stop``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
from typing import Callable


MIB = 1024 * 1024


class RetentionMode(StrEnum):
    """How much execution history a document compiler retains in memory."""

    AUDIT_FULL = "audit_full"
    PRODUCTION_COMPACT = "production_compact"
    BENCHMARK_VERIFIED = "benchmark_verified"


class PressureState(StrEnum):
    """Scheduler-visible resource state for the active document."""

    NORMAL = "normal"
    THROTTLED = "throttled"
    COMPACTING = "compacting"
    RECOVERING = "recovering"
    BOUNDED_STOP = "bounded_stop"


@dataclass(frozen=True)
class DocumentExecutionPolicy:
    """Bounded execution policy shared by all operators for one document."""

    worker_budget: int = 4
    max_in_flight_jobs: int = 8
    queue_limit_bytes: int = 64 * MIB
    soft_memory_limit_bytes: int = 5 * 1024 * MIB
    hard_memory_limit_bytes: int = 6 * 1024 * MIB
    recovery_target_bytes: int | None = None
    max_compaction_attempts: int = 3
    minimum_recovery_bytes: int = 64 * MIB
    producer_lease_limit_under_pressure: int = 0

    def __post_init__(self) -> None:
        if self.worker_budget < 1:
            raise ValueError("worker_budget must be positive")
        if self.max_in_flight_jobs < 1:
            raise ValueError("max_in_flight_jobs must be positive")
        if self.queue_limit_bytes < 1:
            raise ValueError("queue_limit_bytes must be positive")
        if self.soft_memory_limit_bytes < 1:
            raise ValueError("soft_memory_limit_bytes must be positive")
        if self.hard_memory_limit_bytes <= self.soft_memory_limit_bytes:
            raise ValueError("hard memory limit must exceed soft memory limit")
        if self.max_compaction_attempts < 1:
            raise ValueError("max_compaction_attempts must be positive")
        if self.minimum_recovery_bytes < 0:
            raise ValueError("minimum_recovery_bytes must be non-negative")
        if self.producer_lease_limit_under_pressure < 0:
            raise ValueError("producer pressure lease limit must be non-negative")
        target = self.recovery_target
        if not 0 < target < self.soft_memory_limit_bytes:
            raise ValueError("recovery target must be below the soft memory limit")

    @property
    def recovery_target(self) -> int:
        if self.recovery_target_bytes is not None:
            return self.recovery_target_bytes
        # Hysteresis prevents repeatedly toggling producer work around the limit.
        return int(self.soft_memory_limit_bytes * 0.90)

    def lease_limit(
        self,
        *,
        in_flight_jobs: int,
        queued_bytes: int,
        pressure_state: PressureState,
        producer: bool,
    ) -> int:
        """Return the number of additional jobs that may be leased now."""

        capacity = max(
            0,
            min(self.worker_budget, self.max_in_flight_jobs) - in_flight_jobs,
        )
        if queued_bytes >= self.queue_limit_bytes and producer:
            return 0
        if pressure_state in {
            PressureState.THROTTLED,
            PressureState.COMPACTING,
            PressureState.RECOVERING,
            PressureState.BOUNDED_STOP,
        } and producer:
            return min(capacity, self.producer_lease_limit_under_pressure)
        if pressure_state is PressureState.BOUNDED_STOP:
            return 0
        return capacity


@dataclass(frozen=True)
class DocumentRetentionPolicy:
    """Retention controls independent of semantic execution policy."""

    mode: RetentionMode = RetentionMode.PRODUCTION_COMPACT
    retain_completed_jobs: bool | None = None
    retain_full_receipts: bool | None = None
    retain_state_deltas: bool | None = None
    retain_observation_bodies: bool | None = None

    def _default(self, *, audit: bool, benchmark: bool = False) -> bool:
        if self.mode is RetentionMode.AUDIT_FULL:
            return audit
        if self.mode is RetentionMode.BENCHMARK_VERIFIED:
            return benchmark
        return False

    @property
    def completed_jobs(self) -> bool:
        return (
            self.retain_completed_jobs
            if self.retain_completed_jobs is not None
            else self._default(audit=True, benchmark=False)
        )

    @property
    def full_receipts(self) -> bool:
        return (
            self.retain_full_receipts
            if self.retain_full_receipts is not None
            else self._default(audit=True, benchmark=True)
        )

    @property
    def state_deltas(self) -> bool:
        return (
            self.retain_state_deltas
            if self.retain_state_deltas is not None
            else self._default(audit=True, benchmark=False)
        )

    @property
    def observation_bodies(self) -> bool:
        return (
            self.retain_observation_bodies
            if self.retain_observation_bodies is not None
            else self._default(audit=True, benchmark=True)
        )


@dataclass(frozen=True)
class ResourceSnapshot:
    """One scheduler sampling point."""

    rss_bytes: int
    process_tree_rss_bytes: int
    queued_bytes: int = 0
    pending_jobs: int = 0
    in_flight_jobs: int = 0
    dirty_groups: int = 0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if isinstance(value, int) and value < 0:
                raise ValueError(f"{name} must be non-negative")

    def to_dict(self) -> dict[str, int]:
        return {
            "rss_bytes": self.rss_bytes,
            "process_tree_rss_bytes": self.process_tree_rss_bytes,
            "queued_bytes": self.queued_bytes,
            "pending_jobs": self.pending_jobs,
            "in_flight_jobs": self.in_flight_jobs,
            "dirty_groups": self.dirty_groups,
        }


@dataclass(frozen=True)
class PressureDecision:
    state: PressureState
    defer_producers: bool
    prioritise_consumers: bool
    compact: bool
    checkpoint: bool
    bounded_stop: bool
    reason: str
    compaction_attempt: int
    rss_before_bytes: int | None
    rss_after_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "defer_producers": self.defer_producers,
            "prioritise_consumers": self.prioritise_consumers,
            "compact": self.compact,
            "checkpoint": self.checkpoint,
            "bounded_stop": self.bounded_stop,
            "reason": self.reason,
            "compaction_attempt": self.compaction_attempt,
            "rss_before_bytes": self.rss_before_bytes,
            "rss_after_bytes": self.rss_after_bytes,
        }


class MemoryPressureController:
    """Convert memory samples into backpressure and recovery decisions."""

    def __init__(self, policy: DocumentExecutionPolicy):
        self.policy = policy
        self.state = PressureState.NORMAL
        self.compaction_attempts = 0
        self._pressure_baseline: int | None = None
        self._last_rss: int | None = None

    def observe(self, snapshot: ResourceSnapshot) -> PressureDecision:
        rss = max(snapshot.rss_bytes, snapshot.process_tree_rss_bytes)
        previous = self._last_rss
        self._last_rss = rss

        if self.state is PressureState.BOUNDED_STOP:
            return self._decision(
                rss,
                previous,
                bounded_stop=True,
                checkpoint=True,
                reason="resource limit already declared unrecoverable",
            )

        if rss < self.policy.recovery_target:
            self.state = PressureState.NORMAL
            self.compaction_attempts = 0
            self._pressure_baseline = None
            return self._decision(rss, previous, reason="memory below recovery target")

        if rss < self.policy.soft_memory_limit_bytes:
            # Stay throttled until hysteresis clears, avoiding producer oscillation.
            if self.state is PressureState.NORMAL:
                return self._decision(rss, previous, reason="memory below soft limit")
            self.state = PressureState.RECOVERING
            return self._decision(
                rss,
                previous,
                defer=True,
                consume=True,
                checkpoint=True,
                reason="memory falling but recovery target not reached",
            )

        if self._pressure_baseline is None:
            self._pressure_baseline = rss

        recovered = self._pressure_baseline - rss
        if recovered >= self.policy.minimum_recovery_bytes:
            self._pressure_baseline = rss
            self.compaction_attempts = 0
            self.state = PressureState.RECOVERING
            return self._decision(
                rss,
                previous,
                defer=True,
                consume=True,
                checkpoint=True,
                reason="pressure relief is shrinking the footprint",
            )

        if self.compaction_attempts < self.policy.max_compaction_attempts:
            self.compaction_attempts += 1
            self.state = PressureState.COMPACTING
            return self._decision(
                rss,
                previous,
                defer=True,
                consume=True,
                compact=True,
                checkpoint=True,
                reason="soft limit crossed; defer producers and compact",
            )

        if rss < self.policy.hard_memory_limit_bytes:
            self.state = PressureState.THROTTLED
            return self._decision(
                rss,
                previous,
                defer=True,
                consume=True,
                checkpoint=True,
                reason="compaction exhausted; continue draining below hard limit",
            )

        # The hard limit is terminal only after compaction attempts failed and the
        # footprint did not shrink by the configured minimum amount.
        self.state = PressureState.BOUNDED_STOP
        return self._decision(
            rss,
            previous,
            defer=True,
            consume=True,
            checkpoint=True,
            bounded_stop=True,
            reason="hard limit sustained after pressure relief failed",
        )

    def _decision(
        self,
        rss: int,
        previous: int | None,
        *,
        defer: bool = False,
        consume: bool = False,
        compact: bool = False,
        checkpoint: bool = False,
        bounded_stop: bool = False,
        reason: str,
    ) -> PressureDecision:
        return PressureDecision(
            state=self.state,
            defer_producers=defer,
            prioritise_consumers=consume,
            compact=compact,
            checkpoint=checkpoint,
            bounded_stop=bounded_stop,
            reason=reason,
            compaction_attempt=self.compaction_attempts,
            rss_before_bytes=previous,
            rss_after_bytes=rss,
        )


def current_process_rss_bytes() -> int:
    """Return current RSS without adding a mandatory monitoring dependency."""

    statm = Path("/proc/self/statm")
    try:
        pages = int(statm.read_text(encoding="ascii").split()[1])
        return pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        # On unsupported systems callers may inject their own sampler.  Zero is
        # explicitly "unavailable", not an invented memory reading.
        return 0


def relieve_memory_pressure(
    *,
    controller: MemoryPressureController,
    snapshot: ResourceSnapshot,
    compact: Callable[[], None],
    resample: Callable[[], ResourceSnapshot],
) -> tuple[PressureDecision, ResourceSnapshot]:
    """Apply one bounded pressure-relief cycle and return the post-action sample."""

    decision = controller.observe(snapshot)
    if decision.compact:
        compact()
        snapshot = resample()
        decision = controller.observe(snapshot)
    return decision, snapshot


__all__ = [
    "DocumentExecutionPolicy",
    "DocumentRetentionPolicy",
    "MemoryPressureController",
    "PressureDecision",
    "PressureState",
    "ResourceSnapshot",
    "RetentionMode",
    "current_process_rss_bytes",
    "relieve_memory_pressure",
]
