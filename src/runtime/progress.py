"""Deterministic progress and timing events shared by long-running runtime lanes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from time import monotonic_ns
from threading import Event, Lock, Thread
from typing import Any, Iterator, Mapping, TextIO


PROGRESS_SCHEMA_VERSION = "sl.progress_event.v0_3"
PHASE_LEDGER_SCHEMA_VERSION = "sl.phase_ledger.v0_1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _format_duration_ms(value_ms: int | None) -> str:
    if value_ms is None:
        return ""
    seconds = max(0, int(round(value_ms / 1000)))
    return str(timedelta(seconds=seconds))


def _rate(completed: int | float, elapsed_ms: int) -> float | None:
    if completed <= 0 or elapsed_ms <= 0:
        return None
    return round(float(completed) / (elapsed_ms / 1_000), 3)


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    state: str
    completed: int = 0
    total: int | None = None
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
    work_completed: int | None = None
    work_total: int | None = None
    work_unit: str | None = None
    work_elapsed_ms: int | None = None
    work_units_per_second: float | None = None
    work_estimated_remaining_ms: int | None = None
    work_estimated_completion_at: str | None = None

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
    subject_ref: str | None = None
    message: str = ""
    worker: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    completed: int = 0
    reused: int = 0
    processed_tokens: int = 0
    total_tokens: int | None = None
    heartbeat_seconds: float | None = 30.0
    work_completed: int | None = None
    work_total: int | None = None
    work_unit: str | None = None
    _started_at: str | None = None
    _started_ns: int | None = None
    _work_started_ns: int | None = None
    _finished: bool = False
    _heartbeat_stop: Event = field(default_factory=Event, init=False, repr=False)
    _heartbeat_thread: Thread | None = field(default=None, init=False, repr=False)
    _state_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def start(self) -> None:
        self._started_at = _utc_now()
        self._started_ns = monotonic_ns()
        self._work_started_ns = self._started_ns
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
        work_total: int | None = None,
        work_unit: str | None = None,
        details: Mapping[str, Any] | None = None,
        subject_ref: str | None = None,
        worker: str | None = None,
    ) -> None:
        """Declare the current inner stage without advancing the outer phase."""

        with self._state_lock:
            self.message = stage
            self.details = {"document_stage": stage, **dict(details or {})}
            self.work_completed = 0
            self.work_total = work_total
            self.work_unit = work_unit
            self._work_started_ns = monotonic_ns()
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
        self.recorder.emit(self._event(state="running", elapsed_ms=self.elapsed_ms))

    def observe(
        self,
        *,
        message: str | None = None,
        work_completed: int | None = None,
        work_total: int | None = None,
        work_unit: str | None = None,
        details: Mapping[str, Any] | None = None,
        subject_ref: str | None = None,
        worker: str | None = None,
    ) -> None:
        """Emit current inner work and throughput without completing an outer unit."""

        with self._state_lock:
            if message is not None:
                self.message = message
            if details is not None:
                self.details = {**self.details, **dict(details)}
            if work_completed is not None:
                self.work_completed = max(0, work_completed)
            if work_total is not None:
                self.work_total = max(0, work_total)
            if work_unit is not None:
                self.work_unit = work_unit
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
        self.recorder.emit(self._event(state="running", elapsed_ms=self.elapsed_ms))

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
        with self._state_lock:
            self.completed += amount
            if reused:
                self.reused += amount
            self.processed_tokens += max(0, processed_tokens)
            if message:
                self.message = message
            if details is not None:
                self.details = dict(details)
            if subject_ref is not None:
                self.subject_ref = subject_ref
            if worker is not None:
                self.worker = worker
        self.recorder.emit(
            self._event(
                state="running",
                elapsed_ms=self.elapsed_ms,
                reused=reused,
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

    def _work_estimate(self) -> dict[str, Any]:
        completed = self.work_completed
        elapsed_ms = self.work_elapsed_ms
        rate = _rate(completed or 0, elapsed_ms)
        result: dict[str, Any] = {
            "work_completed": completed,
            "work_total": self.work_total,
            "work_unit": self.work_unit,
            "work_elapsed_ms": elapsed_ms if self._work_started_ns is not None else None,
            "work_units_per_second": rate,
        }
        if (
            rate is not None
            and self.work_total is not None
            and completed is not None
            and self.work_total >= completed
        ):
            remaining_ms = round((self.work_total - completed) / rate * 1_000)
            result["work_estimated_remaining_ms"] = max(0, remaining_ms)
            result["work_estimated_completion_at"] = (
                datetime.now(UTC) + timedelta(milliseconds=max(0, remaining_ms))
            ).isoformat()
        return result

    def _event(
        self,
        *,
        state: str,
        elapsed_ms: int,
        details: Mapping[str, Any] | None = None,
        reused: bool | None = None,
    ) -> ProgressEvent:
        token_rate = _rate(self.processed_tokens, elapsed_ms)
        return ProgressEvent(
            phase=self.phase,
            state=state,
            completed=self.completed,
            total=self.total,
            message=self.message,
            subject_ref=self.subject_ref,
            details=dict(details if details is not None else self.details) or None,
            started_at=self._started_at,
            elapsed_ms=elapsed_ms,
            worker=self.worker,
            reused=reused,
            processed_tokens=self.processed_tokens or None,
            total_tokens=self.total_tokens,
            tokens_per_second=token_rate,
            **self._outer_estimate(elapsed_ms),
            **self._work_estimate(),
        )

    @property
    def elapsed_ms(self) -> int:
        if self._started_ns is None:
            return 0
        return max(0, (monotonic_ns() - self._started_ns) // 1_000_000)

    @property
    def work_elapsed_ms(self) -> int:
        if self._work_started_ns is None:
            return 0
        return max(0, (monotonic_ns() - self._work_started_ns) // 1_000_000)

    def finish(self, *, state: str, details: Mapping[str, Any] | None = None) -> None:
        if self._finished:
            return
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
        f" rate={event.throughput_units_per_second:.3f}/s"
        if event.throughput_units_per_second is not None
        else ""
    )
    eta_at = (
        f" eta_at={event.estimated_completion_at}"
        if event.estimated_completion_at
        else ""
    )
    work = ""
    if event.work_completed is not None:
        work_total = f"/{event.work_total}" if event.work_total is not None else ""
        unit = event.work_unit or "units"
        work_rate = (
            f" {event.work_units_per_second:.3f}/{unit}/s"
            if event.work_units_per_second is not None
            else ""
        )
        work_eta = (
            f" work_eta={_format_duration_ms(event.work_estimated_remaining_ms)}"
            if event.work_estimated_remaining_ms is not None
            else ""
        )
        work = f" work={event.work_completed}{work_total} {unit}{work_rate}{work_eta}"
    token_rate = (
        f" tokens={event.processed_tokens} ({event.tokens_per_second:.3f}/s)"
        if event.processed_tokens is not None and event.tokens_per_second is not None
        else ""
    )
    print(
        f"[{event.phase}] {event.state} {event.completed}{total}{subject}{elapsed}{worker}{reuse}{outer_rate}{eta_at}{work}{token_rate}{message}",
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
