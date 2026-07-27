"""Deterministic progress and timing events shared by long-running runtime lanes.

Progress has two independent coordinates:

* ``completed`` counts closed outer boundaries only;
* ``active_stage`` names work that has begun but has not yet closed.

Inner throughput is a named measure vector.  Anonymous ``rate=/s`` values are not
emitted because a rate without a semantic unit is not interpretable.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from threading import Event, Lock, Thread
from time import monotonic_ns
from typing import Any, Iterator, Mapping, TextIO


PROGRESS_SCHEMA_VERSION = "sl.progress_event.v0_4"
PHASE_LEDGER_SCHEMA_VERSION = "sl.phase_ledger.v0_1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _format_duration_ms(value_ms: int | None) -> str:
    if value_ms is None:
        return ""
    return str(timedelta(seconds=max(0, int(round(value_ms / 1000)))))


def _rate(completed: int | float, elapsed_ms: int) -> float | None:
    if completed <= 0 or elapsed_ms <= 0:
        return None
    return round(float(completed) / (elapsed_ms / 1_000), 3)


def _measure_snapshot(
    measures: Mapping[str, Mapping[str, Any]], elapsed_ms: int
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(measures):
        source = dict(measures[name])
        completed = float(source.get("completed") or 0)
        total_raw = source.get("total")
        total = float(total_raw) if total_raw is not None else None
        unit = str(source.get("unit") or name)
        rate = _rate(completed, elapsed_ms)
        row: dict[str, Any] = {
            "completed": int(completed) if completed.is_integer() else completed,
            "unit": unit,
        }
        if total is not None:
            row["total"] = int(total) if total.is_integer() else total
        if rate is not None:
            row["per_second"] = rate
            if total is not None and total >= completed:
                remaining_ms = round((total - completed) / rate * 1_000)
                row["estimated_remaining_ms"] = max(0, remaining_ms)
                row["estimated_completion_at"] = (
                    datetime.now(UTC)
                    + timedelta(milliseconds=max(0, remaining_ms))
                ).isoformat()
        result[name] = row
    return result


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    state: str
    completed: int = 0
    total: int | None = None
    phase_unit: str = "units"
    message: str = ""
    subject_ref: str | None = None
    details: Mapping[str, Any] | None = None
    started_at: str | None = None
    observed_at: str = field(default_factory=_utc_now)
    elapsed_ms: int | None = None
    throughput_units_per_second: float | None = None
    estimated_remaining_ms: int | None = None
    estimated_completion_at: str | None = None
    processed_tokens: int | None = None
    total_tokens: int | None = None
    tokens_per_second: float | None = None
    worker: str | None = None
    reused: bool | None = None
    active_stage: str | None = None
    stage_elapsed_ms: int | None = None
    measures: Mapping[str, Mapping[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = PROGRESS_SCHEMA_VERSION
        return {key: value for key, value in payload.items() if value not in (None, "")}


@dataclass
class PhaseRecorder:
    """Collect durable phase events while also emitting useful CLI/Actions output."""

    stream: TextIO | None = None
    json_lines: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def emit(self, event: ProgressEvent) -> None:
        with self._lock:
            self.events.append(event.to_dict())
        emit_progress(event, stream=self.stream, json_lines=self.json_lines)

    @contextmanager
    def phase(
        self,
        phase: str,
        *,
        total: int | None = None,
        phase_unit: str = "units",
        subject_ref: str | None = None,
        message: str = "",
        worker: str | None = None,
        details: Mapping[str, Any] | None = None,
        heartbeat_seconds: float | None = 30.0,
    ) -> Iterator["PhaseHandle"]:
        handle = PhaseHandle(
            recorder=self,
            phase=phase,
            total=total,
            phase_unit=phase_unit,
            subject_ref=subject_ref,
            message=message,
            worker=worker,
            details=dict(details or {}),
            heartbeat_seconds=heartbeat_seconds,
        )
        handle.start()
        try:
            yield handle
        except BaseException as error:
            handle.finish(
                state="failed",
                details={"error_type": type(error).__name__, "error": str(error)},
            )
            raise
        else:
            handle.finish(state="completed")

    def to_dict(self) -> dict[str, Any]:
        by_phase: dict[str, dict[str, int]] = {}
        for event in self.events:
            phase = str(event["phase"])
            row = by_phase.setdefault(
                phase, {"events": 0, "elapsed_ms": 0, "failed": 0}
            )
            row["events"] += 1
            row["elapsed_ms"] += int(event.get("elapsed_ms") or 0)
            row["failed"] += int(event.get("state") == "failed")
        return {
            "schema_version": PHASE_LEDGER_SCHEMA_VERSION,
            "event_count": len(self.events),
            "phase_summary": {key: by_phase[key] for key in sorted(by_phase)},
            "events": self.events,
        }

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
            + "\n"
        )


@dataclass
class PhaseHandle:
    recorder: PhaseRecorder
    phase: str
    total: int | None = None
    phase_unit: str = "units"
    subject_ref: str | None = None
    message: str = ""
    worker: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    completed: int = 0
    reused: int = 0
    processed_tokens: int = 0
    total_tokens: int | None = None
    heartbeat_seconds: float | None = 30.0
    active_stage: str | None = None
    measures: dict[str, dict[str, Any]] = field(default_factory=dict)
    _started_at: str | None = None
    _started_ns: int | None = None
    _stage_started_ns: int | None = None
    _finished: bool = False
    _heartbeat_stop: Event = field(default_factory=Event, init=False, repr=False)
    _heartbeat_thread: Thread | None = field(default=None, init=False, repr=False)
    _state_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def start(self) -> None:
        self._started_at = _utc_now()
        self._started_ns = monotonic_ns()
        self.recorder.emit(self._event(state="started", elapsed_ms=0))
        if self.heartbeat_seconds is not None and self.heartbeat_seconds > 0:
            self._heartbeat_thread = Thread(
                target=self._run_heartbeat,
                name=f"progress-{self.phase}",
                daemon=True,
            )
            self._heartbeat_thread.start()

    def _run_heartbeat(self) -> None:
        assert self.heartbeat_seconds is not None
        while not self._heartbeat_stop.wait(self.heartbeat_seconds):
            self.heartbeat()

    def begin_stage(
        self,
        stage: str,
        *,
        measures: Mapping[str, Mapping[str, Any]] | None = None,
        work_total: int | None = None,
        work_unit: str | None = None,
        details: Mapping[str, Any] | None = None,
        subject_ref: str | None = None,
        worker: str | None = None,
    ) -> None:
        """Open an inner stage without advancing any completion counter.

        ``work_total``/``work_unit`` remain as a compatibility shorthand for one
        named measure.  New call sites should pass ``measures``.
        """

        declared = {name: dict(value) for name, value in (measures or {}).items()}
        if work_total is not None or work_unit is not None:
            unit = str(work_unit or "work_items")
            declared.setdefault(
                unit,
                {"completed": 0, "total": work_total, "unit": unit},
            )
        with self._state_lock:
            if self.active_stage is not None:
                raise RuntimeError(
                    f"cannot begin {stage!r}; stage {self.active_stage!r} is still active"
                )
            self.active_stage = stage
            self.measures = declared
            self._stage_started_ns = monotonic_ns()
            self.details = {**self.details, **dict(details or {})}
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
        self.recorder.emit(
            self._event(state="stage_started", elapsed_ms=self.elapsed_ms, message=stage)
        )

    @contextmanager
    def stage(
        self,
        stage: str,
        *,
        measures: Mapping[str, Mapping[str, Any]] | None = None,
        work_total: int | None = None,
        work_unit: str | None = None,
        details: Mapping[str, Any] | None = None,
        subject_ref: str | None = None,
        worker: str | None = None,
        advance_outer: bool = True,
    ) -> Iterator["PhaseHandle"]:
        """Open one inner stage and close it deterministically on exit."""

        self.begin_stage(
            stage,
            measures=measures,
            work_total=work_total,
            work_unit=work_unit,
            details=details,
            subject_ref=subject_ref,
            worker=worker,
        )
        try:
            yield self
        except BaseException as error:
            if self.active_stage is not None:
                self.complete_stage(
                    advance_outer=False,
                    details={
                        "error_type": type(error).__name__,
                        "error": str(error),
                    },
                )
            raise
        else:
            if self.active_stage is not None:
                self.complete_stage(advance_outer=advance_outer)

    def observe(
        self,
        *,
        measures: Mapping[str, int | float | Mapping[str, Any]] | None = None,
        message: str | None = None,
        work_completed: int | None = None,
        work_total: int | None = None,
        work_unit: str | None = None,
        details: Mapping[str, Any] | None = None,
        subject_ref: str | None = None,
        worker: str | None = None,
    ) -> None:
        """Update named inner measures without closing a stage or outer unit."""

        with self._state_lock:
            if self.active_stage is None:
                # Late worker callbacks are diagnostic-only and may arrive just
                # after a stage closes.  Never turn that race into a semantic
                # compilation failure; the closed stage receipt remains the
                # authoritative record.
                return
            for name, value in (measures or {}).items():
                if isinstance(value, Mapping):
                    self.measures[name] = {**self.measures.get(name, {}), **dict(value)}
                else:
                    self.measures.setdefault(name, {"unit": name})["completed"] = value
            if work_completed is not None:
                unit = str(work_unit or next(iter(self.measures), "work_items"))
                row = self.measures.setdefault(unit, {"unit": unit})
                row["completed"] = max(0, work_completed)
                if work_total is not None:
                    row["total"] = max(0, work_total)
            if details is not None:
                self.details = {**self.details, **dict(details)}
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
        self.recorder.emit(
            self._event(
                state="running",
                elapsed_ms=self.elapsed_ms,
                message=message or self.active_stage or "",
            )
        )

    def complete_stage(
        self,
        *,
        advance_outer: bool = False,
        amount: int = 1,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        """Close the active stage; optionally close an outer boundary too."""

        with self._state_lock:
            if self.active_stage is None:
                raise RuntimeError("cannot complete a stage when none is active")
            stage = self.active_stage
            snapshot = _measure_snapshot(self.measures, self.stage_elapsed_ms)
            if advance_outer:
                self.completed += amount
            self.active_stage = None
            self._stage_started_ns = None
            self.measures = {}
            merged = {**self.details, **dict(details or {}), "completed_stage": stage}
        self.recorder.emit(
            self._event(
                state="stage_completed",
                elapsed_ms=self.elapsed_ms,
                details={**merged, "final_measures": snapshot},
                message=stage,
            )
        )

    def heartbeat(self) -> None:
        if self._finished:
            return
        with self._state_lock:
            details = {**self.details, "heartbeat": True}
        self.recorder.emit(
            self._event(state="heartbeat", elapsed_ms=self.elapsed_ms, details=details)
        )

    def advance(
        self,
        *,
        amount: int = 1,
        subject_ref: str | None = None,
        message: str = "",
        reused: bool | None = None,
        details: Mapping[str, Any] | None = None,
        processed_tokens: int = 0,
        worker: str | None = None,
    ) -> None:
        """Close outer units only; never overwrite the active-stage identity."""

        with self._state_lock:
            self.completed += amount
            if reused:
                self.reused += amount
            self.processed_tokens += max(0, processed_tokens)
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
            event_details = dict(details or {})
        self.recorder.emit(
            self._event(
                state="running",
                elapsed_ms=self.elapsed_ms,
                reused=reused,
                details=event_details,
                message=message,
            )
        )

    def _outer_estimate(self, elapsed_ms: int) -> dict[str, Any]:
        if self.total is None or self.total <= 0 or self.completed <= 0 or elapsed_ms <= 0:
            return {}
        throughput = self.completed / (elapsed_ms / 1_000)
        remaining_ms = round(elapsed_ms * (self.total - self.completed) / self.completed)
        return {
            "throughput_units_per_second": round(throughput, 3),
            "estimated_remaining_ms": max(0, remaining_ms),
            "estimated_completion_at": (
                datetime.now(UTC) + timedelta(milliseconds=max(0, remaining_ms))
            ).isoformat(),
        }

    def _event(
        self,
        *,
        state: str,
        elapsed_ms: int,
        details: Mapping[str, Any] | None = None,
        reused: bool | None = None,
        message: str | None = None,
    ) -> ProgressEvent:
        token_rate = _rate(self.processed_tokens, elapsed_ms)
        stage_elapsed = self.stage_elapsed_ms if self.active_stage is not None else None
        measures = (
            _measure_snapshot(self.measures, stage_elapsed or 0)
            if self.active_stage is not None
            else None
        )
        return ProgressEvent(
            phase=self.phase,
            state=state,
            completed=self.completed,
            total=self.total,
            phase_unit=self.phase_unit,
            message=self.message if message is None else message,
            subject_ref=self.subject_ref,
            details=dict(details if details is not None else self.details) or None,
            started_at=self._started_at,
            elapsed_ms=elapsed_ms,
            worker=self.worker,
            reused=reused,
            processed_tokens=self.processed_tokens or None,
            total_tokens=self.total_tokens,
            tokens_per_second=token_rate,
            active_stage=self.active_stage,
            stage_elapsed_ms=stage_elapsed,
            measures=measures,
            **self._outer_estimate(elapsed_ms),
        )

    @property
    def elapsed_ms(self) -> int:
        if self._started_ns is None:
            return 0
        return max(0, (monotonic_ns() - self._started_ns) // 1_000_000)

    @property
    def stage_elapsed_ms(self) -> int:
        if self._stage_started_ns is None:
            return 0
        return max(0, (monotonic_ns() - self._stage_started_ns) // 1_000_000)

    def finish(self, *, state: str, details: Mapping[str, Any] | None = None) -> None:
        if self._finished:
            return
        if self.active_stage is not None:
            raise RuntimeError(
                f"cannot finish phase while stage {self.active_stage!r} is active"
            )
        self._finished = True
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=0.1)
        merged_details = {
            **self.details,
            **dict(details or {}),
            "reused_units": self.reused,
        }
        self.recorder.emit(
            self._event(state=state, elapsed_ms=self.elapsed_ms, details=merged_details)
        )


def emit_progress(
    event: ProgressEvent,
    *,
    stream: TextIO | None = None,
    json_lines: bool = False,
) -> None:
    """Emit one progress event without taking authority over the underlying work."""

    target = stream or sys.stderr
    if json_lines:
        print(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True),
            file=target,
            flush=True,
        )
        return
    total = f"/{event.total}" if event.total is not None else ""
    subject = f" {event.subject_ref}" if event.subject_ref else ""
    message = f" — {event.message}" if event.message else ""
    elapsed = (
        f" elapsed={_format_duration_ms(event.elapsed_ms)}"
        if event.elapsed_ms is not None
        else ""
    )
    worker = f" worker={event.worker}" if event.worker else ""
    reuse = " reused" if event.reused else ""
    outer_rate = (
        f" {event.phase_unit}_rate={event.throughput_units_per_second:.3f}/s"
        if event.throughput_units_per_second is not None
        else ""
    )
    eta_at = (
        f" eta_at={event.estimated_completion_at}"
        if event.estimated_completion_at
        else ""
    )
    stage = f" active_stage={event.active_stage}" if event.active_stage else ""
    measure_text = ""
    if event.measures:
        chunks = []
        for name, row in event.measures.items():
            total_value = f"/{row['total']}" if "total" in row else ""
            rate_value = (
                f" {row['per_second']:.3f}/{row['unit']}/s"
                if "per_second" in row
                else ""
            )
            eta_value = (
                f" eta={_format_duration_ms(row['estimated_remaining_ms'])}"
                if "estimated_remaining_ms" in row
                else ""
            )
            chunks.append(
                f"{name}={row['completed']}{total_value} {row['unit']}{rate_value}{eta_value}"
            )
        measure_text = " measures=[" + "; ".join(chunks) + "]"
    print(
        f"[{event.phase}] {event.state} {event.completed}{total}{subject}{elapsed}{worker}{reuse}{outer_rate}{eta_at}{stage}{measure_text}{message}",
        file=target,
        flush=True,
    )


__all__ = [
    "PHASE_LEDGER_SCHEMA_VERSION",
    "PROGRESS_SCHEMA_VERSION",
    "PhaseHandle",
    "PhaseRecorder",
    "ProgressEvent",
    "emit_progress",
]
