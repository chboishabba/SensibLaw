"""Install PostgreSQL-authoritative durability for bounded typing leaves.

Semantic functions remain unchanged. This policy enriches physical leaf
payloads with deterministic work identities and replaces only worker adapters.
Each child leases and commits its result before reporting success to the parent.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.runtime.durable_stage_state import (
    commit_stage_manifest,
    record_stage_failure,
)
from src.runtime.durable_work_item_hardening import (
    complete_leased_work,
    lease_registered_work,
)
from src.runtime.durable_work_items import (
    DurableWorkSpec,
    linux_parent_death_initializer,
    load_completed_work,
    register_work_items,
)


_INSTALL_MARKER = "_durable_work_item_execution_installed"
TYPING_STAGE_CONTRACT = "postgres-durable-typing-leaf:v1"


def _enabled() -> bool:
    value = os.environ.get("SENSIBLAW_DURABLE_WORK_ITEMS", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _spec(payload: Mapping[str, Any]) -> DurableWorkSpec | None:
    value = payload.get("__durable_work__")
    return DurableWorkSpec.from_dict(value) if isinstance(value, Mapping) else None


def _execute_and_commit(
    payload: Mapping[str, Any],
    compute: Callable[[Mapping[str, Any]], Any],
) -> dict[str, Any]:
    spec = _spec(payload)
    if spec is None:
        return {"pid": os.getpid(), "value": compute(payload), "durable": False}
    lease = lease_registered_work(spec)
    if lease is None:
        cached = load_completed_work(spec)
        if cached is None:
            raise RuntimeError("durable work is leased elsewhere but has no committed result")
        return {
            "pid": os.getpid(),
            "value": cached,
            "durable": True,
            "reused": True,
            "work_ref": spec.work_ref,
        }
    value = compute(payload)
    receipt = complete_leased_work(lease, value, worker_pid=os.getpid())
    if receipt["admission_state"] == "stale":
        cached = load_completed_work(spec)
        if cached is None:
            raise RuntimeError("stale typing worker has no authoritative committed result")
        value = cached
    return {
        "pid": os.getpid(),
        "value": value,
        "durable": True,
        "reused": receipt["admission_state"] == "duplicate",
        "work_ref": spec.work_ref,
        "durable_receipt": receipt,
    }


def _derive_hypothesis_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    def compute(row: Mapping[str, Any]) -> Any:
        from src.language.semantic_reductions import derive_relational_type_hypotheses

        return list(
            derive_relational_type_hypotheses(
                bundle=row["bundle"],
                atom_mention_refs=row["atom_mention_refs"],
                declarations=row["declarations"],
            )
        )

    return _execute_and_commit(payload, compute)


def _local_typing_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    def compute(row: Mapping[str, Any]) -> Any:
        from src.policy.entity_resolution import build_local_typing_carrier

        return build_local_typing_carrier(
            mentions=row["mentions"],
            forms=row["forms"],
            typing_rules=row["typing_rules"],
            structural_hypotheses=row["structural_hypotheses"],
            authority=str(row.get("authority") or "candidate_only"),
        )

    return _execute_and_commit(payload, compute)


def _diagnostic_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    def compute(row: Mapping[str, Any]) -> Any:
        from src.language.semantic_reductions import diagnose_untyped_mentions

        return list(
            diagnose_untyped_mentions(
                mentions=row["mentions"],
                local_typing=row["local_typing"],
                bundle=row["bundle"],
                atom_mention_refs=row["atom_mention_refs"],
                parser_observation_refs=row["parser_observation_refs"],
                parser_capabilities=row["parser_capabilities"],
            )
        )

    return _execute_and_commit(payload, compute)


def _durable_pool() -> ProcessPoolExecutor | None:
    """Use direct spawn children so parent-death signalling targets coordinator."""

    from src.policy import parallel_typing_tail as tail

    workers = tail._process_workers()
    if workers <= 1:
        return None
    with tail._POOL_LOCK:
        if tail._POOL is None:
            tail._POOL = ProcessPoolExecutor(
                max_workers=workers,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=linux_parent_death_initializer,
            )
            tail._POOL_WORKERS = workers
        elif tail._POOL_WORKERS != workers:
            raise ValueError("semantic process worker count changed during one document")
        return tail._POOL


def _work_specs(
    *,
    operation: str,
    context: Any,
    input_identities: Sequence[Mapping[str, Any]],
) -> tuple[DurableWorkSpec, ...]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url or context.checkpoint_root is None:
        return ()
    identity = context.typing_identity.to_dict()
    artifact_root = Path(context.checkpoint_root) / "durable-artifacts" / "typing"
    return tuple(
        DurableWorkSpec(
            database_url=database_url,
            run_ref=context.run_ref,
            document_ref=context.document_ref,
            stage_contract_ref=TYPING_STAGE_CONTRACT,
            operation_ref=operation,
            partition_ref=f"typing:{operation}:{ordinal}",
            ordinal=ordinal,
            input_manifest={
                "stage_input_identity": identity,
                "operation": operation,
                "ordinal": ordinal,
                "leaf_input_identity": dict(input_identity),
            },
            artifact_root=artifact_root,
            worker_ref=f"{context.run_ref}:typing-worker",
        )
        for ordinal, input_identity in enumerate(input_identities)
    )


def install_durable_work_item_execution() -> bool:
    if not _enabled():
        return False

    from src.policy import parallel_typing_tail as tail

    if getattr(tail, _INSTALL_MARKER, False):
        return False

    original_execute = tail._execute_leaves

    def execute_leaves(
        *,
        operation: str,
        context: Any,
        payloads: Sequence[Mapping[str, Any]],
        input_identities: Sequence[Mapping[str, Any]],
        worker: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        merge: Callable[[Sequence[Any]], Any],
    ) -> tuple[Any, dict[str, Any]]:
        specs = _work_specs(
            operation=operation,
            context=context,
            input_identities=input_identities,
        )
        if not specs:
            return original_execute(
                operation=operation,
                context=context,
                payloads=payloads,
                input_identities=input_identities,
                worker=worker,
                merge=merge,
            )
        register_work_items(specs)
        enriched = tuple(
            {**dict(payload), "__durable_work__": spec.to_dict()}
            for payload, spec in zip(payloads, specs, strict=True)
        )
        worker_map = {
            tail._derive_hypothesis_worker: _derive_hypothesis_worker,
            tail._local_typing_worker: _local_typing_worker,
            tail._diagnostic_worker: _diagnostic_worker,
        }
        durable_worker = worker_map.get(worker, worker)
        try:
            output, receipt = original_execute(
                operation=operation,
                context=context,
                payloads=enriched,
                input_identities=input_identities,
                worker=durable_worker,
                merge=merge,
            )
        except Exception as error:
            record_stage_failure(
                specs[0].database_url,
                stage_instance_ref=specs[0].stage_instance_ref,
                error={"type": type(error).__name__, "message": str(error)},
            )
            raise
        manifest_ref = commit_stage_manifest(
            specs[0].database_url,
            stage_instance_ref=specs[0].stage_instance_ref,
            run_ref=context.run_ref,
            document_ref=context.document_ref,
            child_work_refs=[spec.work_ref for spec in specs],
            logical_output_ref=str(receipt["logical_typing_ref"]),
        )
        receipt["durable_work_contract_ref"] = TYPING_STAGE_CONTRACT
        receipt["durable_work_refs"] = [spec.work_ref for spec in specs]
        receipt["durable_stage_manifest_ref"] = manifest_ref
        receipt["durable_commit_before_parent_ack"] = True
        receipt["descendant_payload_bytes_reconstructed"] = 0
        receipt["recomputed_committed_work"] = 0
        return output, receipt

    tail._execute_leaves = execute_leaves
    tail._pool = _durable_pool
    tail._derive_hypothesis_worker = _derive_hypothesis_worker
    tail._local_typing_worker = _local_typing_worker
    tail._diagnostic_worker = _diagnostic_worker
    setattr(tail, _INSTALL_MARKER, True)
    return True


__all__ = [
    "TYPING_STAGE_CONTRACT",
    "install_durable_work_item_execution",
]
