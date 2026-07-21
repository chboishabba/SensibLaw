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


PROGRESS_SCHEMA_VERSION = "sl.progress_event.v0_2"
PHASE_LEDGER_SCHEMA_VERSION = "sl.phase_ledger.v0_1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
    worker: str | None = None
    reused: bool | None = None

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
            handle.finish(state="failed", details={"error_type": type(error).__name__, "error": str(error)})
            raise
        else:
            handle.finish(state="completed")

    def to_dict(self) -> dict[str, Any]:
        by_phase: dict[str, dict[str, int]] = {}
        for event in self.events:
            phase = str(event["phase"])
            row = by_phase.setdefault(phase, {"events": 0, "elapsed_ms": 0, "failed": 0})
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
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")


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
    _started_at: str | None = None
    _started_ns: int | None = None
    _finished: bool = False
    heartbeat_seconds: float | None = 30.0
    _heartbeat_stop: Event = field(default_factory=Event, init=False, repr=False)
    _heartbeat_thread: Thread | None = field(default=None, init=False, repr=False)

    def start(self) -> None:
        self._started_at = _utc_now()
        self._started_ns = monotonic_ns()
        self.recorder.emit(
            ProgressEvent(
                phase=self.phase,
                state="started",
                completed=self.completed,
                total=self.total,
                message=self.message,
                subject_ref=self.subject_ref,
                details=self.details or None,
                started_at=self._started_at,
                worker=self.worker,
            )
        )
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

    def heartbeat(self) -> None:
        if self._finished:
            return
        elapsed_ms = self.elapsed_ms
        self.recorder.emit(
            ProgressEvent(
                phase=self.phase,
                state="heartbeat",
                completed=self.completed,
                total=self.total,
                message=self.message,
                subject_ref=self.subject_ref,
                details={**self.details, "heartbeat": True} or None,
                started_at=self._started_at,
                elapsed_ms=elapsed_ms,
                worker=self.worker,
                **self._estimate(elapsed_ms),
            )
        )

    def advance(
        self,
        *,
        amount: int = 1,
        subject_ref: str | None = None,
        message: str = "",
        reused: bool | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.completed += amount
        if reused:
            self.reused += amount
        elapsed_ms = self.elapsed_ms
        estimate = self._estimate(elapsed_ms)
        self.recorder.emit(
            ProgressEvent(
                phase=self.phase,
                state="running",
                completed=self.completed,
                total=self.total,
                message=message,
                subject_ref=subject_ref or self.subject_ref,
                details=dict(details or {}) or None,
                started_at=self._started_at,
                elapsed_ms=elapsed_ms,
                worker=self.worker,
                reused=reused,
                **estimate,
            )
        )

    def _estimate(self, elapsed_ms: int) -> dict[str, Any]:
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

    @property
    def elapsed_ms(self) -> int:
        if self._started_ns is None:
            return 0
        return max(0, (monotonic_ns() - self._started_ns) // 1_000_000)

    def finish(self, *, state: str, details: Mapping[str, Any] | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=0.1)
        merged_details = {**self.details, **dict(details or {}), "reused_units": self.reused}
        self.recorder.emit(
            ProgressEvent(
                phase=self.phase,
                state=state,
                completed=self.completed,
                total=self.total,
                message=self.message,
                subject_ref=self.subject_ref,
                details=merged_details,
                started_at=self._started_at,
                elapsed_ms=self.elapsed_ms,
                worker=self.worker,
            )
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
        print(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True), file=target, flush=True)
        return
    total = f"/{event.total}" if event.total is not None else ""
    subject = f" {event.subject_ref}" if event.subject_ref else ""
    message = f" — {event.message}" if event.message else ""
    elapsed = f" {event.elapsed_ms}ms" if event.elapsed_ms is not None else ""
    worker = f" worker={event.worker}" if event.worker else ""
    reuse = " reused" if event.reused else ""
    estimate = (
        f" eta={event.estimated_remaining_ms}ms"
        if event.estimated_remaining_ms is not None
        else ""
    )
    print(
        f"[{event.phase}] {event.state} {event.completed}{total}{subject}{elapsed}{worker}{reuse}{estimate}{message}",
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
