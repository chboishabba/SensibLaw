from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable, Mapping

SL_LATENT_PROMOTED_GRAPH_VERSION = "sl.latent_promoted_graph.v1"
SL_LATENT_PROMOTED_GRAPH_PROVENANCE_RULE_VERSION = "sl.latent_graph.promoted_anchor_only.v1"


def _stable_hash(parts: Iterable[object]) -> str:
    payload = "||".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _authority_type(record: Mapping[str, Any]) -> str:
    rule_type = str(record.get("rule_type") or "").strip()
    predicate_key = str(record.get("predicate_key") or "").strip()
    subject_key = str(record.get("subject_key") or "").strip().lower()
    object_key = str(record.get("object_key") or "").strip().lower()

    if "court" in object_key or predicate_key in {"heard_by", "ruled_by", "challenged", "appealed"}:
        return "judicial"
    if "senate" in object_key or "congress" in object_key:
        return "legislative"
    if rule_type == "executive_action" or predicate_key in {"signed", "vetoed"} or "president" in subject_key or "bush" in subject_key:
        return "executive"
    if rule_type == "review_relation":
        return "judicial"
    if rule_type == "governance_action":
        return "governance"
    return "unknown"


def _node_type(kind: str) -> str:
    if kind == "actor":
        return "actor"
    if kind == "legal_ref":
        return "legal_ref"
    raise ValueError(f"unsupported promoted record kind for latent graph: {kind}")


def _node_ref(system_id: str, node_type: str, key: str) -> str:
    digest = _stable_hash((system_id, node_type, key))[:16]
    return f"latent://{system_id}/node/{node_type}/{digest}"


def _edge_ref(system_id: str, edge_type: str, src: str, dst: str) -> str:
    digest = _stable_hash((system_id, edge_type, src, dst))[:16]
    return f"latent://{system_id}/edge/{edge_type}/{digest}"


def _motif_signature(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("rule_type") or ""),
        str(record.get("predicate_key") or ""),
        str(record.get("subject_kind") or ""),
        str(record.get("object_kind") or ""),
    )


def _motif_label(signature: tuple[str, str, str, str]) -> str:
    rule_type, predicate_key, subject_kind, object_kind = signature
    return f"{rule_type}:{predicate_key}:{subject_kind}->{object_kind}"


def _provenance_index(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "provenance_ref": record["record_ref"],
            "system_id": record["system_id"],
            "run_id": record["run_id"],
            "event_id": record["event_id"],
            "predicate_key": record["predicate_key"],
            "source_document_id": record["source_document_id"],
            "source_char_start": record["source_char_start"],
            "source_char_end": record["source_char_end"],
            "event_text": record["event_text"],
        }
        for record in records
    ]


def _typing_rules() -> list[dict[str, str]]:
    return [
        {"src_node_type": "fact", "edge_type": "instantiated_by", "dst_node_type": "actor"},
        {"src_node_type": "fact", "edge_type": "instantiated_by", "dst_node_type": "legal_ref"},
        {"src_node_type": "fact", "edge_type": "refers_to", "dst_node_type": "document"},
        {"src_node_type": "fact", "edge_type": "member_of", "dst_node_type": "motif"},
        {"src_node_type": "fact", "edge_type": "applies_to", "dst_node_type": "authority"},
    ]


def _constraint_rows(system_id: str) -> list[dict[str, Any]]:
    return [
        {
            "constraint_id": f"constraint://{system_id}/anchored-promoted-records-only",
            "constraint_type": "consistency_constraint",
            "scope": "graph",
            "expression": "Every node and edge provenance ref must resolve to a promoted anchored record in provenance_index.",
            "provenance_refs": [],
            "severity": "error",
        },
        {
            "constraint_id": f"constraint://{system_id}/fact-instantiation-typing",
            "constraint_type": "type_constraint",
            "scope": "edge:instantiated_by",
            "expression": "instantiated_by edges may only connect fact nodes to actor or legal_ref nodes.",
            "provenance_refs": [],
            "severity": "error",
        },
        {
            "constraint_id": f"constraint://{system_id}/motif-membership-typing",
            "constraint_type": "type_constraint",
            "scope": "edge:member_of",
            "expression": "member_of edges may only connect fact nodes to motif nodes.",
            "provenance_refs": [],
            "severity": "error",
        },
    ]


def build_latent_promoted_graph(
    *,
    system_id: str,
    promoted_basis_ref: str,
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if not records:
        raise ValueError("records must be non-empty")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    record_index: list[dict[str, Any]] = []
    entity_nodes: dict[str, str] = {}
    document_nodes: dict[str, str] = {}
    authority_nodes: dict[str, str] = {}
    fact_node_refs: dict[str, str] = {}
    motif_members: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    motif_support_refs: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)

    def ensure_node(
        *,
        node_ref: str,
        node_type: str,
        label: str,
        payload: Mapping[str, Any],
        provenance_refs: list[str],
        confidence: float = 1.0,
        temporal_scope: str | None = None,
        jurisdiction_scope: str | None = None,
    ) -> str:
        if any(row["node_ref"] == node_ref for row in nodes):
            return node_ref
        nodes.append(
            {
                "node_ref": node_ref,
                "system_id": system_id,
                "node_type": node_type,
                "label": label,
                "payload": dict(payload),
                "provenance_refs": provenance_refs,
                "confidence": confidence,
                "temporal_scope": temporal_scope,
                "jurisdiction_scope": jurisdiction_scope,
            }
        )
        return node_ref

    for record in records:
        record_ref = str(record["record_ref"])
        fact_node_ref = _node_ref(system_id, "fact", record_ref)
        fact_node_refs[record_ref] = fact_node_ref
        ensure_node(
            node_ref=fact_node_ref,
            node_type="fact",
            label=str(record.get("display_label") or record.get("predicate_key") or record_ref),
            payload={
                "predicate_key": record["predicate_key"],
                "display_label": record["display_label"],
                "rule_type": record.get("rule_type"),
                "subject_key": record["subject_key"],
                "object_key": record["object_key"],
            },
            provenance_refs=[record_ref],
        )

        source_document_id = str(record["source_document_id"])
        document_node_ref = document_nodes.setdefault(
            source_document_id,
            _node_ref(system_id, "document", source_document_id),
        )
        ensure_node(
            node_ref=document_node_ref,
            node_type="document",
            label=source_document_id,
            payload={"source_document_id": source_document_id},
            provenance_refs=[record_ref],
        )
        edges.append(
            {
                "edge_ref": _edge_ref(system_id, "refers_to", fact_node_ref, document_node_ref),
                "src": fact_node_ref,
                "dst": document_node_ref,
                "edge_type": "refers_to",
                "payload": {},
                "provenance_refs": [record_ref],
                "confidence": 1.0,
            }
        )

        authority_type = _authority_type(record)
        authority_node_ref = authority_nodes.setdefault(
            authority_type,
            _node_ref(system_id, "authority", authority_type),
        )
        ensure_node(
            node_ref=authority_node_ref,
            node_type="authority",
            label=authority_type,
            payload={"authority_type": authority_type},
            provenance_refs=[record_ref],
        )
        edges.append(
            {
                "edge_ref": _edge_ref(system_id, "applies_to", fact_node_ref, authority_node_ref),
                "src": fact_node_ref,
                "dst": authority_node_ref,
                "edge_type": "applies_to",
                "payload": {"authority_type": authority_type},
                "provenance_refs": [record_ref],
                "confidence": 1.0,
            }
        )

        entity_refs: dict[str, str] = {}
        for role, key_field, kind_field in (
            ("subject", "subject_key", "subject_kind"),
            ("object", "object_key", "object_kind"),
        ):
            entity_key = str(record[key_field])
            entity_kind = _node_type(str(record[kind_field]))
            entity_node_ref = entity_nodes.setdefault(
                entity_key,
                _node_ref(system_id, entity_kind, entity_key),
            )
            entity_refs[role] = entity_node_ref
            ensure_node(
                node_ref=entity_node_ref,
                node_type=entity_kind,
                label=entity_key,
                payload={"canonical_key": entity_key},
                provenance_refs=[record_ref],
            )
            edges.append(
                {
                    "edge_ref": _edge_ref(system_id, "instantiated_by", fact_node_ref, entity_node_ref),
                    "src": fact_node_ref,
                    "dst": entity_node_ref,
                    "edge_type": "instantiated_by",
                    "payload": {"role": role},
                    "provenance_refs": [record_ref],
                    "confidence": 1.0,
                }
            )

        signature = _motif_signature(record)
        motif_members[signature].append(fact_node_ref)
        motif_support_refs[signature].append(record_ref)

        record_index.append(
            {
                "record_ref": record_ref,
                "fact_node_ref": fact_node_ref,
                "subject_node_ref": entity_refs["subject"],
                "object_node_ref": entity_refs["object"],
                "document_node_ref": document_node_ref,
                "authority_node_ref": authority_node_ref,
                "motif_node_refs": [],
            }
        )

    for signature, member_refs in motif_members.items():
        motif_node_ref = _node_ref(system_id, "motif", "|".join(signature))
        support_refs = sorted(set(motif_support_refs[signature]))
        ensure_node(
            node_ref=motif_node_ref,
            node_type="motif",
            label=_motif_label(signature),
            payload={
                "signature": {
                    "rule_type": signature[0],
                    "predicate_key": signature[1],
                    "subject_kind": signature[2],
                    "object_kind": signature[3],
                },
                "support_count": len(member_refs),
            },
            provenance_refs=support_refs,
        )
        for fact_node_ref in member_refs:
            edges.append(
                {
                    "edge_ref": _edge_ref(system_id, "member_of", fact_node_ref, motif_node_ref),
                    "src": fact_node_ref,
                    "dst": motif_node_ref,
                    "edge_type": "member_of",
                    "payload": {},
                    "provenance_refs": [next(row["record_ref"] for row in record_index if row["fact_node_ref"] == fact_node_ref)],
                    "confidence": 1.0,
                }
            )
        for row in record_index:
            if row["fact_node_ref"] in member_refs:
                row["motif_node_refs"].append(motif_node_ref)

    graph_id = f"latent://{system_id}/graph/{_stable_hash((system_id, promoted_basis_ref, len(records)))[:16]}"
    node_type_counts: dict[str, int] = defaultdict(int)
    edge_type_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        node_type_counts[str(node["node_type"])] += 1
    for edge in edges:
        edge_type_counts[str(edge["edge_type"])] += 1

    return {
        "payload_version": SL_LATENT_PROMOTED_GRAPH_VERSION,
        "graph_id": graph_id,
        "system_id": system_id,
        "promoted_basis_ref": promoted_basis_ref,
        "provenance_rule": {
            "rule_id": SL_LATENT_PROMOTED_GRAPH_PROVENANCE_RULE_VERSION,
            "description": "All latent graph nodes and edges must resolve to promoted anchored records via provenance_index.",
            "anchored_promoted_records_only": True,
        },
        "typing_rules": _typing_rules(),
        "nodes": nodes,
        "edges": edges,
        "constraints": _constraint_rows(system_id),
        "record_index": record_index,
        "provenance_index": _provenance_index(records),
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "constraint_count": 3,
            "fact_node_count": node_type_counts["fact"],
            "motif_node_count": node_type_counts["motif"],
            "node_type_counts": dict(sorted(node_type_counts.items())),
            "edge_type_counts": dict(sorted(edge_type_counts.items())),
        },
    }


__all__ = [
    "SL_LATENT_PROMOTED_GRAPH_PROVENANCE_RULE_VERSION",
    "SL_LATENT_PROMOTED_GRAPH_VERSION",
    "build_latent_promoted_graph",
]
