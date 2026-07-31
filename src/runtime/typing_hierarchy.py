"""Bounded mini/midi/mega execution for local typing overlap work."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.runtime.hierarchical_graph_execution import HierarchyPlan
from src.runtime.interval_overlap import IntervalRecord, TokenIntervalIndex


TYPING_EXECUTION_CONTRACT = "typing-execution:indexed-hierarchy:v1"
TYPING_LEAF_SCHEMA_VERSION = "sensiblaw.typing-leaf-checkpoint.v1"
TYPING_ROOT_SCHEMA_VERSION = "sensiblaw.typing-hierarchy-receipt.v1"


class TypingCheckpointStop(RuntimeError):
    """Injected stop after immutable leaves have been written."""


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


@dataclass(frozen=True)
class TypingExecutionIdentity:
    document_ref: str
    source_sha256: str
    parser_contract_ref: str
    build_key_sha256: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "document_ref": self.document_ref,
            "source_sha256": self.source_sha256,
            "parser_contract_ref": self.parser_contract_ref,
            "build_key_sha256": self.build_key_sha256,
            "typing_contract_ref": TYPING_EXECUTION_CONTRACT,
        }

    def semantic_payload(self) -> dict[str, str]:
        """Identity fields whose meaning is independent of execution partitioning."""

        return self.to_dict()


class TypingCheckpointStore:
    def __init__(self, root: str | Path | None):
        self.root = Path(root) if root is not None else None

    def path(self, operation: str, leaf_ref: str) -> Path | None:
        if self.root is None:
            return None
        safe = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in leaf_ref
        )
        return self.root / operation / f"{safe}.json"

    def load(
        self,
        operation: str,
        leaf_ref: str,
        input_digest: str,
    ) -> dict[str, Any] | None:
        path = self.path(operation, leaf_ref)
        if path is None or not path.exists():
            return None
        payload = _read_json(path)
        if payload is None:
            return None
        if (
            payload.get("schema_version") != TYPING_LEAF_SCHEMA_VERSION
            or payload.get("leaf_ref") != leaf_ref
            or payload.get("input_digest") != input_digest
        ):
            return None
        records = payload.get("records")
        if not isinstance(records, list):
            return None
        if canonical_sha256(records) != payload.get("output_digest"):
            return None
        return payload

    def write(
        self,
        operation: str,
        leaf_ref: str,
        payload: Mapping[str, Any],
    ) -> None:
        path = self.path(operation, leaf_ref)
        if path is not None:
            _atomic_write_json(path, payload)

    def write_root(
        self, operation: str, root_graph_ref: str, payload: Mapping[str, Any]
    ) -> None:
        if self.root is None:
            return
        safe = root_graph_ref.replace(":", "_")
        _atomic_write_json(self.root / "roots" / f"{operation}-{safe}.json", payload)


def _leaf_input_digest(
    *,
    operation: str,
    identity: TypingExecutionIdentity,
    carrier_start: int,
    carrier_end: int,
    left: Sequence[IntervalRecord],
    right: Sequence[IntervalRecord],
) -> str:
    return canonical_sha256(
        {
            "operation": operation,
            "identity": identity.to_dict(),
            "carrier": [carrier_start, carrier_end],
            "left": [[row.ref, row.start, row.end] for row in left],
            "right": [[row.ref, row.start, row.end] for row in right],
        }
    )


def _leaf_ref(operation: str, node_ref: str, input_digest: str) -> str:
    return "typing-leaf:" + canonical_sha256(
        {
            "operation": operation,
            "hierarchy_node_ref": node_ref,
            "input_digest": input_digest,
        }
    )


def _compute_leaf(
    *,
    operation: str,
    node_ref: str,
    carrier_start: int,
    carrier_end: int,
    left: Sequence[IntervalRecord],
    right: Sequence[IntervalRecord],
    index: TokenIntervalIndex,
    identity: TypingExecutionIdentity,
    store: TypingCheckpointStore,
) -> dict[str, Any]:
    input_digest = _leaf_input_digest(
        operation=operation,
        identity=identity,
        carrier_start=carrier_start,
        carrier_end=carrier_end,
        left=left,
        right=right,
    )
    leaf_ref = _leaf_ref(operation, node_ref, input_digest)
    cached = store.load(operation, leaf_ref, input_digest)
    if cached is not None:
        return {**cached, "reused": True}

    started = monotonic_ns()
    records: list[list[Any]] = []
    query_node_visits = 0
    query_candidate_checks = 0
    for row in left:
        matches, receipt = index.overlapping_with_receipt(row.start, row.end)
        query_node_visits += receipt.node_visits
        query_candidate_checks += receipt.candidate_checks
        if matches:
            records.append([row.ref, list(matches)])
    output_digest = canonical_sha256(records)
    left_crossing = sorted(
        row.ref
        for row in left
        if row.end > carrier_end or row.start < carrier_start
    )
    right_crossing = sorted(
        row.ref
        for row in right
        if row.start < carrier_end
        and row.end > carrier_start
        and (row.start < carrier_start or row.end > carrier_end)
    )
    payload = {
        "schema_version": TYPING_LEAF_SCHEMA_VERSION,
        "leaf_ref": leaf_ref,
        "operation": operation,
        "hierarchy_node_ref": node_ref,
        "carrier": {
            "start": carrier_start,
            "end": carrier_end,
            "unit": "tokens",
        },
        "identity": identity.to_dict(),
        "input_digest": input_digest,
        "output_digest": output_digest,
        "record_count": len(records),
        "records": records,
        "boundary_interface": {
            "left_crossing_refs": left_crossing,
            "right_crossing_refs": right_crossing,
            "unresolved_demand_refs": [],
        },
        "coverage": {
            "state": "complete",
            "local_fixed_point": True,
            "exact_owner_coverage": True,
        },
        "complexity": {
            "left_input_count": len(left),
            "right_interface_count": len(right),
            "query_node_visits": query_node_visits,
            "query_candidate_checks": query_candidate_checks,
            "actual_match_count": sum(len(row[1]) for row in records),
            "target": "O(left + right + actual_matches)",
        },
        "elapsed_ns": monotonic_ns() - started,
        "reused": False,
        "semantic_authority": "document_fibre_only",
    }
    store.write(operation, leaf_ref, payload)
    return payload


def _hierarchy_receipt(
    *,
    operation: str,
    identity: TypingExecutionIdentity,
    plan: HierarchyPlan,
    leaves: Mapping[str, Mapping[str, Any]],
    merged_records: Sequence[Sequence[Any]],
) -> dict[str, Any]:
    graph_ref_by_node: dict[str, str] = {}
    interface_by_node: dict[str, tuple[str, ...]] = {}
    nodes: list[dict[str, Any]] = []

    for level, node_refs in enumerate(plan.node_refs_by_level):
        for node_ref in node_refs:
            children = tuple(plan.children_by_node.get(node_ref, ()))
            if level == 0:
                payload = leaves[node_ref]
                graph_ref = "typing-graph:" + canonical_sha256(
                    {
                        "leaf_ref": payload["leaf_ref"],
                        "output_digest": payload["output_digest"],
                    }
                )
                interface = tuple(
                    sorted(
                        set(payload["boundary_interface"]["left_crossing_refs"])
                        | set(payload["boundary_interface"]["right_crossing_refs"])
                    )
                )
                introduced_count = int(payload["record_count"])
            else:
                child_graph_refs = tuple(
                    sorted(graph_ref_by_node[child] for child in children)
                )
                interface = tuple(
                    sorted(
                        {
                            ref
                            for child in children
                            for ref in interface_by_node[child]
                        }
                    )
                )
                graph_ref = "typing-graph:" + canonical_sha256(
                    {
                        "node_ref": node_ref,
                        "child_graph_refs": child_graph_refs,
                        "cross_child_additions": [],
                        "boundary_interface_refs": interface,
                    }
                )
                introduced_count = 0
            graph_ref_by_node[node_ref] = graph_ref
            interface_by_node[node_ref] = interface
            nodes.append(
                {
                    "node_ref": node_ref,
                    "level": level,
                    "carrier": plan.carriers[node_ref].to_dict(),
                    "child_graph_refs": [
                        graph_ref_by_node[child] for child in children
                    ],
                    "graph_ref": graph_ref,
                    "introduced_record_count": introduced_count,
                    "boundary_interface_ref_count": len(interface),
                    "unresolved_demand_count": 0,
                    "locally_fixed_point": True,
                    "descendant_bytes_reconstructed": 0,
                }
            )

    output_digest = canonical_sha256(list(merged_records))
    logical_typing_ref = "logical-typing:" + canonical_sha256(
        {
            "operation": operation,
            "identity": identity.semantic_payload(),
            "output_digest": output_digest,
        }
    )
    return {
        "schema_version": TYPING_ROOT_SCHEMA_VERSION,
        "operation": operation,
        "identity": identity.to_dict(),
        "leaf_capacity": plan.leaf_capacity,
        "arity": plan.arity,
        "leaf_count": len(plan.leaf_refs),
        "node_count": plan.node_count,
        "root_node_ref": plan.root_ref,
        "root_graph_ref": graph_ref_by_node[plan.root_ref],
        "logical_typing_ref": logical_typing_ref,
        "output_digest": output_digest,
        "output_record_count": len(merged_records),
        "nodes": nodes,
        "coverage": {
            "state": "complete",
            "exact_owner_coverage": True,
            "local_fixed_point": True,
        },
        "descendant_bytes_reconstructed": 0,
        "flattening_free": True,
        "semantic_identity_partition_independent": True,
        "semantic_authority": "one_document",
    }


def execute_partitioned_overlap(
    *,
    operation: str,
    identity: TypingExecutionIdentity,
    left_records: Sequence[IntervalRecord],
    right_records: Sequence[IntervalRecord],
    workers: int,
    leaf_capacity: int = 4096,
    arity: int = 4,
    checkpoint_root: str | Path | None = None,
    stop_after_new_leaves: int = 0,
    observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Solve independent overlap leaves and deterministically join one root."""

    if workers < 1:
        raise ValueError("workers must be positive")
    if leaf_capacity < 1:
        raise ValueError("leaf_capacity must be positive")
    if arity < 2:
        raise ValueError("arity must be at least two")
    if stop_after_new_leaves < 0:
        raise ValueError("stop_after_new_leaves must be non-negative")

    primitive_count = max(
        [1]
        + [row.end for row in left_records]
        + [row.end for row in right_records]
    )
    plan = HierarchyPlan.build(
        document_ref=identity.document_ref,
        primitive_unit_count=primitive_count,
        leaf_capacity=leaf_capacity,
        arity=arity,
        unit="tokens",
    )
    left_by_leaf: dict[str, list[IntervalRecord]] = {
        node_ref: [] for node_ref in plan.leaf_refs
    }
    for row in left_records:
        left_by_leaf[plan.leaf_for_offset(row.start)].append(row)

    index = TokenIntervalIndex(right_records)
    right_by_ref = {row.ref: row for row in right_records}
    if len(right_by_ref) != len(right_records):
        raise ValueError("right-side interval references must be unique")

    def right_for_carrier(start: int, end: int) -> tuple[IntervalRecord, ...]:
        refs = index.overlapping(start, end)
        return tuple(right_by_ref[ref] for ref in refs)

    store = TypingCheckpointStore(checkpoint_root)
    leaves: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for node_ref in plan.leaf_refs:
        carrier = plan.carriers[node_ref]
        left = tuple(
            sorted(
                left_by_leaf[node_ref],
                key=lambda row: (row.start, row.end, row.ref),
            )
        )
        right = right_for_carrier(carrier.start, carrier.end)
        digest = _leaf_input_digest(
            operation=operation,
            identity=identity,
            carrier_start=carrier.start,
            carrier_end=carrier.end,
            left=left,
            right=right,
        )
        ref = _leaf_ref(operation, node_ref, digest)
        cached = store.load(operation, ref, digest)
        if cached is None:
            missing.append(node_ref)
        else:
            leaves[node_ref] = {**cached, "reused": True}

    started = monotonic_ns()
    newly_completed = 0
    max_workers = min(max(1, workers), max(1, len(missing)))
    if missing:
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"typing-{operation}",
        ) as pool:
            futures = {}
            for node_ref in missing:
                carrier = plan.carriers[node_ref]
                left = tuple(
                    sorted(
                        left_by_leaf[node_ref],
                        key=lambda row: (row.start, row.end, row.ref),
                    )
                )
                right = right_for_carrier(carrier.start, carrier.end)
                future = pool.submit(
                    _compute_leaf,
                    operation=operation,
                    node_ref=node_ref,
                    carrier_start=carrier.start,
                    carrier_end=carrier.end,
                    left=left,
                    right=right,
                    index=index,
                    identity=identity,
                    store=store,
                )
                futures[future] = node_ref

            for future in as_completed(futures):
                node_ref = futures[future]
                payload = future.result()
                leaves[node_ref] = payload
                newly_completed += 1
                if observer is not None:
                    observer(
                        {
                            "operation": operation,
                            "leaf_ref": payload["leaf_ref"],
                            "hierarchy_node_ref": node_ref,
                            "record_count": int(payload["record_count"]),
                            "input_row_count": len(left_by_leaf[node_ref]),
                            "reused": False,
                            "elapsed_ns": int(payload["elapsed_ns"]),
                            "workers": max_workers,
                            "complexity": dict(payload.get("complexity") or {}),
                        }
                    )
                if (
                    stop_after_new_leaves
                    and newly_completed >= stop_after_new_leaves
                ):
                    for other in futures:
                        other.cancel()
                    raise TypingCheckpointStop(
                        f"stopped after {newly_completed} completed typing leaves"
                    )

    merged: dict[str, tuple[str, ...]] = {}
    for node_ref in plan.leaf_refs:
        payload = leaves[node_ref]
        for key, values in payload["records"]:
            merged[str(key)] = tuple(sorted(str(value) for value in values))
    merged_records = [[key, list(merged[key])] for key in sorted(merged)]
    receipt = _hierarchy_receipt(
        operation=operation,
        identity=identity,
        plan=plan,
        leaves=leaves,
        merged_records=merged_records,
    )
    receipt["elapsed_ns"] = monotonic_ns() - started
    receipt["reused_leaf_count"] = sum(
        1 for payload in leaves.values() if payload.get("reused")
    )
    receipt["computed_leaf_count"] = len(leaves) - receipt["reused_leaf_count"]
    receipt["complexity"] = {
        "left_input_count": len(left_records),
        "right_input_count": len(right_records),
        "actual_match_count": sum(len(value) for value in merged.values()),
        "planning_right_scan_per_leaf": False,
        "target": "O(left + right + actual_matches + hierarchy_interfaces)",
    }
    store.write_root(operation, receipt["root_graph_ref"], receipt)
    return merged, receipt


__all__ = [
    "TYPING_EXECUTION_CONTRACT",
    "TypingCheckpointStop",
    "TypingCheckpointStore",
    "TypingExecutionIdentity",
    "execute_partitioned_overlap",
]
