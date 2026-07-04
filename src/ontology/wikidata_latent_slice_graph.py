from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from src.policy.diagnostic_graph_metrics import build_graph_diagnostics


WIKIDATA_LATENT_SLICE_GRAPH_SCHEMA_VERSION = "sl.wikidata_latent_slice_graph.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _node(*, node_id: str, kind: str, label: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": _text(node_id),
        "kind": _text(kind),
        "label": _text(label),
        "metadata": dict(metadata or {}),
    }


def _edge(*, source: str, target: str, kind: str) -> dict[str, Any]:
    return {
        "source": _text(source),
        "target": _text(target),
        "kind": _text(kind),
    }


def _emission_diagnostics(*, graph_payload: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph_payload.get("nodes") if isinstance(graph_payload.get("nodes"), list) else []
    edges = graph_payload.get("edges") if isinstance(graph_payload.get("edges"), list) else []
    node_id_counts = Counter(
        _text(row.get("id"))
        for row in nodes
        if isinstance(row, Mapping) and _text(row.get("id"))
    )
    duplicate_node_ids = {
        node_id: count
        for node_id, count in sorted(node_id_counts.items())
        if count > 1
    }
    return {
        "emitted_node_count": len(nodes),
        "emitted_edge_count": len(edges),
        "unique_node_count": len(node_id_counts),
        "duplicate_node_id_count": len(duplicate_node_ids),
        "duplicate_node_emission_count": len(nodes) - len(node_id_counts),
        "duplicate_node_ids": duplicate_node_ids,
    }


def _flatness_indicators(*, graph_payload: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph_payload.get("nodes") if isinstance(graph_payload.get("nodes"), list) else []
    edges = graph_payload.get("edges") if isinstance(graph_payload.get("edges"), list) else []
    node_kind_counts: dict[str, int] = {}
    for row in nodes:
        if not isinstance(row, Mapping):
            continue
        kind = _text(row.get("kind"))
        if kind:
            node_kind_counts[kind] = node_kind_counts.get(kind, 0) + 1
    entity_count = node_kind_counts.get("candidate_entity", 0)
    property_count = node_kind_counts.get("candidate_property", 0)
    residual_count = node_kind_counts.get("residual", 0)
    receipt_count = node_kind_counts.get("receipt", 0)
    unique_node_kind_count = len(node_kind_counts)
    branching_factor = round(len(edges) / len(nodes), 6) if nodes else 0.0

    if entity_count == 0 and property_count == 0:
        posture = "missing_authority_structure"
    elif residual_count > entity_count + property_count:
        posture = "residual_heavy"
    elif unique_node_kind_count <= 2 or branching_factor <= 1.0:
        posture = "projection_flat"
    else:
        posture = "structured"

    return {
        "flatness_posture": posture,
        "candidate_entity_count": entity_count,
        "candidate_property_count": property_count,
        "residual_count": residual_count,
        "receipt_count": receipt_count,
        "unique_node_kind_count": unique_node_kind_count,
        "branching_factor": branching_factor,
        "promotion_status": _text(bundle.get("promotion_status")),
    }


def build_wikidata_latent_slice_graph(bundle: Mapping[str, Any]) -> dict[str, Any]:
    lane_id = _text(bundle.get("lane_id")) or "unknown_lane"
    lane_family = _text(bundle.get("lane_family"))
    nodes: list[dict[str, Any]] = [
        _node(
            node_id=f"lane:{lane_id}",
            kind="lane",
            label=lane_id,
            metadata={
                "lane_family": lane_family,
                "signal_kind": _text(bundle.get("signal_kind")),
                "authority_surface": _text(bundle.get("authority_surface")),
                "promotion_status": _text(bundle.get("promotion_status")),
            },
        )
    ]
    edges: list[dict[str, Any]] = []

    for row in bundle.get("candidate_entities", []):
        if not isinstance(row, Mapping):
            continue
        qid = _text(row.get("qid"))
        if not qid:
            continue
        node_id = f"entity:{qid}:{_text(row.get('role')) or 'candidate'}"
        nodes.append(
            _node(
                node_id=node_id,
                kind="candidate_entity",
                label=_text(row.get("label")) or qid,
                metadata={"qid": qid, "role": _text(row.get("role")), "status": _text(row.get("status"))},
            )
        )
        edges.append(_edge(source=f"lane:{lane_id}", target=node_id, kind="projects_entity"))

    for row in bundle.get("candidate_properties", []):
        if not isinstance(row, Mapping):
            continue
        pid = _text(row.get("pid"))
        if not pid:
            continue
        node_id = f"property:{pid}:{_text(row.get('role')) or 'candidate'}"
        nodes.append(
            _node(
                node_id=node_id,
                kind="candidate_property",
                label=pid,
                metadata={"pid": pid, "role": _text(row.get("role")), "status": _text(row.get("status"))},
            )
        )
        edges.append(_edge(source=f"lane:{lane_id}", target=node_id, kind="projects_property"))

    for index, row in enumerate(bundle.get("residuals", []), start=1):
        if not isinstance(row, Mapping):
            continue
        code = _text(row.get("code")) or f"residual_{index}"
        node_id = f"residual:{lane_id}:{index}"
        nodes.append(
            _node(
                node_id=node_id,
                kind="residual",
                label=code,
                metadata={"code": code, "status": _text(row.get("status")), "detail": _text(row.get("detail"))},
            )
        )
        edges.append(_edge(source=f"lane:{lane_id}", target=node_id, kind="has_residual"))

    for index, row in enumerate(bundle.get("receipts", []), start=1):
        if not isinstance(row, Mapping):
            continue
        kind = _text(row.get("kind")) or f"receipt_{index}"
        value = _text(row.get("value"))
        node_id = f"receipt:{lane_id}:{index}"
        nodes.append(
            _node(
                node_id=node_id,
                kind="receipt",
                label=kind,
                metadata={"kind": kind, "value": value, "status": _text(row.get("status"))},
            )
        )
        edges.append(_edge(source=f"lane:{lane_id}", target=node_id, kind="has_receipt"))

    graph_payload = {"nodes": nodes, "edges": edges}
    diagnostics = build_graph_diagnostics(
        graph_payload=graph_payload,
        source_artifact_id=lane_id,
        source_lane="wikidata",
        substrate_kind="wikidata_signal_review_bundle",
        projection_role="latent_slice_graph",
        graph_version=WIKIDATA_LATENT_SLICE_GRAPH_SCHEMA_VERSION,
        cone_seed_node_kinds=["lane"],
        cone_allowed_edge_types=["projects_entity", "projects_property", "has_residual", "has_receipt"],
        cone_max_depth=1,
    )
    return {
        "schema_version": WIKIDATA_LATENT_SLICE_GRAPH_SCHEMA_VERSION,
        "lane_id": lane_id,
        "lane_family": lane_family,
        "bundle_schema_version": _text(bundle.get("schema_version")),
        "graph_payload": graph_payload,
        "diagnostics": diagnostics,
        "emission_diagnostics": _emission_diagnostics(graph_payload=graph_payload),
        "flatness_indicators": _flatness_indicators(graph_payload=graph_payload, bundle=bundle),
    }


__all__ = [
    "WIKIDATA_LATENT_SLICE_GRAPH_SCHEMA_VERSION",
    "build_wikidata_latent_slice_graph",
]
