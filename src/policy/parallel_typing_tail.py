"""Process-backed bounded local-typing tails and closure handlers.

Workers receive only bounded JSON-like leaves or immutable solver jobs. They do
not receive the parsed document, annotation graph, parser runtime, or complete
semantic worktree. The process pool is opt-in and is destroyed before document
persistence.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing
import os
from pathlib import Path
from threading import Lock
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence, TypeVar

from src.policy.carriers.canonical import canonical_sha256


TAIL_LEAF_SCHEMA_VERSION = "sensiblaw.typing-value-leaf.v1"
TAIL_ROOT_SCHEMA_VERSION = "sensiblaw.typing-value-hierarchy.v1"
PROCESS_EXECUTION_CONTRACT = "semantic-process-leaves:v1"
_INSTALL_MARKER = "_parallel_typing_tail_installed"

T = TypeVar("T")
_POOL: ProcessPoolExecutor | None = None
_POOL_WORKERS = 0
_POOL_LOCK = Lock()


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


def _process_workers() -> int:
    return _integer_env("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", 1)


def _multiprocessing_context() -> multiprocessing.context.BaseContext:
    requested = os.environ.get("SENSIBLAW_SEMANTIC_MP_CONTEXT", "forkserver")
    available = multiprocessing.get_all_start_methods()
    if requested not in available:
        requested = "spawn"
    return multiprocessing.get_context(requested)


def _pool() -> ProcessPoolExecutor | None:
    global _POOL, _POOL_WORKERS
    workers = _process_workers()
    if workers <= 1:
        return None
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = ProcessPoolExecutor(
                max_workers=workers,
                mp_context=_multiprocessing_context(),
            )
            _POOL_WORKERS = workers
        elif _POOL_WORKERS != workers:
            raise ValueError("semantic process worker count changed during one document")
        return _POOL


def shutdown_semantic_process_pool() -> None:
    global _POOL, _POOL_WORKERS
    with _POOL_LOCK:
        pool = _POOL
        _POOL = None
        _POOL_WORKERS = 0
    if pool is not None:
        pool.shutdown(wait=True, cancel_futures=True)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    method = getattr(value, "to_dict", None)
    if callable(method):
        row = method()
        if isinstance(row, Mapping):
            return dict(row)
    raise ValueError("semantic leaf input must be a mapping or expose to_dict()")


def _derive_hypothesis_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    from src.language.semantic_reductions import derive_relational_type_hypotheses

    value = derive_relational_type_hypotheses(
        bundle=payload["bundle"],
        atom_mention_refs=payload["atom_mention_refs"],
        declarations=payload["declarations"],
    )
    return {"pid": os.getpid(), "value": list(value)}


def _local_typing_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    from src.policy.entity_resolution import build_local_typing_carrier

    value = build_local_typing_carrier(
        mentions=payload["mentions"],
        forms=payload["forms"],
        typing_rules=payload["typing_rules"],
        structural_hypotheses=payload["structural_hypotheses"],
        authority=str(payload.get("authority") or "candidate_only"),
    )
    return {"pid": os.getpid(), "value": value}


def _diagnostic_worker(payload: Mapping[str, Any]) -> dict[str, Any]:
    from src.language.semantic_reductions import diagnose_untyped_mentions

    value = diagnose_untyped_mentions(
        mentions=payload["mentions"],
        local_typing=payload["local_typing"],
        bundle=payload["bundle"],
        atom_mention_refs=payload["atom_mention_refs"],
        parser_observation_refs=payload["parser_observation_refs"],
        parser_capabilities=payload["parser_capabilities"],
    )
    return {"pid": os.getpid(), "value": list(value)}


def _solve_operator_job_worker(job: Any) -> dict[str, Any]:
    from src.pnf.streaming_operator_executor import solve_operator_job

    return {"pid": os.getpid(), "value": tuple(solve_operator_job(job))}


def _leaf_path(root: Path | None, operation: str, leaf_ref: str) -> Path | None:
    if root is None:
        return None
    safe = "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in leaf_ref
    )
    return root / operation / f"{safe}.json"


def _load_leaf(
    path: Path | None, *, leaf_ref: str, input_digest: str
) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = _read_json(path)
    if payload is None:
        return None
    if (
        payload.get("schema_version") != TAIL_LEAF_SCHEMA_VERSION
        or payload.get("leaf_ref") != leaf_ref
        or payload.get("input_digest") != input_digest
    ):
        return None
    if canonical_sha256(payload.get("value")) != payload.get("output_digest"):
        return None
    return payload


def _hierarchy_receipt(
    *,
    operation: str,
    identity: Mapping[str, Any],
    leaves: Sequence[Mapping[str, Any]],
    output_value: Any,
    arity: int,
) -> dict[str, Any]:
    if arity < 2:
        raise ValueError("typing hierarchy arity must be at least two")
    levels: list[list[dict[str, Any]]] = []
    level = [
        {
            "node_ref": str(row["leaf_ref"]),
            "graph_ref": "typing-graph:"
            + canonical_sha256(
                {
                    "leaf_ref": row["leaf_ref"],
                    "output_digest": row["output_digest"],
                }
            ),
            "child_graph_refs": [],
            "level": 0,
            "descendant_bytes_reconstructed": 0,
        }
        for row in leaves
    ]
    levels.append(level)
    depth = 0
    while len(level) > 1:
        depth += 1
        parent_level: list[dict[str, Any]] = []
        for offset in range(0, len(level), arity):
            children = level[offset : offset + arity]
            child_graph_refs = sorted(str(row["graph_ref"]) for row in children)
            node_ref = "typing-node:" + canonical_sha256(
                {
                    "operation": operation,
                    "level": depth,
                    "child_graph_refs": child_graph_refs,
                }
            )
            parent_level.append(
                {
                    "node_ref": node_ref,
                    "graph_ref": "typing-graph:"
                    + canonical_sha256(
                        {
                            "node_ref": node_ref,
                            "child_graph_refs": child_graph_refs,
                            "cross_child_additions": [],
                        }
                    ),
                    "child_graph_refs": child_graph_refs,
                    "level": depth,
                    "descendant_bytes_reconstructed": 0,
                }
            )
        level = parent_level
        levels.append(level)
    output_digest = canonical_sha256(output_value)
    logical_ref = "logical-typing:" + canonical_sha256(
        {
            "operation": operation,
            "identity": dict(identity),
            "output_digest": output_digest,
        }
    )
    return {
        "schema_version": TAIL_ROOT_SCHEMA_VERSION,
        "operation": operation,
        "identity": dict(identity),
        "leaf_count": len(leaves),
        "node_count": sum(len(rows) for rows in levels),
        "root_graph_ref": levels[-1][0]["graph_ref"] if levels else "",
        "logical_typing_ref": logical_ref,
        "output_digest": output_digest,
        "levels": levels,
        "worker_pids": sorted(
            {
                int(row.get("worker_pid") or 0)
                for row in leaves
                if row.get("worker_pid")
            }
        ),
        "computed_leaf_count": sum(not bool(row.get("reused")) for row in leaves),
        "reused_leaf_count": sum(bool(row.get("reused")) for row in leaves),
        "descendant_bytes_reconstructed": 0,
        "flattening_free": True,
        "semantic_identity_partition_independent": True,
        "semantic_authority": "one_document",
        "process_execution_contract_ref": PROCESS_EXECUTION_CONTRACT,
    }


def _execute_leaves(
    *,
    operation: str,
    context: Any,
    payloads: Sequence[Mapping[str, Any]],
    input_identities: Sequence[Mapping[str, Any]],
    worker: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    merge: Callable[[Sequence[Any]], Any],
) -> tuple[Any, dict[str, Any]]:
    if len(payloads) != len(input_identities):
        raise ValueError("typing leaf payload and identity counts disagree")
    root = context.typing_checkpoint_root
    identity = context.typing_identity.to_dict()
    leaves: list[dict[str, Any] | None] = [None] * len(payloads)
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
        cached = _load_leaf(
            _leaf_path(root, operation, leaf_ref),
            leaf_ref=leaf_ref,
            input_digest=input_digest,
        )
        if cached is None:
            missing.append(ordinal)
        else:
            leaves[ordinal] = {**cached, "reused": True}

    started = monotonic_ns()
    executor = _pool()
    if executor is None:
        future_rows = ((ordinal, worker(payloads[ordinal])) for ordinal in missing)
    else:
        futures = {
            executor.submit(worker, payloads[ordinal]): ordinal for ordinal in missing
        }
        future_rows = (
            (futures[future], future.result()) for future in as_completed(futures)
        )

    newly_completed = 0
    stop_after = _integer_env(
        "SENSIBLAW_TYPING_TAIL_STOP_AFTER_LEAVES", 0, minimum=0
    )
    for ordinal, worker_result in future_rows:
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
            "schema_version": TAIL_LEAF_SCHEMA_VERSION,
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
        path = _leaf_path(root, operation, leaf_ref)
        if path is not None:
            _atomic_write_json(path, payload)
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
            },
        )
        if stop_after and newly_completed >= stop_after:
            raise RuntimeError(
                f"stopped after {newly_completed} checkpointed typing-tail leaves"
            )

    completed = [row for row in leaves if row is not None]
    if len(completed) != len(payloads):
        raise RuntimeError("typing leaf execution ended without complete coverage")
    output = merge([row["value"] for row in completed])
    receipt = _hierarchy_receipt(
        operation=operation,
        identity=identity,
        leaves=completed,
        output_value=output,
        arity=context.hierarchy_arity,
    )
    receipt["elapsed_ns"] = monotonic_ns() - started
    receipt["complexity"] = {
        "input_leaf_count": len(payloads),
        "document_rescan_per_leaf": False,
        "target": "O(inputs + outputs + hierarchy_interfaces)",
    }
    context.typing_receipts[operation] = receipt
    return output, receipt


def _chunked(rows: Sequence[T], size: int) -> tuple[tuple[T, ...], ...]:
    return tuple(
        tuple(rows[offset : offset + size]) for offset in range(0, len(rows), size)
    )


def _structural_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["mention_ref"]),
        str(row["semantic_family"]),
        str(row["local_type"]),
        tuple(row["evidence_refs"]),
    )


def _diagnostic_normalize(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    for key in (
        "available_annotation_refs",
        "parser_observation_refs",
        "reduction_consumption_refs",
        "existing_form_alternatives",
    ):
        if key in value:
            value[key] = tuple(value[key] or ())
    return value


def install_parallel_typing_tail() -> bool:
    """Install process-backed typing leaves and the pure closure handler."""

    from src.policy import corpus_compilation as legacy
    from src.policy import operational_corpus_compilation as operational
    from src.policy.parallel_semantic_execution import _CONTEXT, _context_for_document

    if getattr(operational, _INSTALL_MARKER, False):
        return False

    current_derive = legacy.derive_relational_type_hypotheses
    current_build_typing = legacy.build_local_typing_carrier
    current_diagnose = legacy.diagnose_untyped_mentions
    current_solve_operator = operational.solve_operator_job
    current_compile = operational.compile_document_operational

    def derive_wrapper(*args: Any, **kwargs: Any) -> Any:
        context = _CONTEXT.get()
        if context is None:
            return current_derive(*args, **kwargs)
        bundle = kwargs.get("bundle") or (args[0] if args else {})
        atom_mentions = kwargs.get("atom_mention_refs") or {}
        declarations = kwargs.get("declarations")
        relations = tuple(bundle.get("relations") or ())
        if not relations:
            return current_derive(*args, **kwargs)
        started = monotonic_ns()
        leaf_size = _integer_env("SENSIBLAW_TYPING_RELATION_LEAF_SIZE", 4096)
        chunks = _chunked(relations, leaf_size)
        declaration_identity = [_mapping(value) for value in declarations or ()]
        payloads: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for chunk in chunks:
            atom_refs = {
                str(role.get("atom") or "")
                for relation in chunk
                for role in relation.get("roles") or ()
                if role.get("atom")
            }
            subset = {
                ref: tuple(atom_mentions.get(ref, ())) for ref in sorted(atom_refs)
            }
            payloads.append(
                {
                    "bundle": {"relations": chunk},
                    "atom_mention_refs": subset,
                    "declarations": declarations,
                }
            )
            identities.append(
                {
                    "relation_refs": [str(row.get("id") or "") for row in chunk],
                    "atom_mention_refs": {
                        key: list(value) for key, value in subset.items()
                    },
                    "declarations": declaration_identity,
                }
            )

        def merge(values: Sequence[Any]) -> tuple[dict[str, Any], ...]:
            return tuple(
                sorted(
                    (
                        {
                            **dict(row),
                            "evidence_refs": tuple(row.get("evidence_refs") or ()),
                        }
                        for value in values
                        for row in value
                    ),
                    key=_structural_sort_key,
                )
            )

        result, receipt = _execute_leaves(
            operation="structural_hypothesis_derivation",
            context=context,
            payloads=payloads,
            input_identities=identities,
            worker=_derive_hypothesis_worker,
            merge=merge,
        )
        context.sample(
            "local_typing_diagnostics:structural_hypothesis_derivation",
            phase="kernel_completed",
            counts={
                "relations": len(relations),
                "structural_hypotheses": len(result),
                "leaf_count": receipt["leaf_count"],
            },
            details={
                "process_backed": _process_workers() > 1,
                "worker_pids": receipt["worker_pids"],
                "logical_typing_ref": receipt["logical_typing_ref"],
            },
            elapsed_ns=monotonic_ns() - started,
        )
        return result

    def build_typing_wrapper(*args: Any, **kwargs: Any) -> Any:
        context = _CONTEXT.get()
        if context is None:
            return current_build_typing(*args, **kwargs)
        mentions = tuple(kwargs.get("mentions") or ())
        forms = tuple(kwargs.get("forms") or ())
        typing_rules = tuple(kwargs.get("typing_rules") or ())
        structural = tuple(kwargs.get("structural_hypotheses") or ())
        authority = str(kwargs.get("authority") or "candidate_only")
        if not mentions:
            return current_build_typing(*args, **kwargs)
        started = monotonic_ns()
        leaf_size = _integer_env("SENSIBLAW_TYPING_MENTION_LEAF_SIZE", 4096)
        mention_rows = sorted(
            (_mapping(value) for value in mentions),
            key=lambda row: (
                int(row.get("start_token") or 0),
                str(row.get("mention_ref") or ""),
            ),
        )
        forms_by_mention: dict[str, list[dict[str, Any]]] = {}
        for value in forms:
            row = _mapping(value)
            forms_by_mention.setdefault(str(row.get("mention_ref") or ""), []).append(
                row
            )
        structural_by_mention: dict[str, list[dict[str, Any]]] = {}
        for value in structural:
            row = _mapping(value)
            structural_by_mention.setdefault(
                str(row.get("mention_ref") or ""), []
            ).append(row)
        rule_identity = [_mapping(value) for value in typing_rules]
        payloads: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for chunk in _chunked(mention_rows, leaf_size):
            refs = {str(row["mention_ref"]) for row in chunk}
            chunk_forms = tuple(
                row for ref in refs for row in forms_by_mention.get(ref, ())
            )
            chunk_structural = tuple(
                row for ref in refs for row in structural_by_mention.get(ref, ())
            )
            payloads.append(
                {
                    "mentions": chunk,
                    "forms": chunk_forms,
                    "typing_rules": typing_rules,
                    "structural_hypotheses": chunk_structural,
                    "authority": authority,
                }
            )
            identities.append(
                {
                    "mention_refs": sorted(refs),
                    "form_refs": sorted(
                        str(row.get("form_ref") or "") for row in chunk_forms
                    ),
                    "structural_hypotheses": chunk_structural,
                    "typing_rules": rule_identity,
                    "authority": authority,
                }
            )

        def merge(values: Sequence[Any]) -> dict[str, Any]:
            from src.policy.entity_resolution import (
                LOCAL_TYPING_SCHEMA_VERSION,
                _COVERAGE_STATES,
                _canonical_digest,
            )

            mention_output = sorted(
                (row for value in values for row in value["mentions"]),
                key=lambda row: row["mention_ref"],
            )
            form_output = sorted(
                (row for value in values for row in value["forms"]),
                key=lambda row: row["form_ref"],
            )
            rule_outputs = [value["typing_rules"] for value in values]
            rule_output = rule_outputs[0] if rule_outputs else []
            if any(rows != rule_output for rows in rule_outputs[1:]):
                raise ValueError("typing leaves disagree on typing rules")
            structural_output = sorted(
                (
                    {
                        **dict(row),
                        "evidence_refs": tuple(row.get("evidence_refs") or ()),
                    }
                    for value in values
                    for row in value["structural_hypotheses"]
                ),
                key=_structural_sort_key,
            )
            alternatives = sorted(
                (
                    row
                    for value in values
                    for row in value["local_type_alternatives"]
                ),
                key=lambda row: row["type_ref"],
            )
            coverage = sorted(
                (row for value in values for row in value["coverage_pressure"]),
                key=lambda row: row["mention_ref"],
            )
            identity = {
                "schema_version": LOCAL_TYPING_SCHEMA_VERSION,
                "authority": authority,
                "mentions": mention_output,
                "forms": form_output,
                "typing_rules": rule_output,
                "structural_hypotheses": structural_output,
                "local_type_alternatives": alternatives,
                "coverage_pressure": coverage,
                "serialization_order": "reference_nonsemantic",
            }
            return {
                **identity,
                "carrier_ref": f"local-typing:{_canonical_digest(identity)}",
                "resolution_effect": "none",
                "pnf_effect": "none",
                "promotion_effect": "none",
                "execution_effect": "none",
                "summary": {
                    "mention_count": len(mention_output),
                    "form_count": len(form_output),
                    "typing_rule_count": len(rule_output),
                    "structural_hypothesis_count": len(structural_output),
                    "local_type_alternative_count": len(alternatives),
                    "coverage_state_counts": {
                        state: sum(
                            row["coverage_state"] == state for row in coverage
                        )
                        for state in sorted(_COVERAGE_STATES)
                    },
                },
            }

        result, receipt = _execute_leaves(
            operation="local_type_carrier_build",
            context=context,
            payloads=payloads,
            input_identities=identities,
            worker=_local_typing_worker,
            merge=merge,
        )
        context.sample(
            "local_typing_diagnostics:local_type_carrier_build",
            phase="kernel_completed",
            counts={
                "mentions": len(mentions),
                "local_type_alternatives": len(
                    result.get("local_type_alternatives") or ()
                ),
                "leaf_count": receipt["leaf_count"],
            },
            details={
                "process_backed": _process_workers() > 1,
                "worker_pids": receipt["worker_pids"],
                "logical_typing_ref": receipt["logical_typing_ref"],
            },
            elapsed_ns=monotonic_ns() - started,
        )
        return result

    def diagnose_wrapper(*args: Any, **kwargs: Any) -> Any:
        context = _CONTEXT.get()
        if context is None:
            return current_diagnose(*args, **kwargs)
        mentions = tuple(kwargs.get("mentions") or ())
        local_typing = dict(kwargs.get("local_typing") or {})
        bundle = dict(kwargs.get("bundle") or {})
        atom_mentions = dict(kwargs.get("atom_mention_refs") or {})
        parser_refs = dict(kwargs.get("parser_observation_refs") or {})
        parser_capabilities = dict(kwargs.get("parser_capabilities") or {})
        if not mentions:
            return current_diagnose(*args, **kwargs)
        started = monotonic_ns()
        leaf_size = _integer_env("SENSIBLAW_TYPING_MENTION_LEAF_SIZE", 4096)
        mention_rows = sorted(
            (_mapping(value) for value in mentions),
            key=lambda row: (
                int(row.get("start_token") or 0),
                str(row.get("mention_ref") or ""),
            ),
        )
        chunks = _chunked(mention_rows, leaf_size)
        mention_leaf = {
            str(row["mention_ref"]): ordinal
            for ordinal, chunk in enumerate(chunks)
            for row in chunk
        }
        relations_by_leaf: dict[int, list[Mapping[str, Any]]] = {
            ordinal: [] for ordinal in range(len(chunks))
        }
        for relation in bundle.get("relations") or ():
            leaf_ordinals = {
                mention_leaf[mention_ref]
                for role in relation.get("roles") or ()
                for mention_ref in atom_mentions.get(str(role.get("atom") or ""), ())
                if mention_ref in mention_leaf
            }
            for ordinal in leaf_ordinals:
                relations_by_leaf[ordinal].append(relation)
        coverage_by_mention = {
            str(row.get("mention_ref") or ""): row
            for row in local_typing.get("coverage_pressure") or ()
        }
        forms_by_mention: dict[str, list[Mapping[str, Any]]] = {}
        for row in local_typing.get("forms") or ():
            forms_by_mention.setdefault(str(row.get("mention_ref") or ""), []).append(
                row
            )
        payloads: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for ordinal, chunk in enumerate(chunks):
            refs = {str(row["mention_ref"]) for row in chunk}
            subset_atom_mentions = {
                atom_ref: tuple(ref for ref in mention_refs if ref in refs)
                for atom_ref, mention_refs in atom_mentions.items()
                if any(ref in refs for ref in mention_refs)
            }
            subset_relations = tuple(relations_by_leaf[ordinal])
            subset_local = {
                "coverage_pressure": [
                    coverage_by_mention[ref]
                    for ref in sorted(refs)
                    if ref in coverage_by_mention
                ],
                "forms": [
                    row for ref in sorted(refs) for row in forms_by_mention.get(ref, ())
                ],
            }
            subset_parser = {
                ref: tuple(parser_refs.get(ref, ())) for ref in sorted(refs)
            }
            payloads.append(
                {
                    "mentions": chunk,
                    "local_typing": subset_local,
                    "bundle": {"relations": subset_relations},
                    "atom_mention_refs": subset_atom_mentions,
                    "parser_observation_refs": subset_parser,
                    "parser_capabilities": parser_capabilities,
                }
            )
            identities.append(
                {
                    "mention_refs": sorted(refs),
                    "relation_refs": [
                        str(row.get("id") or "") for row in subset_relations
                    ],
                    "coverage_pressure": subset_local["coverage_pressure"],
                    "parser_observation_refs": {
                        key: list(value) for key, value in subset_parser.items()
                    },
                    "parser_capabilities": parser_capabilities,
                }
            )

        def merge(values: Sequence[Any]) -> tuple[dict[str, Any], ...]:
            return tuple(
                sorted(
                    (
                        _diagnostic_normalize(row)
                        for value in values
                        for row in value
                    ),
                    key=lambda row: str(row["mention_ref"]),
                )
            )

        result, receipt = _execute_leaves(
            operation="untyped_diagnostic_generation",
            context=context,
            payloads=payloads,
            input_identities=identities,
            worker=_diagnostic_worker,
            merge=merge,
        )
        context.sample(
            "local_typing_diagnostics:untyped_diagnostic_generation",
            phase="kernel_completed",
            counts={
                "mentions": len(mentions),
                "diagnostics": len(result),
                "leaf_count": receipt["leaf_count"],
            },
            details={
                "process_backed": _process_workers() > 1,
                "worker_pids": receipt["worker_pids"],
                "logical_typing_ref": receipt["logical_typing_ref"],
            },
            elapsed_ns=monotonic_ns() - started,
        )
        return result

    def solve_operator_wrapper(job: Any) -> Any:
        context = _context_for_document(job.owner_key.document_ref)
        executor = _pool()
        if context is None or executor is None:
            return current_solve_operator(job)
        started = monotonic_ns()
        result = executor.submit(_solve_operator_job_worker, job).result()
        with context.lock:
            context.closure_counters["process_jobs_completed"] += 1
            context.closure_counters[f"process_worker_pid:{result['pid']}"] += 1
        context.sample(
            "streaming_closure:process_solver",
            phase="closure_job_completed",
            counts={
                "proposals_emitted": len(result["value"]),
                "worker_pid": int(result["pid"]),
            },
            details={
                "job_ref": job.job_ref,
                "owner_ref": job.owner_key.owner_ref,
                "process_backed": True,
            },
            elapsed_ns=monotonic_ns() - started,
        )
        return result["value"]

    def compile_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return current_compile(*args, **kwargs)
        finally:
            shutdown_semantic_process_pool()

    legacy._serial_derive_relational_type_hypotheses = current_derive
    legacy._serial_build_local_typing_carrier = current_build_typing
    legacy._serial_diagnose_untyped_mentions = current_diagnose
    legacy.derive_relational_type_hypotheses = derive_wrapper
    legacy.build_local_typing_carrier = build_typing_wrapper
    legacy.diagnose_untyped_mentions = diagnose_wrapper
    operational.solve_operator_job = solve_operator_wrapper
    operational.compile_document_operational = compile_wrapper
    operational._parallel_semantic_compile_document_operational = current_compile
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = [
    "PROCESS_EXECUTION_CONTRACT",
    "install_parallel_typing_tail",
    "shutdown_semantic_process_pool",
]
