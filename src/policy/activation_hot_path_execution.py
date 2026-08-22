"""Remove process IPC from non-semantic closure activation descriptors.

Activation leaves are execution checkpoints over already-existing immutable
``ObservationDelta`` objects.  The previous path sent each leaf to the semantic
process pool only to derive observation types/counts, checkpointed that tiny
value, and then admitted the *original* in-memory deltas.  No worker result was a
semantic input to owner admission.

This strategy preserves the same leaf identity/value/checkpoint contract but
computes that descriptor in the coordinator.  The process pool is therefore
reserved for actual closure and typing work.
"""

from __future__ import annotations

import os
from time import monotonic_ns
from typing import Any, Iterable, Iterator

from src.policy.carriers.canonical import canonical_bytes, canonical_sha256


_INSTALL_MARKER = "_activation_hot_path_execution_installed"


def _descriptor_value(chunk: tuple[Any, ...]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for delta in chunk:
        observations = tuple(delta.observations)
        observation_types = tuple(
            sorted(
                {
                    str(value.get("observation_type") or value.get("type_ref") or "")
                    for value in observations
                }
            )
        )
        prepared.append(
            {
                "delta_ref": delta.delta_ref,
                "sequence_no": delta.sequence_no,
                "observation_refs": tuple(delta.observation_refs),
                "observation_types": observation_types,
                "compact_operator_input": {
                    "scope_ref": delta.scope_ref,
                    "coverage_barrier": delta.coverage_barrier,
                    "coverage_complete": delta.coverage_complete,
                    "observation_count": len(observations),
                },
                "checkpoint_payload": {
                    "delta_ref": delta.delta_ref,
                    "sequence_no": delta.sequence_no,
                    "observation_refs": tuple(delta.observation_refs),
                },
            }
        )
    return prepared


def iter_coordinator_activation_leaves(
    *,
    context: Any,
    observation_deltas: Iterable[Any],
) -> Iterator[tuple[Any, ...]]:
    from src.policy import parallel_semantic_execution as parallel

    ordered = tuple(
        sorted(
            observation_deltas,
            key=lambda row: (int(row.sequence_no), row.delta_ref),
        )
    )
    size = context.closure_activation_leaf_size
    chunks = tuple(
        ordered[offset : offset + size]
        for offset in range(0, len(ordered), size)
    )
    started = monotonic_ns()
    completed_leaf_refs: list[str] = []
    admitted_leaf_refs: list[str] = []
    worker_pids: set[int] = set()
    computed = 0
    reused = 0
    input_bytes = 0
    output_bytes = 0
    max_leaf_bytes = 0

    context.closure_activation.update(
        {
            "contract_ref": parallel.CLOSURE_ACTIVATION_CONTRACT,
            "configured_leaf_size": size,
            "leaf_count": len(chunks),
            "admission_order": "sequence_no_delta_ref_ascending",
            "admitted_delta_count": int(
                context.closure_activation.get("reconstructed_admission_count") or 0
            ),
            "new_admission_count": 0,
            "duplicate_admission_count": 0,
            "admitted_batch_refs": (),
            "first_owner_admission_latency_ns": None,
            "first_ready_job_latency_ns": None,
            "owner_admission_started_immediately": False,
            "ready_job_count": 0,
            "admission_elapsed_ns": 0,
            "buffer_limit_leaves": 1,
            "activation_descriptor_process_backed": False,
        }
    )

    for ordinal, chunk in enumerate(chunks):
        input_identity = [
            [int(delta.sequence_no), delta.delta_ref]
            for delta in chunk
        ]
        input_digest = canonical_sha256(input_identity)
        leaf_ref = "closure-activation:" + canonical_sha256(
            {"ordinal": ordinal, "input_digest": input_digest}
        )
        path = parallel._closure_activation_leaf_path(
            context.closure_activation_checkpoint_root,
            leaf_ref,
        )
        cached = parallel._load_closure_activation_leaf(
            path,
            leaf_ref=leaf_ref,
            input_identity=input_identity,
            input_digest=input_digest,
        )
        if cached is None:
            value = _descriptor_value(chunk)
            pid = os.getpid()
            leaf = {
                "schema_version": parallel.CLOSURE_ACTIVATION_LEAF_SCHEMA_VERSION,
                "contract_ref": parallel.CLOSURE_ACTIVATION_CONTRACT,
                "leaf_ref": leaf_ref,
                "input_identity": input_identity,
                "input_digest": input_digest,
                "value": value,
                "output_digest": canonical_sha256(value),
                "worker_pid": pid,
            }
            if path is not None:
                parallel._atomic_write_json(path, leaf)
            computed += 1
        else:
            leaf = cached
            value = cached.get("value") or ()
            pid = int(cached.get("worker_pid") or 0)
            reused += 1

        if pid:
            worker_pids.add(pid)
        completed_leaf_refs.append(leaf_ref)
        admitted_leaf_refs.append(leaf_ref)
        encoded_input = len(canonical_bytes(input_identity))
        encoded_output = len(canonical_bytes(value))
        input_bytes += encoded_input
        output_bytes += encoded_output
        max_leaf_bytes = max(max_leaf_bytes, encoded_output)

        context.closure_activation_completed_ns = monotonic_ns()
        context.closure_activation.update(
            {
                "next_leaf_ordinal": ordinal + 1,
                "completed_leaf_refs": tuple(completed_leaf_refs),
                "buffered_leaf_refs": (),
                "admitted_leaf_refs": tuple(admitted_leaf_refs),
                "max_buffered_leaves": 1 if chunks else 0,
                "max_buffered_bytes": max_leaf_bytes,
            }
        )
        parallel._write_closure_handoff_checkpoint(context)

        stop_after = parallel._integer_env(
            "SENSIBLAW_CLOSURE_ACTIVATION_STOP_AFTER_LEAVES",
            0,
            minimum=0,
        )
        if stop_after and computed >= stop_after:
            raise RuntimeError(
                f"stopped after {computed} checkpointed closure activation leaves"
            )
        stop_after_completion = parallel._integer_env(
            "SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION",
            0,
            minimum=0,
        )
        if stop_after_completion and len(admitted_leaf_refs) >= stop_after_completion:
            raise RuntimeError("stopped after closure activation completion checkpoint")
        yield chunk

    elapsed_ns = monotonic_ns() - started
    context.closure_activation.update(
        {
            "computed_leaf_count": computed,
            "reused_leaf_count": reused,
            "worker_pids": sorted(worker_pids),
            "computed_worker_pids": [os.getpid()] if computed else [],
            "reused_worker_pids": sorted(worker_pids) if reused else [],
            "activation_elapsed_ns": elapsed_ns,
            "max_buffered_leaves": 1 if chunks else 0,
            "buffer_limit_leaves": 1,
            "max_buffered_bytes": max_leaf_bytes,
            "head_of_line_wait_ns": 0,
            "activation_input_bytes": input_bytes,
            "activation_output_bytes": output_bytes,
            "completed_leaf_refs": tuple(completed_leaf_refs),
            "admitted_leaf_refs": tuple(admitted_leaf_refs),
            "buffered_leaf_refs": (),
            "next_leaf_ordinal": len(chunks),
            "activation_descriptor_process_backed": False,
        }
    )
    parallel._write_closure_handoff_checkpoint(context)
    with context.lock:
        context.closure_counters["activation_leaf_count"] = len(chunks)
        context.closure_counters["activation_leaves_computed"] = computed
        context.closure_counters["activation_leaves_reused"] = reused
        context.closure_counters["activation_process_submissions_avoided"] += computed
    context.sample(
        "activation_result_collection",
        phase="closure_activation_completed",
        counts={
            "leaf_count": len(chunks),
            "computed_leaf_count": computed,
            "reused_leaf_count": reused,
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "max_buffered_bytes": max_leaf_bytes,
        },
        details=dict(context.closure_activation),
        elapsed_ns=elapsed_ns,
    )


def install_activation_hot_path_execution() -> bool:
    from src.policy import parallel_semantic_execution as parallel

    if getattr(parallel, _INSTALL_MARKER, False):
        return False
    parallel.iter_closure_activation_leaves = iter_coordinator_activation_leaves
    setattr(parallel, _INSTALL_MARKER, True)
    return True


__all__ = [
    "install_activation_hot_path_execution",
    "iter_coordinator_activation_leaves",
]
