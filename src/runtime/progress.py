"""Small deterministic progress surface shared by long-running runtime lanes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any, Mapping, TextIO


PROGRESS_SCHEMA_VERSION = "sl.progress_event.v0_1"


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    state: str
    completed: int = 0
    total: int | None = None
    message: str = ""
    subject_ref: str | None = None
    details: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = PROGRESS_SCHEMA_VERSION
        return {key: value for key, value in payload.items() if value not in (None, "")}


def emit_progress(
    event: ProgressEvent,
    *,
    stream: TextIO | None = None,
    json_lines: bool = False,
) -> None:
    """Emit one progress event without taking authority over the underlying work."""

    target = stream or sys.stderr
    if json_lines:
        print(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True), file=target)
        return
    total = f"/{event.total}" if event.total is not None else ""
    subject = f" {event.subject_ref}" if event.subject_ref else ""
    message = f" — {event.message}" if event.message else ""
    print(
        f"[{event.phase}] {event.state} {event.completed}{total}{subject}{message}",
        file=target,
    )


__all__ = ["PROGRESS_SCHEMA_VERSION", "ProgressEvent", "emit_progress"]
