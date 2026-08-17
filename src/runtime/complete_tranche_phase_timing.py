"""Durable wall-time observation for complete-tranche phase completion.

The semantic runner remains authoritative for phase execution and receipts. This
module accepts monotone phase-completion snapshots and turns consecutive
completions into wall intervals. The benchmark wrapper feeds it synchronously
from ``PhaseReceipt`` construction, so every completed phase is observed even
when several phases finish faster than a filesystem polling interval.

The timing ledger is deliberately outside semantic receipts. It can rank
minutes/hours work without making elapsed time part of semantic identity, and it
can be persisted after every completed phase so a later failure does not erase
prior timing evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.runtime.performance_attention import MeasuredPhase, rank_optimization_attention


@dataclass(frozen=True, slots=True)
class CompleteTranchePhaseInterval:
    phase: str
    phase_ref: str | None
    state: str | None
    start_epoch_ns: int
    end_epoch_ns: int
    wall_ns: int
    token_count_in: int | None
    token_count_out: int | None
    new_work_units: int | None
    reused_work_units: int | None
    detail: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        value = asdict(self)
        value["wall_seconds"] = self.wall_ns / 1_000_000_000
        return value


def _optional_nonnegative_int(detail: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = detail.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= 0:
            return value
    return None


class CompleteTranchePhaseTimer:
    """Observe monotone phase completions without changing semantic execution."""

    def __init__(self) -> None:
        self._last_fingerprint: tuple[str, str | None] | None = None
        self._interval_start_epoch_ns: int | None = None
        self._interval_start_monotonic_ns: int | None = None
        self._intervals: list[CompleteTranchePhaseInterval] = []

    def prime(
        self,
        state: Mapping[str, Any] | None,
        *,
        epoch_ns: int,
        monotonic_ns: int,
    ) -> None:
        """Establish a pre-run boundary without charging old completed work."""

        if state:
            phase = state.get("last_phase")
            if isinstance(phase, str) and phase:
                receipt = state.get("last_receipt_ref")
                self._last_fingerprint = (
                    phase,
                    str(receipt) if receipt is not None else None,
                )
        self._interval_start_epoch_ns = epoch_ns
        self._interval_start_monotonic_ns = monotonic_ns

    def observe(
        self,
        state: Mapping[str, Any],
        *,
        epoch_ns: int,
        monotonic_ns: int,
    ) -> CompleteTranchePhaseInterval | None:
        phase = state.get("last_phase")
        if not isinstance(phase, str) or not phase:
            return None
        receipt = state.get("last_receipt_ref")
        fingerprint = (phase, str(receipt) if receipt is not None else None)
        if fingerprint == self._last_fingerprint:
            return None

        if self._interval_start_epoch_ns is None or self._interval_start_monotonic_ns is None:
            self.prime(None, epoch_ns=epoch_ns, monotonic_ns=monotonic_ns)

        phase_state = (state.get("phases") or {}).get(phase)
        phase_state = phase_state if isinstance(phase_state, Mapping) else {}
        detail = phase_state.get("detail")
        detail = dict(detail) if isinstance(detail, Mapping) else {}
        interval = CompleteTranchePhaseInterval(
            phase=phase,
            phase_ref=(
                str(phase_state.get("phase_ref"))
                if phase_state.get("phase_ref") is not None
                else None
            ),
            state=(
                str(phase_state.get("state"))
                if phase_state.get("state") is not None
                else None
            ),
            start_epoch_ns=int(self._interval_start_epoch_ns),
            end_epoch_ns=int(epoch_ns),
            wall_ns=max(0, int(monotonic_ns - self._interval_start_monotonic_ns)),
            token_count_in=_optional_nonnegative_int(
                detail, "input_token_count", "tokens_in"
            ),
            token_count_out=_optional_nonnegative_int(
                detail, "output_token_count", "token_count", "tokens_out"
            ),
            new_work_units=_optional_nonnegative_int(
                detail, "new_work_units", "semantic_new_work_units"
            ),
            reused_work_units=_optional_nonnegative_int(
                detail, "reused_work_units", "semantic_reused_work_units"
            ),
            detail=detail,
        )
        self._intervals.append(interval)
        self._last_fingerprint = fingerprint
        self._interval_start_epoch_ns = int(epoch_ns)
        self._interval_start_monotonic_ns = int(monotonic_ns)
        return interval

    @property
    def intervals(self) -> tuple[CompleteTranchePhaseInterval, ...]:
        return tuple(self._intervals)

    def report(self, *, tranche: str, process_returncode: int | None) -> dict[str, Any]:
        ranking = rank_optimization_attention(
            MeasuredPhase(row.phase, row.wall_ns, production_required=True)
            for row in self._intervals
        )
        return {
            "schema_version": "sensiblaw.complete-tranche-phase-timing.v1",
            "tranche": tranche,
            "measurement_semantics": (
                "phase-completion wall intervals; semantic receipts exclude timing"
            ),
            "process_returncode": process_returncode,
            "completed_phase_count": len(self._intervals),
            "total_observed_wall_ns": sum(row.wall_ns for row in self._intervals),
            "phases": [row.to_mapping() for row in self._intervals],
            "optimization_attention": [asdict(row) for row in ranking],
        }


__all__ = [
    "CompleteTranchePhaseInterval",
    "CompleteTranchePhaseTimer",
]
