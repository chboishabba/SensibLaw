"""End-to-end progress envelopes for bounded semantic execution.

This module changes no semantic identity or reduction rule. It hardens the
physical execution surface so parent stages roll up child completion as work
finishes, durable progress mirrors emitted logs, and waits name the dependency
that can make progress.
"""

from __future__ import annotations

from concurrent.futures import Future, wait, FIRST_COMPLETED
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256

PROGRESS_ENVELOPE_SCHEMA_VERSION = "sensiblaw.progress-envelope.v1"
_INSTALL_MARKER = "_progress_observability_execution_installed"
_DEFAULT_WAIT_HEARTBEAT_SECONDS = 30


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _integer_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _safe_ref(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in value
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)
    return len(encoded.encode("utf-8"))


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
    return len(encoded.encode("utf-8"))


def _checkpoint_bytes(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _universal_envelope(
    *,
    context: Any,
    stage: str,
    phase: str,
    counts: Mapping[str, int] | None,
    details: Mapping[str, Any] | None,
    resource_row: Mapping[str, Any],
    elapsed_ns: int | None,
) -> dict[str, Any]:
    count_values = dict(counts or {})
    detail_values = dict(details or {})
    completed = int(
        count_values.get("leaves_completed")
        or count_values.get("jobs_completed")
        or count_values.get("completed")
        or 0
    )
    total_raw = (
        count_values.get("leaves_total")
        or count_values.get("jobs_total")
        or count_values.get("total")
    )
    total = int(total_raw) if total_raw is not None else None
    envelope = {
        "schema_version": PROGRESS_ENVELOPE_SCHEMA_VERSION,
        "run_ref": context.run_ref,
        "document_ref": context.document_ref,
        "stage": stage,
        "phase": phase,
        "observed_at": _utc_now(),
        "completed": completed,
        "total": total,
        "current_work_key": detail_values.get("current_work_key")
        or detail_values.get("leaf_ref")
        or detail_values.get("job_ref"),
        "last_completion_at": detail_values.get("last_completion_at"),
        "batch_size": int(detail_values.get("batch_size") or 0),
        "checkpoint_bytes_written": int(
            detail_values.get("checkpoint_bytes_written") or 0
        ),
        "checkpoint_bytes_reused": int(
            detail_values.get("checkpoint_bytes_reused") or 0
        ),
        "queue_count": int(
            count_values.get("queue_count")
            or count_values.get("pending_jobs")
            or 0
        ),
        "in_flight_count": int(
            count_values.get("in_flight_count")
            or count_values.get("in_flight_jobs")
            or 0
        ),
        "active_workers": int(detail_values.get("active_workers") or 0),
        "wait_reason": detail_values.get("wait_reason"),
        "wait_dependency": detail_values.get("wait_dependency"),
        "wait_elapsed_ns": int(detail_values.get("wait_elapsed_ns") or 0),
        "rss_bytes": int(resource_row.get("rss_bytes") or 0),
        "pss_bytes": int(resource_row.get("pss_bytes") or 0),
        "uss_bytes": int(resource_row.get("uss_bytes") or 0),
        "retained_object_delta": int(
            detail_values.get("retained_object_delta") or 0
        ),
        "elapsed_ns": elapsed_ns,
        "counts": dict(sorted(count_values.items())),
        "details": detail_values,
    }
    return {key: value for key, value in envelope.items() if value is not None}


def _persist_and_log(context: Any, envelope: Mapping[str, Any]) -> None:
    root = context.checkpoint_root
    if root is not None:
        progress_root = Path(root) / "progress"
        _atomic_json(progress_root / "latest.json", envelope)
        _append_jsonl(progress_root / "events.jsonl", envelope)
    print(
        "SENSIBLAW_PROGRESS "
        + json.dumps(dict(envelope), ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def _enhanced_execute_leaves(
    *,
    operation: str,
    context: Any,
    payloads: Sequence[Mapping[str, Any]],
    input_identities: Sequence[Mapping[str, Any]],
    worker: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    merge: Callable[[Sequence[Any]], Any],
) -> tuple[Any, dict[str, Any]]:
    from src.policy import parallel_typing_tail as tail

    if len(payloads) != len(input_identities):
        raise ValueError("typing leaf payload and identity counts disagree")
    root = context.typing_checkpoint_root
    identity = context.typing_identity.to_dict()
    leaves: list[dict[str, Any] | None] = [None] * len(payloads)
    missing: list[int] = []
    reused_bytes = 0
    for ordinal, input_identity in enumerate(input_identities):
        input_digest = canonical_sha256(
            {
                "operation": operation,
                "identity": identity,
                "ordinal": ordinal,
                "input": dict(input_identity),
            }
        )
        leaf_ref = "typing-leaf:" + canonical_sha256(
            {"operation": operation, "input_digest": input_digest}
        )
        path = tail._leaf_path(root, operation, leaf_ref)
        cached = tail._load_leaf(
            path,
            leaf_ref=leaf_ref,
            input_digest=input_digest,
        )
        if cached is None:
            missing.append(ordinal)
        else:
            leaves[ordinal] = {**cached, "reused": True}
            reused_bytes += _checkpoint_bytes(path)

    started = monotonic_ns()
    total = len(payloads)
    reused_count = total - len(missing)
    completed_count = reused_count
    completed_output_items = sum(
        len(row["value"]) if hasattr(row["value"], "__len__") else 1
        for row in leaves
        if row is not None
    )
    active_worker_pids = {
        int(row.get("worker_pid") or 0)
        for row in leaves
        if row is not None and row.get("worker_pid")
    }
    last_completion_at = _utc_now() if reused_count else None
    context.sample(
        f"local_typing_diagnostics:{operation}",
        phase="typing_parent_started",
        counts={
            "leaves_completed": completed_count,
            "leaves_total": total,
            "leaves_reused": reused_count,
            "leaves_missing": len(missing),
            "output_items_completed": completed_output_items,
        },
        details={
            "batch_size": context.leaf_capacity,
            "checkpoint_bytes_reused": reused_bytes,
            "active_workers": len(active_worker_pids),
            "last_completion_at": last_completion_at,
            "wait_reason": "worker_results" if missing else None,
            "wait_dependency": operation if missing else None,
        },
    )

    executor = tail._pool()
    newly_completed = 0
    bytes_written = 0
    stop_after = tail._integer_env(
        "SENSIBLAW_TYPING_TAIL_STOP_AFTER_LEAVES", 0, minimum=0
    )

    def admit_result(ordinal: int, worker_result: Mapping[str, Any]) -> None:
        nonlocal newly_completed, completed_count, completed_output_items
        nonlocal bytes_written, last_completion_at
        input_identity = input_identities[ordinal]
        input_digest = canonical_sha256(
            {
                "operation": operation,
                "identity": identity,
                "ordinal": ordinal,
                "input": dict(input_identity),
            }
        )
        leaf_ref = "typing-leaf:" + canonical_sha256(
            {"operation": operation, "input_digest": input_digest}
        )
        value = worker_result["value"]
        payload = {
            "schema_version": tail.TAIL_LEAF_SCHEMA_VERSION,
            "leaf_ref": leaf_ref,
            "operation": operation,
            "ordinal": ordinal,
            "identity": identity,
            "input_digest": input_digest,
            "output_digest": canonical_sha256(value),
            "value": value,
            "worker_pid": int(worker_result["pid"]),
            "reused": False,
            "semantic_authority": "document_fibre_only",
        }
        path = tail._leaf_path(root, operation, leaf_ref)
        if path is not None:
            tail._atomic_write_json(path, payload)
            bytes_written += _checkpoint_bytes(path)
        leaves[ordinal] = payload
        newly_completed += 1
        completed_count += 1
        output_items = len(value) if hasattr(value, "__len__") else 1
        completed_output_items += output_items
        active_worker_pids.add(int(payload["worker_pid"]))
        last_completion_at = _utc_now()
        context.sample(
            f"local_typing_diagnostics:{operation}",
            phase="typing_leaf_completed",
            counts={
                "leaves_completed": completed_count,
                "leaves_total": total,
                "leaves_reused": reused_count,
                "output_items_completed": completed_output_items,
                "leaf_ordinal": ordinal,
                "output_items": output_items,
                "queue_count": max(0, total - completed_count),
                "in_flight_count": max(0, len(missing) - newly_completed),
            },
            details={
                "leaf_ref": leaf_ref,
                "current_work_key": leaf_ref,
                "worker_pid": payload["worker_pid"],
                "active_workers": len(active_worker_pids),
                "process_backed": executor is not None,
                "batch_size": len(payloads[ordinal]),
                "checkpoint_bytes_written": bytes_written,
                "checkpoint_bytes_reused": reused_bytes,
                "last_completion_at": last_completion_at,
            },
        )
        if stop_after and newly_completed >= stop_after:
            raise RuntimeError(
                f"stopped after {newly_completed} checkpointed typing-tail leaves"
            )

    if executor is None:
        for ordinal in missing:
            admit_result(ordinal, worker(payloads[ordinal]))
    else:
        futures: dict[Future[Mapping[str, Any]], int] = {
            executor.submit(worker, payloads[ordinal]): ordinal for ordinal in missing
        }
        pending = set(futures)
        wait_started = monotonic_ns()
        heartbeat_seconds = _integer_env(
            "SENSIBLAW_PROGRESS_WAIT_HEARTBEAT_SECONDS",
            _DEFAULT_WAIT_HEARTBEAT_SECONDS,
        )
        while pending:
            done, pending = wait(
                pending,
                timeout=heartbeat_seconds,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                context.sample(
                    f"local_typing_diagnostics:{operation}",
                    phase="typing_parent_waiting",
                    counts={
                        "leaves_completed": completed_count,
                        "leaves_total": total,
                        "queue_count": len(pending),
                        "in_flight_count": len(pending),
                        "output_items_completed": completed_output_items,
                    },
                    details={
                        "active_workers": max(1, min(len(pending), tail._POOL_WORKERS)),
                        "wait_reason": "worker_results",
                        "wait_dependency": operation,
                        "wait_elapsed_ns": monotonic_ns() - wait_started,
                        "last_completion_at": last_completion_at,
                        "checkpoint_bytes_written": bytes_written,
                        "checkpoint_bytes_reused": reused_bytes,
                    },
                )
                continue
            wait_started = monotonic_ns()
            for future in done:
                admit_result(futures[future], future.result())

    completed = [row for row in leaves if row is not None]
    if len(completed) != total:
        raise RuntimeError("typing leaf execution ended without complete coverage")

    merge_started = monotonic_ns()
    context.sample(
        f"local_typing_diagnostics:{operation}",
        phase="typing_parent_aggregation_started",
        counts={
            "leaves_completed": completed_count,
            "leaves_total": total,
            "output_items_completed": completed_output_items,
        },
        details={
            "current_work_key": f"typing-aggregation:{operation}",
            "active_workers": 1,
            "last_completion_at": last_completion_at,
            "checkpoint_bytes_written": bytes_written,
            "checkpoint_bytes_reused": reused_bytes,
        },
    )
    output = merge([row["value"] for row in completed])
    output_count = len(output) if hasattr(output, "__len__") else 1
    receipt = tail._hierarchy_receipt(
        operation=operation,
        identity=identity,
        leaves=completed,
        output_value=output,
        arity=context.hierarchy_arity,
    )
    receipt["elapsed_ns"] = monotonic_ns() - started
    receipt["aggregation_elapsed_ns"] = monotonic_ns() - merge_started
    receipt["checkpoint_bytes_written"] = bytes_written
    receipt["checkpoint_bytes_reused"] = reused_bytes
    receipt["last_completion_at"] = last_completion_at
    receipt["complexity"] = {
        "input_leaf_count": total,
        "document_rescan_per_leaf": False,
        "target": "O(inputs + outputs + hierarchy_interfaces)",
    }
    context.typing_receipts[operation] = receipt
    context.sample(
        f"local_typing_diagnostics:{operation}",
        phase="typing_parent_aggregation_completed",
        counts={
            "leaves_completed": completed_count,
            "leaves_total": total,
            "output_items_completed": completed_output_items,
            "parent_output_items": output_count,
        },
        details={
            "current_work_key": receipt["root_graph_ref"],
            "active_workers": 0,
            "last_completion_at": _utc_now(),
            "checkpoint_bytes_written": bytes_written,
            "checkpoint_bytes_reused": reused_bytes,
            "logical_typing_ref": receipt["logical_typing_ref"],
        },
        elapsed_ns=monotonic_ns() - merge_started,
    )
    return output, receipt


def install_progress_observability_execution() -> bool:
    """Install universal envelopes and live typing parent/child roll-up."""

    from src.policy import parallel_semantic_execution as semantic
    from src.policy import parallel_typing_tail as tail

    if getattr(semantic, _INSTALL_MARKER, False):
        return False
    original_sample = semantic.SemanticExecutionContext.sample

    def sample(self: Any, stage: str, **kwargs: Any) -> dict[str, Any]:
        row = original_sample(self, stage, **kwargs)
        envelope = _universal_envelope(
            context=self,
            stage=stage,
            phase=str(kwargs["phase"]),
            counts=kwargs.get("counts"),
            details=kwargs.get("details"),
            resource_row=row,
            elapsed_ns=kwargs.get("elapsed_ns"),
        )
        row["progress_envelope"] = envelope
        _persist_and_log(self, envelope)
        return row

    semantic.SemanticExecutionContext.sample = sample
    tail._serial_execute_leaves = tail._execute_leaves
    tail._execute_leaves = _enhanced_execute_leaves
    setattr(semantic, _INSTALL_MARKER, True)
    return True


__all__ = [
    "PROGRESS_ENVELOPE_SCHEMA_VERSION",
    "install_progress_observability_execution",
]
