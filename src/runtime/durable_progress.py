"""Failure-surviving progress ledgers for long strict runtime phases.

The ordinary :class:`PhaseRecorder` is deliberately an in-memory observer.  A
multi-hour production measurement needs one stronger physical property: every
emitted event must already be on durable storage before later work is allowed to
fail.  This subclass preserves the existing progress semantics and only changes
persistence.

The file is rewritten atomically after each event, fsynced, then the containing
directory is fsynced.  Timing/progress remains observational and never enters a
semantic receipt or identity digest.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from typing import TextIO

from src.runtime.progress import PhaseRecorder, ProgressEvent


class DurablePhaseRecorder(PhaseRecorder):
    """A ``PhaseRecorder`` whose current ledger survives terminal failure."""

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

    def emit(self, event: ProgressEvent) -> None:
        super().emit(event)
        self.persist()

    def persist(self) -> None:
        """Atomically persist an exact snapshot of all events emitted so far."""

        with self._durable_lock:
            with self._lock:
                payload = self.to_dict()
            target = self.durable_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(
                    json.dumps(
                        payload,
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            temporary.replace(target)
            parent_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)

    def write_json(self, path: str | Path) -> None:
        """Retain the public API while preserving durable-write semantics."""

        requested = Path(path)
        if requested == self.durable_path:
            self.persist()
            return
        super().write_json(requested)


__all__ = ["DurablePhaseRecorder"]
