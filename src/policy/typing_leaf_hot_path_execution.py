"""Bounded-window execution for process-backed semantic typing leaves.

The original leaf executor computed each immutable input digest/leaf reference
once while checking the cache and again after worker completion, then submitted
*all* cache misses to ``ProcessPoolExecutor`` at once.  Large inputs therefore
created an unbounded pending-future/pickled-payload frontier despite using bounded
logical leaves.

This strategy precomputes each physical leaf descriptor once and keeps at most
``2 * process_workers`` missing leaves submitted concurrently.  Output merge
order, checkpoint format, leaf identity, hierarchy identity and semantic results
are unchanged.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, wait
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


_INSTALL_MARKER = "_typing_leaf_hot_path_execution_installed"


def execute_leaves_bounded(
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
    descriptors: list[tuple[str, str, Any]] = []
    missing: list[int] = []

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
        descriptors.append((input_digest, leaf_ref, path))
        cached = tail._load_leaf(
            path,
            leaf_ref=leaf_ref,
            input_digest=input_digest,
        )
        if cached is None:
            missing.append(ordinal)
        else:
            leaves[ordinal] = {**cached, "reused": True}

    started = monotonic_ns()
    executor = tail._pool()
    newly_completed = 0
    stop_after = tail._integer_env(
        "SENSIBLAW_TYPING_TAIL_STOP_AFTER_LEAVES",
        0,
        minimum=0,
    )

    def accept(ordinal: int, worker_result: Mapping[str, Any]) -> None:
        nonlocal newly_completed
        input_digest, leaf_ref, path = descriptors[ordinal]
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
        if path is not None:
            tail._atomic_write_json(path, payload)
        leaves[ordinal] = payload
        newly_completed += 1
        output_items = len(value) if hasattr(value, "__len__") else 1
        context.sample(
            f"local_typing_diagnostics:{operation}",
            phase="typing_leaf_completed",
            counts={"leaf_ordinal": ordinal, "output_items": output_items},
            details={
                "leaf_ref": leaf_ref,
                "worker_pid": payload["worker_pid"],
                "process_backed": executor is not None,
                "bounded_submission_window": True,
            },
        )
        if stop_after and newly_completed >= stop_after:
            raise RuntimeError(
                f"stopped after {newly_completed} checkpointed typing-tail leaves"
            )

    if executor is None:
        for ordinal in missing:
            accept(ordinal, worker(payloads[ordinal]))
    else:
        worker_count = max(1, tail._process_workers())
        window = max(1, 2 * worker_count)
        next_missing = 0
        pending: dict[Any, int] = {}
        max_pending = 0

        while next_missing < len(missing) or pending:
            while next_missing < len(missing) and len(pending) < window:
                ordinal = missing[next_missing]
                pending[executor.submit(worker, payloads[ordinal])] = ordinal
                next_missing += 1
                max_pending = max(max_pending, len(pending))
            if not pending:
                continue
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                ordinal = pending.pop(future)
                accept(ordinal, future.result())

        context.closure_counters[
            f"typing_leaf_max_pending:{operation}"
        ] = max_pending
        context.closure_counters[
            f"typing_leaf_submission_window:{operation}"
        ] = window

    completed_rows = [row for row in leaves if row is not None]
    if len(completed_rows) != len(payloads):
        raise RuntimeError("typing leaf execution ended without complete coverage")
    output = merge([row["value"] for row in completed_rows])
    receipt = tail._hierarchy_receipt(
        operation=operation,
        identity=identity,
        leaves=completed_rows,
        output_value=output,
        arity=context.hierarchy_arity,
    )
    receipt["elapsed_ns"] = monotonic_ns() - started
    receipt["complexity"] = {
        "input_leaf_count": len(payloads),
        "document_rescan_per_leaf": False,
        "identity_hashes_per_leaf": 1,
        "bounded_submission_window": True,
        "target": "O(inputs + outputs + hierarchy_interfaces)",
    }
    context.typing_receipts[operation] = receipt
    return output, receipt


def install_typing_leaf_hot_path_execution() -> bool:
    from src.policy import parallel_typing_tail as tail

    if getattr(tail, _INSTALL_MARKER, False):
        return False
    tail._execute_leaves = execute_leaves_bounded
    setattr(tail, _INSTALL_MARKER, True)
    return True


__all__ = [
    "execute_leaves_bounded",
    "install_typing_leaf_hot_path_execution",
]
