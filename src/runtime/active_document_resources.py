"""Shared resource guard for the active document compiler lifecycle.

This guard is execution-only: it neither persists partial semantic state nor
changes compiler output. An early limit stop is explicitly restart-from-
document, with an atomic receipt for the next allocation investigation.

Resource checkpoints also carry partial monotonic/CPU timing coordinates. Those
coordinates survive timeout or resource-stop termination and are diagnostic
only: they must never be promoted into completed parser/post-parser acceptance
metrics.
"""

from __future__ import annotations

from contextlib import contextmanager
import gc
import json
import os
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic_ns, process_time_ns
from typing import Any, Iterator, Mapping

from .document_execution_policy import current_process_rss_bytes


MIB = 1024 * 1024
PARTIAL_TIMING_SCHEMA_VERSION = "sensiblaw.partial-document-timing.v0_3"


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


def _heartbeat_seconds() -> float:
    raw = os.environ.get("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS")
    if raw is None or not raw.strip():
        return 5.0
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS must be numeric") from error
    if value < 0:
        raise ValueError("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS cannot be negative")
    return value


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
    """Sample stage boundaries and emit restart-only resource/timing evidence."""

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
        self._started_monotonic_ns = monotonic_ns()
        self._started_process_cpu_ns = process_time_ns()
        self._previous_monotonic_ns = self._started_monotonic_ns
        self._previous_process_cpu_ns = self._started_process_cpu_ns
        self._sample_ordinal = 0
        self._timing_lock = Lock()
        self._kernel_lock = Lock()
        self._active_kernel = "stage_heartbeat"

    def set_active_kernel(self, current_kernel: str) -> None:
        with self._kernel_lock:
            self._active_kernel = str(current_kernel)

    def active_kernel(self) -> str:
        with self._kernel_lock:
            return self._active_kernel

    def sample(self) -> dict[str, int]:
        return {
            "rss_bytes": current_process_rss_bytes(),
            "process_tree_rss_bytes": current_process_tree_rss_bytes(),
        }

    def _timing_sample(self, *, stage: str, current_kernel: str) -> dict[str, Any]:
        with self._timing_lock:
            observed_monotonic_ns = monotonic_ns()
            observed_process_cpu_ns = process_time_ns()
            self._sample_ordinal += 1
            payload = {
                "schema_version": PARTIAL_TIMING_SCHEMA_VERSION,
                "sample_ordinal": self._sample_ordinal,
                "stage": stage,
                "current_kernel": current_kernel,
                "observed_monotonic_ns": observed_monotonic_ns,
                "document_elapsed_ns": observed_monotonic_ns - self._started_monotonic_ns,
                "interval_elapsed_ns": observed_monotonic_ns - self._previous_monotonic_ns,
                "process_cpu_elapsed_ns": observed_process_cpu_ns
                - self._started_process_cpu_ns,
                "interval_process_cpu_ns": observed_process_cpu_ns
                - self._previous_process_cpu_ns,
                "semantic_authority_effect": "none",
                "semantic_identity_effect": "none",
                "acceptance_eligible": False,
                "partial_run_evidence": True,
            }
            self._previous_monotonic_ns = observed_monotonic_ns
            self._previous_process_cpu_ns = observed_process_cpu_ns
            return payload

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
        enforce_limits: bool = True,
    ) -> dict[str, Any]:
        resources = self.sample()
        observed = max(resources.values())
        soft_pressure = observed >= self.soft_limit_bytes
        if soft_pressure:
            gc.collect()
            resources = self.sample()
            observed = max(resources.values())
        payload = {
            "document_ref": self.document_ref,
            "active_stage": stage,
            "current_kernel": current_kernel,
            "resources": resources,
            "partial_timing": self._timing_sample(
                stage=stage,
                current_kernel=current_kernel,
            ),
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
        self._append_timing_sample(payload)
        self._write_checkpoint(payload)
        if enforce_limits and (
            observed >= self.hard_limit_bytes
            or (fail_on_soft_pressure and observed >= self.soft_limit_bytes)
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

    def _append_timing_sample(self, payload: Mapping[str, Any]) -> None:
        if os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_ALL") != "1":
            return
        root = os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
        if not root:
            return
        safe_document = "".join(
            value if value.isalnum() or value in "-_." else "_"
            for value in self.document_ref
        )
        path = Path(root) / f"{safe_document}.partial-timing.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "document_ref": self.document_ref,
            "active_stage": payload["active_stage"],
            "current_kernel": payload["current_kernel"],
            "resources": payload["resources"],
            "active_batch_size": payload["active_batch_size"],
            "retained_indexes": payload["retained_indexes"],
            "persisted_counts": payload["persisted_counts"],
            "partial_timing": payload["partial_timing"],
        }
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()

    def _write_checkpoint(self, payload: Mapping[str, Any]) -> None:
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
        self.set_active_kernel("stage_boundary_before")
        before = self.checkpoint(stage=stage, current_kernel="stage_boundary_before")
        heartbeat_stop = Event()
        heartbeat_interval = _heartbeat_seconds()
        heartbeat_thread: Thread | None = None

        def emit_heartbeats() -> None:
            while not heartbeat_stop.wait(heartbeat_interval):
                self.checkpoint(
                    stage=stage,
                    current_kernel=self.active_kernel(),
                    enforce_limits=False,
                )

        if heartbeat_interval > 0:
            heartbeat_thread = Thread(
                target=emit_heartbeats,
                name=f"sensiblaw-stage-heartbeat-{stage}",
                daemon=True,
            )
            heartbeat_thread.start()
        with progress.stage(stage, **kwargs) as handle:
            if stage == "parser_observation_projection":
                handle.observe(
                    measures=before["resources"],
                    details={
                        "current_kernel": "stage_boundary_before",
                        "partial_timing": before["partial_timing"],
                    },
                )
            try:
                yield handle
            finally:
                heartbeat_stop.set()
                if heartbeat_thread is not None:
                    heartbeat_thread.join(timeout=max(1.0, heartbeat_interval * 2))
                self.set_active_kernel("stage_boundary_after")
                after = self.checkpoint(
                    stage=stage, current_kernel="stage_boundary_after"
                )
                if stage == "parser_observation_projection":
                    handle.observe(
                        measures=after["resources"],
                        details={
                            "current_kernel": "stage_boundary_after",
                            "partial_timing": after["partial_timing"],
                        },
                    )


class _GuardedStageHandle:
    """Forward a phase handle while making owner observations durable."""

    def __init__(
        self,
        handle: Any,
        guard: ActiveDocumentResourceGuard,
        stage: str,
    ) -> None:
        self._handle = handle
        self._guard = guard
        self._stage = stage
        self.active_stage = getattr(handle, "active_stage", stage)

    def observe(self, **values: Any) -> None:
        self._handle.observe(**values)
        details = values.get("details")
        details_mapping = details if isinstance(details, Mapping) else {}
        current_kernel = str(
            details_mapping.get("current_kernel")
            or values.get("current_kernel")
            or self._guard.active_kernel()
        )
        self._guard.set_active_kernel(current_kernel)
        persisted_counts = {
            str(key): int(value)
            for key, value in details_mapping.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
        self._guard.checkpoint(
            stage=self._stage,
            current_kernel=current_kernel,
            persisted_counts=persisted_counts,
            enforce_limits=False,
        )


class GuardedDocumentProgress:
    """Inject the shared guard into an existing progress sink's stage lifecycle."""

    def __init__(self, progress: Any, guard: ActiveDocumentResourceGuard):
        self._progress = progress
        self._guard = guard

    @contextmanager
    def stage(self, stage: str, **kwargs: Any) -> Iterator[Any]:
        with self._guard.stage(self._progress, stage, **kwargs) as handle:
            yield _GuardedStageHandle(handle, self._guard, stage)

    def observe(self, details: Mapping[str, Any]) -> None:
        current_kernel = str(details.get("current_kernel") or "numeric_pnf_compilation")
        self._guard.set_active_kernel(current_kernel)
        persisted_counts = {
            str(key): int(value)
            for key, value in details.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
        self._guard.checkpoint(
            stage="numeric_pnf_compilation",
            current_kernel=current_kernel,
            persisted_counts=persisted_counts,
            enforce_limits=False,
        )


class NullDocumentProgress:
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
    "PARTIAL_TIMING_SCHEMA_VERSION",
    "current_process_tree_rss_bytes",
]
