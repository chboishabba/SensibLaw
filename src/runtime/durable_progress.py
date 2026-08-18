"""Failure-surviving progress journals for long strict runtime phases.

The ordinary :class:`PhaseRecorder` is deliberately an in-memory observer. A
multi-hour production measurement needs one stronger physical property: every
emitted event must already be on durable storage before later work is allowed to
fail. This subclass preserves the existing progress semantics and only changes
physical persistence.

Each event is appended once to an fsynced JSONL journal. This keeps durability
cost O(1) per heartbeat instead of repeatedly rewriting the entire growing
history. The normal aggregate JSON ledger can still be written at a successful
boundary through ``write_json``. Timing/progress remains observational and never
enters a semantic receipt or identity digest.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import TextIO

from src.runtime.progress import PhaseRecorder, ProgressEvent


class DurablePhaseRecorder(PhaseRecorder):
    """A ``PhaseRecorder`` whose emitted event journal survives terminal failure."""

    def __init__(
        self,
        *,
        durable_path: str | Path,
        stream: TextIO | None = None,
        json_lines: bool = False,
    ) -> None:
        super().__init__(stream=stream, json_lines=json_lines)
        self.durable_path = Path(durable_path)
        self._durable_lock = Lock()
        self._journal_initialized = False

    def _append_event(self, payload: dict[str, object]) -> None:
        target = self.durable_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._durable_lock:
            mode = "a" if self._journal_initialized else "w"
            with target.open(mode, encoding="utf-8") as handle:
                handle.write(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
            if not self._journal_initialized:
                parent_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
                self._journal_initialized = True

    def emit(self, event: ProgressEvent) -> None:
        payload = event.to_dict()
        # Keep the base in-memory ledger/CLI behavior unchanged, then durably
        # append exactly the event that was emitted.
        super().emit(event)
        self._append_event(payload)

    def write_json(self, path: str | Path) -> None:
        """Write the ordinary aggregate snapshot at an explicit boundary."""

        super().write_json(path)


__all__ = ["DurablePhaseRecorder"]
