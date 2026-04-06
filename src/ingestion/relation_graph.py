from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RelationNode:
    node_id: str
    node_kind: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "label": self.label,
        }


@dataclass(frozen=True)
class RelationEdge:
    source_id: str
    edge_kind: str
    target_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "edge_kind": self.edge_kind,
            "target_id": self.target_id,
        }


@dataclass(frozen=True)
class RelationGraph:
    graph_id: str
    nodes: tuple[RelationNode, ...] = field(default_factory=tuple)
    edges: tuple[RelationEdge, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _observation_text(observation: Mapping[str, Any]) -> str:
    direct = _clean_text(observation.get("text"))
    if direct:
        return direct
    review_text = observation.get("review_text")
    if isinstance(review_text, Mapping):
        return _clean_text(review_text.get("text"))
    return ""


def _role_text(observation: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = observation.get(key)
        if isinstance(value, str):
            text = _clean_text(value)
            if text:
                return text
    return ""


def _role_texts(observation: Mapping[str, Any], *keys: str) -> set[str]:
    values: set[str] = set()
    for key in keys:
        value = observation.get(key)
        if isinstance(value, str):
            text = _clean_text(value)
            if text:
                values.add(text)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                if isinstance(item, str):
                    text = _clean_text(item)
                    if text:
                        values.add(text)
    return values


def _anchor_values(observation: Mapping[str, Any], anchor_kind: str) -> set[str]:
    raw = observation.get("candidate_anchors")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return set()
    values: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        if _clean_text(item.get("anchor_kind")) != anchor_kind:
            continue
        for key in ("anchor_value", "anchor_label"):
            text = _clean_text(item.get(key))
            if text:
                values.add(text)
    return values


def _source_id(observation: Mapping[str, Any]) -> str:
    direct = _role_text(observation, "source_id", "source_row_id")
    if direct:
        return direct
    review_text = observation.get("review_text")
    if isinstance(review_text, Mapping):
        text_ref = review_text.get("text_ref")
        if isinstance(text_ref, Mapping):
            for key in ("text_id", "envelope_id"):
                text = _clean_text(text_ref.get(key))
                if text:
                    return text
    provenance = observation.get("provenance")
    if isinstance(provenance, Mapping):
        for key in ("text_id", "envelope_id"):
            text = _clean_text(provenance.get(key))
            if text:
                return text
    fallback = _role_text(observation, "claim_id")
    if fallback:
        return fallback
    return ""


def _event_id(observation: Mapping[str, Any], index: int) -> str:
    for key in ("event_id", "review_item_id", "claim_id"):
        text = _role_text(observation, key)
        if text:
            return text
    source_id = _source_id(observation)
    if source_id:
        return f"event:{source_id}"
    return f"event:{index}"


def build_relation_graph(
    observations: Sequence[Mapping[str, Any]],
    *,
    graph_id: str = "relation_graph",
) -> RelationGraph:
    nodes: dict[str, RelationNode] = {}
    edges: list[RelationEdge] = []

    def add_node(node_id: str, node_kind: str, label: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = RelationNode(
                node_id=node_id,
                node_kind=node_kind,
                label=label,
            )

    def add_edge(source_id: str, edge_kind: str, target_id: str) -> None:
        edge = RelationEdge(
            source_id=source_id,
            edge_kind=edge_kind,
            target_id=target_id,
        )
        if edge not in edges:
            edges.append(edge)

    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            continue
        text = _observation_text(observation)
        if not text:
            continue
        event_id = _event_id(observation, index)
        add_node(event_id, "event", text)

        actor = _role_text(observation, "actor", "subject")
        if actor:
            actor_id = f"actor:{actor}"
            add_node(actor_id, "actor", actor)
            add_edge(actor_id, "acts_in", event_id)

        action = _role_text(observation, "action", "predicate")
        if action:
            action_id = f"action:{action}"
            add_node(action_id, "action", action)
            add_edge(event_id, "has_action", action_id)

        object_text = _role_text(observation, "object")
        if object_text:
            object_id = f"object:{object_text}"
            add_node(object_id, "object", object_text)
            add_edge(event_id, "acts_on", object_id)

        source_id = _source_id(observation)
        if source_id:
            source_node_id = f"source:{source_id}"
            add_node(source_node_id, "source", source_id)
            add_edge(event_id, "from_source", source_node_id)

    return RelationGraph(
        graph_id=graph_id,
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def relational_signature(graph: RelationGraph) -> dict[str, set[str]]:
    return {
        "actor_set": {
            node.label for node in graph.nodes if node.node_kind == "actor"
        },
        "action_set": {
            node.label for node in graph.nodes if node.node_kind == "action"
        },
        "object_set": {
            node.label for node in graph.nodes if node.node_kind == "object"
        },
        "edge_types": {
            edge.edge_kind for edge in graph.edges
        },
        "edge_role_set": {
            f"{_node_kind_for_edge_end(graph, edge.source_id)}>{edge.edge_kind}>{_node_kind_for_edge_end(graph, edge.target_id)}"
            for edge in graph.edges
        },
    }


def observation_signature(observations: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    graph = build_relation_graph(observations)
    signature = relational_signature(graph)
    source_families: set[str] = set()
    workload_classes: set[str] = set()
    support_kinds: set[str] = set()
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        source_families |= _role_texts(observation, "source_family")
        workload_classes |= _role_texts(observation, "primary_workload_class", "workload_classes")
        support_kinds |= _anchor_values(observation, "support_kind")
    signature["source_family_set"] = source_families
    signature["workload_class_set"] = workload_classes
    signature["support_kind_set"] = support_kinds
    return signature


def _node_kind_for_edge_end(graph: RelationGraph, node_id: str) -> str:
    for node in graph.nodes:
        if node.node_id == node_id:
            return node.node_kind
    return "unknown"


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / (len(left | right) or 1)


def relational_similarity(left: RelationGraph, right: RelationGraph) -> float:
    left_sig = relational_signature(left)
    right_sig = relational_signature(right)
    scores = [
        _jaccard(left_sig["actor_set"], right_sig["actor_set"]),
        _jaccard(left_sig["action_set"], right_sig["action_set"]),
        _jaccard(left_sig["object_set"], right_sig["object_set"]),
        _jaccard(left_sig["edge_types"], right_sig["edge_types"]),
        _jaccard(left_sig["edge_role_set"], right_sig["edge_role_set"]),
    ]
    return round(sum(scores) / len(scores), 6)


def build_relation_similarity_summary(
    left_candidate: Sequence[Mapping[str, Any]],
    right_candidate: Sequence[Mapping[str, Any]],
    *,
    left_id: str,
    right_id: str,
) -> dict[str, Any]:
    left_graph = build_relation_graph(left_candidate, graph_id=left_id)
    right_graph = build_relation_graph(right_candidate, graph_id=right_id)
    left_signature = observation_signature(left_candidate)
    right_signature = observation_signature(right_candidate)
    similarity = relational_similarity(left_graph, right_graph)

    shared_features = {
        "actors": sorted(left_signature["actor_set"] & right_signature["actor_set"]),
        "actions": sorted(left_signature["action_set"] & right_signature["action_set"]),
        "objects": sorted(left_signature["object_set"] & right_signature["object_set"]),
        "edge_types": sorted(left_signature["edge_types"] & right_signature["edge_types"]),
        "edge_roles": sorted(left_signature["edge_role_set"] & right_signature["edge_role_set"]),
        "source_families": sorted(left_signature["source_family_set"] & right_signature["source_family_set"]),
        "workload_classes": sorted(left_signature["workload_class_set"] & right_signature["workload_class_set"]),
        "support_kinds": sorted(left_signature["support_kind_set"] & right_signature["support_kind_set"]),
    }
    distinct_features = {
        "left_only": {
            "actors": sorted(left_signature["actor_set"] - right_signature["actor_set"]),
            "actions": sorted(left_signature["action_set"] - right_signature["action_set"]),
            "objects": sorted(left_signature["object_set"] - right_signature["object_set"]),
            "edge_types": sorted(left_signature["edge_types"] - right_signature["edge_types"]),
            "edge_roles": sorted(left_signature["edge_role_set"] - right_signature["edge_role_set"]),
            "source_families": sorted(left_signature["source_family_set"] - right_signature["source_family_set"]),
            "workload_classes": sorted(left_signature["workload_class_set"] - right_signature["workload_class_set"]),
            "support_kinds": sorted(left_signature["support_kind_set"] - right_signature["support_kind_set"]),
        },
        "right_only": {
            "actors": sorted(right_signature["actor_set"] - left_signature["actor_set"]),
            "actions": sorted(right_signature["action_set"] - left_signature["action_set"]),
            "objects": sorted(right_signature["object_set"] - left_signature["object_set"]),
            "edge_types": sorted(right_signature["edge_types"] - left_signature["edge_types"]),
            "edge_roles": sorted(right_signature["edge_role_set"] - left_signature["edge_role_set"]),
            "source_families": sorted(right_signature["source_family_set"] - left_signature["source_family_set"]),
            "workload_classes": sorted(right_signature["workload_class_set"] - left_signature["workload_class_set"]),
            "support_kinds": sorted(right_signature["support_kind_set"] - left_signature["support_kind_set"]),
        },
    }
    return {
        "left_candidate_id": left_id,
        "right_candidate_id": right_id,
        "left_graph": left_graph.to_dict(),
        "right_graph": right_graph.to_dict(),
        "left_signature": _serialize_signature(left_signature),
        "right_signature": _serialize_signature(right_signature),
        "similarity": similarity,
        "shared_features": shared_features,
        "distinct_features": distinct_features,
        "provisional_readout": {
            "comparison_band": _comparison_band(similarity),
            "information_level": _information_level(left_signature, right_signature),
        },
    }


def build_seed_relation_comparison(
    source_review_rows: Sequence[Mapping[str, Any]],
    *,
    seed_id: str,
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    source_families: dict[str, str] = {}
    for row in source_review_rows:
        if not isinstance(row, Mapping):
            continue
        if _clean_text(row.get("seed_id")) != seed_id:
            continue
        source_row_id = _clean_text(row.get("source_row_id"))
        if not source_row_id:
            continue
        grouped.setdefault(source_row_id, []).append(row)
        source_families[source_row_id] = _clean_text(row.get("source_family"))

    candidate_graphs = []
    for source_row_id, rows in grouped.items():
        graph = build_relation_graph(rows, graph_id=source_row_id)
        candidate_graphs.append(
            {
                "source_row_id": source_row_id,
                "source_family": source_families.get(source_row_id, ""),
                "graph": graph.to_dict(),
                "signature": _serialize_signature(observation_signature(rows)),
            }
        )

    pairwise_comparisons = []
    for left_id, right_id in combinations(sorted(grouped), 2):
        summary = build_relation_similarity_summary(
            grouped[left_id],
            grouped[right_id],
            left_id=left_id,
            right_id=right_id,
        )
        pairwise_comparisons.append(
            {
                "left_source_row_id": left_id,
                "right_source_row_id": right_id,
                "left_source_family": source_families.get(left_id, ""),
                "right_source_family": source_families.get(right_id, ""),
                "similarity": summary["similarity"],
                "left_signature": summary["left_signature"],
                "right_signature": summary["right_signature"],
                "provisional_readout": summary["provisional_readout"],
            }
        )

    return {
        "seed_id": seed_id,
        "candidate_graphs": candidate_graphs,
        "pairwise_comparisons": pairwise_comparisons,
    }


def build_seed_relation_clusters(
    source_review_rows: Sequence[Mapping[str, Any]],
    *,
    seed_id: str,
) -> dict[str, Any]:
    comparison = build_seed_relation_comparison(source_review_rows, seed_id=seed_id)
    candidate_ids = [item["source_row_id"] for item in comparison["candidate_graphs"]]
    families = {
        item["source_row_id"]: item["source_family"]
        for item in comparison["candidate_graphs"]
    }

    adjacency: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidate_ids}
    for item in comparison["pairwise_comparisons"]:
        if item["provisional_readout"]["comparison_band"] != "near_equivalent":
            continue
        left_id = item["left_source_row_id"]
        right_id = item["right_source_row_id"]
        adjacency.setdefault(left_id, set()).add(right_id)
        adjacency.setdefault(right_id, set()).add(left_id)

    visited: set[str] = set()
    clusters: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        if candidate_id in visited:
            continue
        pending = [candidate_id]
        members: list[str] = []
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            members.append(current)
            pending.extend(sorted(adjacency.get(current, ())))
        members = sorted(members)
        size = len(members)
        if size > 1:
            cluster_kind = "near_equivalent_cluster"
        else:
            cluster_kind = "singleton_candidate"
        clusters.append(
            {
                "cluster_id": f"cluster:{seed_id}:{len(clusters)+1:02d}",
                "cluster_kind": cluster_kind,
                "member_source_row_ids": members,
                "member_source_families": [families.get(member, "") for member in members],
                "provisional_readout": {
                    "comparison_band": "near_equivalent" if size > 1 else "distinct",
                    "information_level": _cluster_information_level(
                        comparison["candidate_graphs"],
                        members,
                    ),
                },
            }
        )

    return {
        "seed_id": seed_id,
        "candidate_count": len(candidate_ids),
        "pairwise_comparison_count": len(comparison["pairwise_comparisons"]),
        "clusters": clusters,
        "pairwise_comparisons": comparison["pairwise_comparisons"],
    }


def build_provisional_invariant_readout(
    source_review_rows: Sequence[Mapping[str, Any]],
    *,
    seed_id: str,
) -> dict[str, Any]:
    clustered = build_seed_relation_clusters(source_review_rows, seed_id=seed_id)
    invariants: list[dict[str, Any]] = []
    for cluster in clustered["clusters"]:
        if cluster["cluster_kind"] != "near_equivalent_cluster":
            continue
        member_ids = set(cluster["member_source_row_ids"])
        matching_comparisons = [
            item
            for item in clustered["pairwise_comparisons"]
            if item["left_source_row_id"] in member_ids
            and item["right_source_row_id"] in member_ids
        ]
        if matching_comparisons:
            similarity = round(
                sum(item["similarity"] for item in matching_comparisons) / len(matching_comparisons),
                6,
            )
        else:
            similarity = 1.0
        invariants.append(
            {
                "provisional_invariant_id": cluster["cluster_id"].replace("cluster:", "invariant:", 1),
                "seed_id": seed_id,
                "member_source_row_ids": cluster["member_source_row_ids"],
                "member_source_families": cluster["member_source_families"],
                "supporting_pairwise_count": len(matching_comparisons),
                "average_similarity": similarity,
                "status": "provisional_invariant",
                "provisional_readout": {
                    "comparison_band": "near_equivalent",
                    "information_level": cluster["provisional_readout"]["information_level"],
                },
            }
        )

    return {
        "seed_id": seed_id,
        "candidate_count": clustered["candidate_count"],
        "pairwise_comparison_count": clustered["pairwise_comparison_count"],
        "provisional_invariants": invariants,
        "clusters": clustered["clusters"],
    }


def _serialize_signature(signature: Mapping[str, set[str]]) -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in signature.items()}


def _information_level(
    left_signature: Mapping[str, set[str]],
    right_signature: Mapping[str, set[str]],
) -> str:
    semantic_keys = ("actor_set", "action_set", "object_set")
    semantic_signal_count = sum(
        len(left_signature[key] | right_signature[key]) for key in semantic_keys
    )
    if semantic_signal_count > 0:
        return "semantic_rich"
    return "low_information"


def _cluster_information_level(
    candidate_graphs: Sequence[Mapping[str, Any]],
    member_ids: Sequence[str],
) -> str:
    signatures = {
        item["source_row_id"]: item["signature"]
        for item in candidate_graphs
        if isinstance(item, Mapping) and isinstance(item.get("signature"), Mapping)
    }
    for member_id in member_ids:
        signature = signatures.get(member_id, {})
        if any(signature.get(key) for key in ("actor_set", "action_set", "object_set")):
            return "semantic_rich"
    return "low_information"


def _comparison_band(similarity: float) -> str:
    if similarity >= 0.85:
        return "near_equivalent"
    if similarity >= 0.45:
        return "partially_overlapping"
    return "distinct"


__all__ = [
    "RelationEdge",
    "RelationGraph",
    "build_relation_similarity_summary",
    "build_provisional_invariant_readout",
    "build_seed_relation_clusters",
    "build_seed_relation_comparison",
    "RelationNode",
    "build_relation_graph",
    "observation_signature",
    "relational_signature",
    "relational_similarity",
]
