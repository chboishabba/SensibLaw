"""Shared resource guard for the active document compiler lifecycle.

This guard is execution-only: it neither persists partial semantic state nor
changes compiler output.  An early limit stop is explicitly restart-from-
document, with an atomic receipt for the next allocation investigation.
"""

from __future__ import annotations

from contextlib import contextmanager
import gc
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

from .document_execution_policy import current_process_rss_bytes


MIB = 1024 * 1024


class DocumentResourceLimitError(RuntimeError):
    """The active document exceeded its pre-closure hard resource limit."""

    def __init__(self, receipt: Mapping[str, Any]):
        self.checkpoint = dict(receipt)
        super().__init__("document compilation stopped at a resource checkpoint")


def _environment_mib(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if result < 1:
        raise ValueError(f"{name} must be positive")
    return result


def current_process_tree_rss_bytes() -> int:
    """Return process-tree RSS on Linux, or the local RSS when unavailable."""

    def resident(pid: int) -> int:
        try:
            pages = int(
                Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()[1]
            )
            return pages * int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, IndexError):
            return 0

    def children(pid: int) -> tuple[int, ...]:
        try:
            return tuple(
                int(value)
                for value in Path(f"/proc/{pid}/task/{pid}/children")
                .read_text(encoding="ascii")
                .split()
            )
        except (OSError, ValueError):
            return ()

    root = os.getpid()
    seen: set[int] = {root}
    frontier = [root]
    total = 0
    while frontier:
        pid = frontier.pop()
        total += resident(pid)
        for child in children(pid):
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return total or current_process_rss_bytes()


class ActiveDocumentResourceGuard:
    """Sample stage boundaries and emit a restart-only receipt before hard stop."""

    def __init__(self, *, document_ref: str):
        self.document_ref = document_ref
        self.soft_limit_bytes = (
            _environment_mib("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", 5 * 1024) * MIB
        )
        self.hard_limit_bytes = (
            _environment_mib("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", 6 * 1024) * MIB
        )
        if self.hard_limit_bytes <= self.soft_limit_bytes:
            raise ValueError(
                "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB must exceed soft limit"
            )

    def sample(self) -> dict[str, int]:
        return {
            "rss_bytes": current_process_rss_bytes(),
            "process_tree_rss_bytes": current_process_tree_rss_bytes(),
        }

    def checkpoint(
        self,
        *,
        stage: str,
        current_kernel: str,
        active_batch_size: int = 0,
        retained_indexes: int = 0,
        persisted_counts: Mapping[str, int] | None = None,
        reusable_partition_refs: tuple[str, ...] = (),
        fail_on_soft_pressure: bool = False,
    ) -> dict[str, Any]:
        resources = self.sample()
        observed = max(resources.values())
        soft_pressure = observed >= self.soft_limit_bytes
        if soft_pressure:
            # Only unreachable diagnostic/temporary cycles can be released here;
            # live semantic carriers remain owned by their later consumers.
            gc.collect()
            resources = self.sample()
            observed = max(resources.values())
        payload = {
            "document_ref": self.document_ref,
            "active_stage": stage,
            "current_kernel": current_kernel,
            "resources": resources,
            "soft_memory_limit_bytes": self.soft_limit_bytes,
            "hard_memory_limit_bytes": self.hard_limit_bytes,
            "soft_pressure": soft_pressure,
            "active_batch_size": active_batch_size,
            "retained_indexes": retained_indexes,
            "persisted_counts": dict(persisted_counts or {}),
            "reusable_partition_refs": list(reusable_partition_refs),
            "restart_from_document": True,
            "partial_state_resumable": False,
        }
        self._write_checkpoint(payload)
        if observed >= self.hard_limit_bytes or (
            fail_on_soft_pressure and observed >= self.soft_limit_bytes
        ):
            payload["resource_limit_reached"] = True
            payload["resource_limit_kind"] = (
                "hard" if observed >= self.hard_limit_bytes else "soft"
            )
            self._write_receipt(payload)
            raise DocumentResourceLimitError(payload)
        return payload

    def _write_receipt(self, payload: Mapping[str, Any]) -> None:
        root = os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
        if not root:
            return
        safe = "".join(
            value if value.isalnum() or value in "-_." else "_"
            for value in self.document_ref
        )
        path = Path(root) / f"{safe}.resource-checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        temporary.replace(path)

    def _write_checkpoint(self, payload: Mapping[str, Any]) -> None:
        """Retain stage samples only when an acceptance calibration asks for them."""

        if os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_ALL") != "1":
            return
        root = os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
        if not root:
            return
        safe_document = "".join(
            value if value.isalnum() or value in "-_." else "_"
            for value in self.document_ref
        )
        safe_stage = "".join(
            value if value.isalnum() or value in "-_." else "_"
            for value in f"{payload['active_stage']}.{payload['current_kernel']}"
        )
        path = Path(root) / f"{safe_document}.{safe_stage}.resource-checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        temporary.replace(path)

    @contextmanager
    def stage(self, progress: Any, stage: str, **kwargs: Any) -> Iterator[Any]:
        before = self.checkpoint(stage=stage, current_kernel="stage_boundary_before")
        with progress.stage(stage, **kwargs) as handle:
            if stage == "parser_observation_projection":
                handle.observe(
                    measures=before["resources"],
                    details={"current_kernel": "stage_boundary_before"},
                )
            try:
                yield handle
            finally:
                after = self.checkpoint(
                    stage=stage, current_kernel="stage_boundary_after"
                )
                if stage == "parser_observation_projection":
                    handle.observe(
                        measures=after["resources"],
                        details={"current_kernel": "stage_boundary_after"},
                    )


class GuardedDocumentProgress:
    """Inject the shared guard into an existing progress sink's stage lifecycle."""

    def __init__(self, progress: Any, guard: ActiveDocumentResourceGuard):
        self._progress = progress
        self._guard = guard

    def stage(self, stage: str, **kwargs: Any):
        return self._guard.stage(self._progress, stage, **kwargs)


class NullDocumentProgress:
    """Minimal stage sink so resource checks also run without user progress."""

    @contextmanager
    def stage(self, stage: str, **_kwargs: Any) -> Iterator[Any]:
        class Handle:
            active_stage = stage

            def observe(self, **_values: Any) -> None:
                return None

        yield Handle()


__all__ = [
    "ActiveDocumentResourceGuard",
    "DocumentResourceLimitError",
    "GuardedDocumentProgress",
    "NullDocumentProgress",
    "current_process_tree_rss_bytes",
]
