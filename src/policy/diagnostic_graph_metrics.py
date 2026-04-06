from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any, Mapping, Sequence


GRAPH_DIAGNOSTICS_SCHEMA_VERSION = "itir.graph_diagnostics.v1"
GRAPH_DIAGNOSTICS_REGISTRY_ID = "sl.graph_metrics.v1"
GRAPH_CONE_SCHEMA_VERSION = "itir.graph_cone.v1"
GRAPH_REVISION_STABILITY_SCHEMA_VERSION = "itir.graph_revision_stability.v1"
GRAPH_REVISION_STABILITY_REGISTRY_ID = "sl.graph_revision_stability.v1"

_V1_METRIC_IDS = (
    "node_count",
    "edge_count",
    "component_count",
    "giant_component_ratio",
    "branching_factor",
)

# Doctrine:
# - graph diagnostics are derived observability surfaces over explicit graph projections
# - revision stability is defined only over an explicit baseline/candidate pair
# - admissibility failures reject comparison rather than normalizing scope silently
# - neither static diagnostics nor revision stability may carry truth or control semantics


def _as_node_list(graph_payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    nodes = graph_payload.get("nodes") if isinstance(graph_payload, Mapping) else []
    return [row for row in nodes if isinstance(row, Mapping)] if isinstance(nodes, list) else []


def _as_edge_list(graph_payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    edges = graph_payload.get("edges") if isinstance(graph_payload, Mapping) else []
    return [row for row in edges if isinstance(row, Mapping)] if isinstance(edges, list) else []


def _round(value: float) -> float:
    return round(float(value), 6)


def _string(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool(value: bool) -> bool:
    return bool(value)


def _component_metrics(
    node_ids: Sequence[str],
    edges: Sequence[Mapping[str, Any]],
) -> tuple[int, float]:
    if not node_ids:
        return 0, 0.0
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)

    seen: set[str] = set()
    component_sizes: list[int] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        queue = deque([node_id])
        seen.add(node_id)
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            for neighbor in sorted(adjacency.get(current, ())):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)
        component_sizes.append(size)

    largest = max(component_sizes, default=0)
    return len(component_sizes), _round(largest / len(node_ids))


def build_graph_cone_diagnostics(
    *,
    graph_payload: Mapping[str, Any],
    seed_node_kinds: Sequence[str],
    allowed_edge_types: Sequence[str],
    max_depth: int,
) -> dict[str, Any]:
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    nodes = _as_node_list(graph_payload)
    edges = _as_edge_list(graph_payload)
    node_ids = {
        str(row.get("id") or "").strip()
        for row in nodes
        if str(row.get("id") or "").strip()
    }
    node_kinds = {
        str(row.get("id") or "").strip(): str(row.get("kind") or "").strip()
        for row in nodes
        if str(row.get("id") or "").strip()
    }
    seed_kind_set = {str(kind).strip() for kind in seed_node_kinds if str(kind).strip()}
    allowed_edge_set = {str(kind).strip() for kind in allowed_edge_types if str(kind).strip()}
    if not seed_kind_set:
        raise ValueError("seed_node_kinds must not be empty")
    if not allowed_edge_set:
        raise ValueError("allowed_edge_types must not be empty")

    seed_set = sorted(node_id for node_id, kind in node_kinds.items() if kind in seed_kind_set)
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    all_outgoing_edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        kind = str(edge.get("kind") or "").strip()
        if not source or not target or source not in node_ids or target not in node_ids or not kind:
            continue
        all_outgoing_edges[source].append((target, kind))
        if kind in allowed_edge_set:
            adjacency[source].append((target, kind))

    visited_depth: dict[str, int] = {}
    frontier = deque()
    for seed_id in seed_set:
        visited_depth[seed_id] = 0
        frontier.append(seed_id)

    traversed_edges: set[tuple[str, str, str]] = set()
    encountered_edges = 0
    encountered_disallowed = 0
    while frontier:
        current = frontier.popleft()
        depth = visited_depth[current]
        outgoing = all_outgoing_edges.get(current, [])
        encountered_edges += len(outgoing)
        encountered_disallowed += sum(1 for _, kind in outgoing if kind not in allowed_edge_set)
        if depth >= max_depth:
            continue
        for target, kind in sorted(adjacency.get(current, []), key=lambda row: (row[1], row[0])):
            traversed_edges.add((current, target, kind))
            if target in visited_depth:
                continue
            visited_depth[target] = depth + 1
            frontier.append(target)

    width_counter = Counter(visited_depth.values())
    total_encountered = encountered_edges
    return {
        "schema_version": GRAPH_CONE_SCHEMA_VERSION,
        "seed_set": seed_set,
        "allowed_edge_types": sorted(allowed_edge_set),
        "max_depth": max_depth,
        "depth_reached": max(width_counter, default=0),
        "width_by_depth": {str(depth): width_counter[depth] for depth in sorted(width_counter)},
        "seed_coverage": {
            "valid_seed_count": len(seed_set),
            "missing_seed_count": 0,
        },
        "selectivity": _round(len(traversed_edges) / total_encountered) if total_encountered else 0.0,
        "leakage": _round(encountered_disallowed / total_encountered) if total_encountered else 0.0,
    }


def build_graph_diagnostics(
    *,
    graph_payload: Mapping[str, Any],
    source_artifact_id: str,
    source_lane: str,
    substrate_kind: str,
    projection_role: str,
    graph_version: str | None = None,
    cone_seed_node_kinds: Sequence[str] | None = None,
    cone_allowed_edge_types: Sequence[str] | None = None,
    cone_max_depth: int | None = None,
) -> dict[str, Any]:
    nodes = _as_node_list(graph_payload)
    edges = _as_edge_list(graph_payload)
    node_ids = sorted(
        {
            str(row.get("id") or "").strip()
            for row in nodes
            if str(row.get("id") or "").strip()
        }
    )
    node_count = len(node_ids)
    edge_count = len(edges)
    component_count, giant_component_ratio = _component_metrics(node_ids, edges)
    diagnostics = {
        "schema_version": GRAPH_DIAGNOSTICS_SCHEMA_VERSION,
        "diagnostic_kind": "deterministic_structural_metrics",
        "scope": {
            "substrate_kind": str(substrate_kind),
            "source_artifact_id": str(source_artifact_id),
            "source_lane": str(source_lane),
            "projection_role": str(projection_role),
            "graph_version": str(graph_version or ""),
            "replay_basis": "explicit_graph_payload",
        },
        "registry": {
            "registry_id": GRAPH_DIAGNOSTICS_REGISTRY_ID,
            "registry_version": "v1",
            "metric_ids": list(_V1_METRIC_IDS),
        },
        "metrics": {
            "node_count": node_count,
            "edge_count": edge_count,
            "component_count": component_count,
            "giant_component_ratio": giant_component_ratio,
            "branching_factor": _round(edge_count / node_count) if node_count else 0.0,
        },
    }
    if cone_seed_node_kinds and cone_allowed_edge_types and cone_max_depth is not None:
        diagnostics["cone"] = build_graph_cone_diagnostics(
            graph_payload=graph_payload,
            seed_node_kinds=cone_seed_node_kinds,
            allowed_edge_types=cone_allowed_edge_types,
            max_depth=cone_max_depth,
        )
    return diagnostics


def build_graph_revision_stability(
    *,
    baseline_diagnostics: Mapping[str, Any],
    candidate_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _mapping(baseline_diagnostics)
    candidate = _mapping(candidate_diagnostics)
    baseline_scope = _mapping(baseline.get("scope"))
    candidate_scope = _mapping(candidate.get("scope"))
    baseline_registry = _mapping(baseline.get("registry"))
    candidate_registry = _mapping(candidate.get("registry"))
    baseline_cone = _mapping(baseline.get("cone"))
    candidate_cone = _mapping(candidate.get("cone"))

    same_registry_id = _string(baseline_registry.get("registry_id")) == _string(candidate_registry.get("registry_id"))
    same_registry_version = _string(baseline_registry.get("registry_version")) == _string(candidate_registry.get("registry_version"))
    same_schema_version = _string(baseline.get("schema_version")) == _string(candidate.get("schema_version"))
    same_substrate_kind = _string(baseline_scope.get("substrate_kind")) == _string(candidate_scope.get("substrate_kind"))
    same_projection_role = _string(baseline_scope.get("projection_role")) == _string(candidate_scope.get("projection_role"))
    same_source_lane = _string(baseline_scope.get("source_lane")) == _string(candidate_scope.get("source_lane"))
    same_allowed_edge_types = sorted(baseline_cone.get("allowed_edge_types") or []) == sorted(candidate_cone.get("allowed_edge_types") or [])
    same_max_depth = baseline_cone.get("max_depth") == candidate_cone.get("max_depth")
    cone_present_in_both = bool(baseline_cone) and bool(candidate_cone)
    seed_set_changed = sorted(baseline_cone.get("seed_set") or []) != sorted(candidate_cone.get("seed_set") or [])

    rejection_reasons: list[str] = []
    if not same_schema_version:
        rejection_reasons.append("schema_version_mismatch")
    if not same_registry_id:
        rejection_reasons.append("registry_id_mismatch")
    if not same_registry_version:
        rejection_reasons.append("registry_version_mismatch")
    if not same_substrate_kind:
        rejection_reasons.append("substrate_kind_mismatch")
    if not same_projection_role:
        rejection_reasons.append("projection_role_mismatch")
    if not same_source_lane:
        rejection_reasons.append("source_lane_mismatch")
    if bool(baseline_cone) != bool(candidate_cone):
        rejection_reasons.append("cone_presence_mismatch")
    if cone_present_in_both and not same_allowed_edge_types:
        rejection_reasons.append("allowed_edge_types_mismatch")
    if cone_present_in_both and not same_max_depth:
        rejection_reasons.append("max_depth_mismatch")

    admissible = not rejection_reasons
    result = {
        "schema_version": GRAPH_REVISION_STABILITY_SCHEMA_VERSION,
        "diagnostic_kind": "deterministic_revision_pair_metrics",
        "comparison_scope": {
            "substrate_kind": _string(candidate_scope.get("substrate_kind") or baseline_scope.get("substrate_kind")),
            "projection_role": _string(candidate_scope.get("projection_role") or baseline_scope.get("projection_role")),
            "source_lane": _string(candidate_scope.get("source_lane") or baseline_scope.get("source_lane")),
            "comparison_basis": "explicit_graph_diagnostics_pair",
            "replay_basis": "explicit_graph_diagnostics_pair",
        },
        "admissibility": {
            "admissible": admissible,
            "baseline_graph_version": _string(baseline_scope.get("graph_version")),
            "candidate_graph_version": _string(candidate_scope.get("graph_version")),
            "baseline_source_artifact_id": _string(baseline_scope.get("source_artifact_id")),
            "candidate_source_artifact_id": _string(candidate_scope.get("source_artifact_id")),
            "same_schema_version": _bool(same_schema_version),
            "same_registry_id": _bool(same_registry_id),
            "same_registry_version": _bool(same_registry_version),
            "same_substrate_kind": _bool(same_substrate_kind),
            "same_projection_role": _bool(same_projection_role),
            "same_source_lane": _bool(same_source_lane),
            "same_allowed_edge_types": _bool(same_allowed_edge_types),
            "same_max_depth": _bool(same_max_depth),
            "seed_set_changed": _bool(seed_set_changed),
            "rejection_reasons": rejection_reasons,
        },
        "registry": {
            "registry_id": GRAPH_REVISION_STABILITY_REGISTRY_ID,
            "registry_version": "v1",
            "metric_ids": [
                "node_count_delta",
                "edge_count_delta",
                "component_count_delta",
                "giant_component_ratio_delta",
                "branching_factor_delta",
                "depth_reached_delta",
                "selectivity_delta",
                "leakage_delta",
                "seed_count_delta",
            ],
        },
        "baseline_ref": {
            "source_artifact_id": _string(baseline_scope.get("source_artifact_id")),
            "graph_version": _string(baseline_scope.get("graph_version")),
        },
        "candidate_ref": {
            "source_artifact_id": _string(candidate_scope.get("source_artifact_id")),
            "graph_version": _string(candidate_scope.get("graph_version")),
        },
        "deltas": {},
    }
    if not admissible:
        return result

    baseline_metrics = _mapping(baseline.get("metrics"))
    candidate_metrics = _mapping(candidate.get("metrics"))
    baseline_width = _mapping(baseline_cone.get("width_by_depth"))
    candidate_width = _mapping(candidate_cone.get("width_by_depth"))
    all_depths = sorted({*baseline_width.keys(), *candidate_width.keys()}, key=lambda depth: int(depth))

    result["deltas"] = {
        "node_count_delta": int(candidate_metrics.get("node_count") or 0) - int(baseline_metrics.get("node_count") or 0),
        "edge_count_delta": int(candidate_metrics.get("edge_count") or 0) - int(baseline_metrics.get("edge_count") or 0),
        "component_count_delta": int(candidate_metrics.get("component_count") or 0) - int(baseline_metrics.get("component_count") or 0),
        "giant_component_ratio_delta": _round((candidate_metrics.get("giant_component_ratio") or 0.0) - (baseline_metrics.get("giant_component_ratio") or 0.0)),
        "branching_factor_delta": _round((candidate_metrics.get("branching_factor") or 0.0) - (baseline_metrics.get("branching_factor") or 0.0)),
        "depth_reached_delta": int(candidate_cone.get("depth_reached") or 0) - int(baseline_cone.get("depth_reached") or 0),
        "selectivity_delta": _round((candidate_cone.get("selectivity") or 0.0) - (baseline_cone.get("selectivity") or 0.0)),
        "leakage_delta": _round((candidate_cone.get("leakage") or 0.0) - (baseline_cone.get("leakage") or 0.0)),
        "seed_count_delta": len(candidate_cone.get("seed_set") or []) - len(baseline_cone.get("seed_set") or []),
        "width_delta_by_depth": {
            depth: int(candidate_width.get(depth) or 0) - int(baseline_width.get(depth) or 0)
            for depth in all_depths
        },
    }
    return result


__all__ = [
    "GRAPH_CONE_SCHEMA_VERSION",
    "GRAPH_DIAGNOSTICS_REGISTRY_ID",
    "GRAPH_DIAGNOSTICS_SCHEMA_VERSION",
    "GRAPH_REVISION_STABILITY_REGISTRY_ID",
    "GRAPH_REVISION_STABILITY_SCHEMA_VERSION",
    "build_graph_cone_diagnostics",
    "build_graph_diagnostics",
    "build_graph_revision_stability",
]
