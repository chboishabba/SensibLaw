"""Install binary-only semantic checkpoint and progress persistence.

The semantic execution modules predate the repository-wide JSON prohibition.
This policy replaces their physical readers, writers, path constructors, and
progress sink before any document work begins. Semantic functions and identities
remain unchanged; no active checkpoint or heartbeat is text-serialized.
"""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import pickle
import sys
from time import monotonic_ns
from typing import Any, Mapping


_INSTALL_MARKER = "_no_json_checkpoint_execution_installed"
_PROGRESS_MODES = {"full", "batched", "disabled"}
_progress_buffers: dict[Path, dict[str, Any]] = {}
_progress_roots: set[Path] = set()
_progress_metrics: dict[str, int] = {
    "binary_bytes_written": 0,
    "binary_fsync_count": 0,
    "binary_fsync_elapsed_ns": 0,
    "binary_persistence_elapsed_ns": 0,
    "progress_events": 0,
    "progress_events_persisted": 0,
    "progress_events_disabled": 0,
    "progress_flushes": 0,
    "progress_atomic_writes": 0,
    "progress_frame_appends": 0,
    "progress_bytes_written": 0,
    "progress_bytes_buffered": 0,
    "progress_fsync_count": 0,
    "progress_fsync_elapsed_ns": 0,
    "progress_persistence_elapsed_ns": 0,
}


def _progress_mode() -> str:
    value = (
        os.environ.get("SENSIBLAW_PROGRESS_PERSISTENCE_MODE", "full").strip().lower()
    )
    if value not in _PROGRESS_MODES:
        raise ValueError(
            "SENSIBLAW_PROGRESS_PERSISTENCE_MODE must be one of: "
            + ", ".join(sorted(_PROGRESS_MODES))
        )
    return value


def _positive_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_float_env(name: str, default: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _record_metric(name: str, value: int = 1) -> None:
    _progress_metrics[name] = _progress_metrics.get(name, 0) + value


def _fsync(handle: Any) -> None:
    started = monotonic_ns()
    os.fsync(handle.fileno())
    _record_metric("binary_fsync_count")
    _record_metric("binary_fsync_elapsed_ns", monotonic_ns() - started)


def _encoded_frame(payload: Mapping[str, Any]) -> bytes:
    encoded = pickle.dumps(dict(payload), protocol=5)
    return len(encoded).to_bytes(8, "big") + encoded


def _atomic_write_binary(path: Path, payload: Mapping[str, Any]) -> int:
    started = monotonic_ns()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = pickle.dumps(dict(payload), protocol=5)
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        _fsync(handle)
    temporary.replace(path)
    _record_metric("binary_bytes_written", len(encoded))
    _record_metric("binary_persistence_elapsed_ns", monotonic_ns() - started)
    return len(encoded)


def _append_binary_frame(path: Path, payload: Mapping[str, Any]) -> int:
    started = monotonic_ns()
    fsync_count_before = _progress_metrics["binary_fsync_count"]
    fsync_elapsed_before = _progress_metrics["binary_fsync_elapsed_ns"]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = _encoded_frame(payload)
    with path.open("ab") as stream:
        stream.write(frame)
        stream.flush()
        _fsync(stream)
    _record_metric("progress_frame_appends")
    _record_metric("progress_events_persisted")
    _record_metric("progress_bytes_written", len(frame))
    _record_metric(
        "progress_fsync_count",
        _progress_metrics["binary_fsync_count"] - fsync_count_before,
    )
    _record_metric(
        "progress_fsync_elapsed_ns",
        _progress_metrics["binary_fsync_elapsed_ns"] - fsync_elapsed_before,
    )
    _record_metric("progress_persistence_elapsed_ns", monotonic_ns() - started)
    return len(frame)


def _flush_progress(root: Path) -> None:
    buffered = _progress_buffers.pop(root, None)
    if not buffered:
        return
    started = monotonic_ns()
    progress_root = root / "progress"
    latest = buffered["latest"]
    fsync_count_before = _progress_metrics["binary_fsync_count"]
    fsync_elapsed_before = _progress_metrics["binary_fsync_elapsed_ns"]
    latest_bytes = _atomic_write_binary(progress_root / "latest.pkl", latest)
    _record_metric("progress_atomic_writes")
    _record_metric("progress_bytes_written", latest_bytes)
    _record_metric(
        "progress_fsync_count",
        _progress_metrics["binary_fsync_count"] - fsync_count_before,
    )
    _record_metric(
        "progress_fsync_elapsed_ns",
        _progress_metrics["binary_fsync_elapsed_ns"] - fsync_elapsed_before,
    )
    frames = buffered["frames"]
    if frames:
        progress_root.mkdir(parents=True, exist_ok=True)
        fsync_count_before = _progress_metrics["binary_fsync_count"]
        fsync_elapsed_before = _progress_metrics["binary_fsync_elapsed_ns"]
        with (progress_root / "events.bin").open("ab") as stream:
            stream.write(b"".join(frames))
            stream.flush()
            _fsync(stream)
        _record_metric(
            "progress_fsync_count",
            _progress_metrics["binary_fsync_count"] - fsync_count_before,
        )
        _record_metric(
            "progress_fsync_elapsed_ns",
            _progress_metrics["binary_fsync_elapsed_ns"] - fsync_elapsed_before,
        )
        _record_metric("progress_frame_appends", len(frames))
        _record_metric("progress_events_persisted", len(frames))
        _record_metric("progress_bytes_written", sum(map(len, frames)))
    _record_metric("progress_flushes")
    _record_metric("progress_persistence_elapsed_ns", monotonic_ns() - started)


def _flush_all_progress() -> None:
    for root in tuple(_progress_buffers):
        _flush_progress(root)


def _write_progress_metrics(root: Path) -> None:
    progress_root = root / "progress"
    progress_root.mkdir(parents=True, exist_ok=True)
    temporary = progress_root / "metrics.pkl.tmp"
    temporary.write_bytes(pickle.dumps(dict(_progress_metrics), protocol=5))
    temporary.replace(progress_root / "metrics.pkl")


def progress_persistence_metrics() -> dict[str, int]:
    """Return a snapshot of diagnostic progress-persistence counters."""

    return dict(_progress_metrics)


def _read_binary(path: Path) -> dict[str, Any] | None:
    try:
        value = pickle.loads(path.read_bytes())
    except (OSError, EOFError, pickle.PickleError, AttributeError, ValueError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _safe_ref(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in value
    )


def _progress_line(envelope: Mapping[str, Any]) -> str:
    fields = (
        "run_ref",
        "document_ref",
        "stage",
        "phase",
        "completed",
        "total",
        "current_work_key",
        "queue_count",
        "in_flight_count",
        "active_workers",
        "wait_reason",
        "wait_dependency",
        "rss_bytes",
        "pss_bytes",
        "uss_bytes",
    )
    parts = [
        f"{field}={envelope[field]}"
        for field in fields
        if envelope.get(field) is not None
    ]
    return "SENSIBLAW_PROGRESS " + " ".join(parts)


def install_no_json_checkpoint_execution() -> bool:
    from src.policy import parallel_semantic_execution as semantic
    from src.policy import parallel_typing_tail as typing_tail
    from src.policy import progress_observability_execution as progress

    if getattr(semantic, _INSTALL_MARKER, False):
        return False

    semantic._atomic_write_json = _atomic_write_binary
    semantic._read_json = _read_binary

    def closure_handoff_checkpoint_path(self: Any) -> Path | None:
        root = self.closure_activation_checkpoint_root
        return None if root is None else root / f"handoff-{self.build_key_sha256}.pkl"

    def closure_receipt_path(self: Any, job_ref: str) -> Path | None:
        root = self.closure_checkpoint_root
        return None if root is None else root / f"{_safe_ref(job_ref)}.pkl"

    def activation_leaf_path(root: Path | None, leaf_ref: str) -> Path | None:
        return None if root is None else root / f"{_safe_ref(leaf_ref)}.pkl"

    def replay_artifact_path(context: Any, artifact_ref: str) -> Path | None:
        root = context.closure_replay_artifact_root
        return None if root is None else root / f"{_safe_ref(artifact_ref)}.pkl"

    def write_receipts(self: Any) -> None:
        if self.checkpoint_root is None:
            return
        closure = semantic.closure_amplification_report(self.closure_counters)
        receipt = {
            "schema_version": semantic.SEMANTIC_EXECUTION_SCHEMA_VERSION,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "parser_contract_ref": self.parser_contract_ref,
            "build_key_sha256": self.build_key_sha256,
            "typing_contract_ref": semantic.TYPING_EXECUTION_CONTRACT,
            "closure_replay_contract_ref": semantic.CLOSURE_REPLAY_CONTRACT,
            "closure_activation_contract_ref": semantic.CLOSURE_ACTIVATION_CONTRACT,
            "configuration": {
                "typing_workers": self.typing_workers,
                "typing_leaf_capacity": self.leaf_capacity,
                "hierarchy_arity": self.hierarchy_arity,
                "closure_activation_leaf_size": self.closure_activation_leaf_size,
            },
            "state": self.state,
            "error": self.error,
            "kernel_timeline": list(self.kernel_timeline),
            "typing_hierarchies": dict(sorted(self.typing_receipts.items())),
            "closure_audit": {
                "events": list(self.closure_events),
                "activation": dict(self.closure_activation),
                **closure,
            },
            "amplification": dict(self.amplification),
            "semantic_authority": "one_document",
            "partition_semantic_effect": "none",
            "text_serialization": False,
        }
        _atomic_write_binary(
            self.checkpoint_root / "semantic-execution-receipt.pkl",
            receipt,
        )
        _atomic_write_binary(
            self.checkpoint_root / "semantic-amplification-report.pkl",
            {
                "schema_version": "sensiblaw.semantic-amplification-report.v2",
                "document_ref": self.document_ref,
                **dict(self.amplification),
                "closure": closure,
                "text_serialization": False,
            },
        )

    semantic.SemanticExecutionContext.closure_handoff_checkpoint_path = property(
        closure_handoff_checkpoint_path
    )
    semantic.SemanticExecutionContext.closure_receipt_path = closure_receipt_path
    semantic.SemanticExecutionContext.write_receipts = write_receipts
    semantic._closure_activation_leaf_path = activation_leaf_path
    semantic._replay_artifact_path = replay_artifact_path

    typing_tail._atomic_write_json = _atomic_write_binary
    typing_tail._read_json = _read_binary

    def typing_leaf_path(
        root: Path | None, operation: str, leaf_ref: str
    ) -> Path | None:
        if root is None:
            return None
        return root / operation / f"{_safe_ref(leaf_ref)}.pkl"

    typing_tail._leaf_path = typing_leaf_path

    progress._atomic_json = _atomic_write_binary
    progress._append_jsonl = _append_binary_frame

    def persist_and_log(context: Any, envelope: Mapping[str, Any]) -> None:
        _record_metric("progress_events")
        root = context.checkpoint_root
        mode = _progress_mode()
        if root is not None:
            root = Path(root)
            _progress_roots.add(root)
        if root is not None and mode == "full":
            started = monotonic_ns()
            progress_root = root / "progress"
            fsync_count_before = _progress_metrics["binary_fsync_count"]
            fsync_elapsed_before = _progress_metrics["binary_fsync_elapsed_ns"]
            latest_bytes = _atomic_write_binary(progress_root / "latest.pkl", envelope)
            _record_metric("progress_atomic_writes")
            _record_metric("progress_bytes_written", latest_bytes)
            _record_metric(
                "progress_fsync_count",
                _progress_metrics["binary_fsync_count"] - fsync_count_before,
            )
            _record_metric(
                "progress_fsync_elapsed_ns",
                _progress_metrics["binary_fsync_elapsed_ns"] - fsync_elapsed_before,
            )
            _append_binary_frame(progress_root / "events.bin", envelope)
            _record_metric("progress_persistence_elapsed_ns", monotonic_ns() - started)
        elif root is not None and mode == "batched":
            state = _progress_buffers.setdefault(
                root,
                {"frames": [], "latest": envelope, "started_ns": monotonic_ns()},
            )
            frame = _encoded_frame(envelope)
            state["frames"].append(frame)
            state["latest"] = envelope
            _record_metric("progress_bytes_buffered", len(frame))
            event_limit = _positive_env("SENSIBLAW_PROGRESS_BATCH_EVENTS", 32)
            time_limit_ns = int(
                _positive_float_env("SENSIBLAW_PROGRESS_BATCH_SECONDS", 1.0)
                * 1_000_000_000
            )
            if (
                len(state["frames"]) >= event_limit
                or monotonic_ns() - int(state["started_ns"]) >= time_limit_ns
            ):
                _flush_progress(root)
        elif mode == "disabled":
            _record_metric("progress_events_disabled")
        print(_progress_line(envelope), file=sys.stderr, flush=True)

    progress._persist_and_log = persist_and_log
    atexit.register(
        lambda: [_write_progress_metrics(Path(root)) for root in tuple(_progress_roots)]
    )
    atexit.register(_flush_all_progress)
    setattr(semantic, _INSTALL_MARKER, True)
    return True


__all__ = ["install_no_json_checkpoint_execution", "progress_persistence_metrics"]
