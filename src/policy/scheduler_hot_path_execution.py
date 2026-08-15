"""Execution-only heap frontier for the bounded document scheduler.

The canonical scheduler order is ``ScheduledJob.order_key``. The legacy physical
implementation repeatedly sorted the complete ready deque in ``extend`` and
again in every leasing cycle. This module preserves exactly the same order key
while maintaining the ready frontier incrementally as a binary heap.
"""

from __future__ import annotations

import heapq
from itertools import count
from typing import Any, Iterable


_INSTALL_MARKER = "_scheduler_hot_path_execution_installed"


def install_scheduler_hot_path_execution() -> bool:
    from src.runtime import bounded_document_scheduler as scheduler

    cls = scheduler.BoundedDocumentScheduler
    if getattr(cls, _INSTALL_MARKER, False):
        return False

    original_init = cls.__init__

    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self._ready_heap_sequence = count()
        # The state field is intentionally reused so existing pressure/sample
        # code continues to observe its exact length/truth value.
        self._state.ready = []

    def push(self: Any, scheduled: Any) -> None:
        heapq.heappush(
            self._state.ready,
            (scheduled.order_key, next(self._ready_heap_sequence), scheduled),
        )

    def extend(self: Any, jobs: Iterable[Any]) -> None:
        rows = tuple(jobs)
        for scheduled in rows:
            push(self, scheduled)
        self._state.queued_bytes += sum(row.estimated_output_bytes for row in rows)
        self._state.peak_queued_bytes = max(
            self._state.peak_queued_bytes,
            self._state.queued_bytes,
        )

    def restore_deferred_if_recovered(self: Any, state: Any) -> None:
        if state is not scheduler.PressureState.NORMAL or not self._state.deferred:
            return
        while self._state.deferred:
            push(self, self._state.deferred.popleft())

    def lease_ready(self: Any, state: Any) -> None:
        if not self._state.ready:
            return
        kept: list[Any] = []
        while self._state.ready:
            _order_key, _sequence, scheduled = heapq.heappop(self._state.ready)
            lease_limit = self.policy.lease_limit(
                in_flight_jobs=len(self._state.in_flight),
                queued_bytes=self._state.queued_bytes,
                pressure_state=state,
                producer=scheduled.work_class.producer,
            )
            if lease_limit < 1:
                if scheduled.work_class.producer and state is not scheduler.PressureState.NORMAL:
                    self._state.deferred.append(scheduled)
                    self._state.deferred_count += 1
                else:
                    kept.append(scheduled)
                continue

            if self.on_lease is not None:
                self.on_lease(scheduled)
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

        for scheduled in kept:
            push(self, scheduled)

    cls.__init__ = init
    cls.extend = extend
    cls._restore_deferred_if_recovered = restore_deferred_if_recovered
    cls._lease_ready = lease_ready
    setattr(cls, _INSTALL_MARKER, True)
    return True


__all__ = ["install_scheduler_hot_path_execution"]
