"""Generic, derived-only follow projections.

The carrier deliberately uses relational rows rather than a nested graph
mapping.  A JSON graph is a boundary representation and must be recreated from
these rows; it is never accepted as semantic input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


FOLLOW_PROJECTION_SCHEMA_VERSION = "sl.follow_projection.v0_1"
DERIVED_ONLY_AUTHORITY = "derived_only_challengeable"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _refs(values: Sequence[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({_text(value) for value in values or () if _text(value)}))


@dataclass(frozen=True)
class FollowNode:
    projection_ref: str
    node_ref: str
    node_kind: str
    label: str
    document_ref: str | None = None
    factor_revision_ref: str | None = None
    domain_ir_ref: str | None = None
    source_record_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_ref": self.projection_ref,
            "node_ref": self.node_ref,
            "node_kind": self.node_kind,
            "label": self.label,
            "document_ref": self.document_ref,
            "factor_revision_ref": self.factor_revision_ref,
            "domain_ir_ref": self.domain_ir_ref,
            "source_record_ref": self.source_record_ref,
        }


@dataclass(frozen=True)
class FollowEdge:
    projection_ref: str
    edge_ref: str
    from_node_ref: str
    to_node_ref: str
    relation_kind: str
    admissibility_state: str
    provenance_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    admissibility_ground_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_ref": self.projection_ref,
            "edge_ref": self.edge_ref,
            "from_node_ref": self.from_node_ref,
            "to_node_ref": self.to_node_ref,
            "relation_kind": self.relation_kind,
            "admissibility_state": self.admissibility_state,
            "provenance_refs": list(self.provenance_refs),
            "evidence_refs": list(self.evidence_refs),
            "admissibility_ground_refs": list(self.admissibility_ground_refs),
        }


def build_follow_projection(
    *,
    document_ref: str,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    projection_kind: str = "follow",
) -> dict[str, Any]:
    """Build a deterministic, non-promoting relational follow projection."""

    normalized_nodes = [
        FollowNode(
            projection_ref="",
            node_ref=_text(row.get("node_ref") or row.get("id")),
            node_kind=_text(row.get("node_kind") or row.get("kind")) or "candidate",
            label=_text(row.get("label"))
            or _text(row.get("node_ref") or row.get("id")),
            document_ref=_text(row.get("document_ref")) or _text(document_ref) or None,
            factor_revision_ref=_text(row.get("factor_revision_ref")) or None,
            domain_ir_ref=_text(row.get("domain_ir_ref")) or None,
            source_record_ref=_text(row.get("source_record_ref")) or None,
        )
        for row in nodes
        if _text(row.get("node_ref") or row.get("id"))
    ]
    node_refs = {row.node_ref for row in normalized_nodes}
    raw_edges = [
        row
        for row in edges
        if _text(row.get("from_node_ref") or row.get("source") or row.get("from"))
        in node_refs
        and _text(row.get("to_node_ref") or row.get("target") or row.get("to"))
        in node_refs
    ]
    projection_ref = "follow-projection:" + canonical_sha256(
        {
            "document_ref": document_ref,
            "projection_kind": projection_kind,
            "nodes": [
                row.to_dict()
                for row in sorted(normalized_nodes, key=lambda item: item.node_ref)
            ],
            "edges": [dict(row) for row in raw_edges],
            "contract": FOLLOW_PROJECTION_SCHEMA_VERSION,
        }
    )
    final_nodes = [
        FollowNode(**{**row.__dict__, "projection_ref": projection_ref})
        for row in normalized_nodes
    ]
    final_edges: list[FollowEdge] = []
    for row in raw_edges:
        source = _text(row.get("from_node_ref") or row.get("source") or row.get("from"))
        target = _text(row.get("to_node_ref") or row.get("target") or row.get("to"))
        relation = _text(row.get("relation_kind") or row.get("kind")) or "follows"
        edge_ref = _text(
            row.get("edge_ref") or row.get("id")
        ) or "follow-edge:" + canonical_sha256(
            (projection_ref, source, target, relation)
        )
        final_edges.append(
            FollowEdge(
                projection_ref=projection_ref,
                edge_ref=edge_ref,
                from_node_ref=source,
                to_node_ref=target,
                relation_kind=relation,
                admissibility_state=_text(row.get("admissibility_state"))
                or "challengeable",
                provenance_refs=_refs(row.get("provenance_refs")),
                evidence_refs=_refs(row.get("evidence_refs")),
                admissibility_ground_refs=_refs(row.get("admissibility_ground_refs")),
            )
        )
    return {
        "schema_version": FOLLOW_PROJECTION_SCHEMA_VERSION,
        "projection_ref": projection_ref,
        "projection_kind": _text(projection_kind) or "follow",
        "document_ref": _text(document_ref),
        "authority": DERIVED_ONLY_AUTHORITY,
        "promotion_allowed": False,
        "execution_allowed": False,
        "nodes": [
            row.to_dict() for row in sorted(final_nodes, key=lambda item: item.node_ref)
        ],
        "edges": [
            row.to_dict() for row in sorted(final_edges, key=lambda item: item.edge_ref)
        ],
    }


def project_follow_view(
    projection: Mapping[str, Any], *, relation_prefix: str | None = None
) -> dict[str, Any]:
    """Create detached presentation data from relational follow rows only."""

    rows = [
        dict(row) for row in projection.get("edges") or () if isinstance(row, Mapping)
    ]
    if relation_prefix:
        rows = [
            row
            for row in rows
            if _text(row.get("relation_kind")).startswith(relation_prefix)
        ]
    nodes = [
        dict(row) for row in projection.get("nodes") or () if isinstance(row, Mapping)
    ]
    return {
        "projection_ref": _text(projection.get("projection_ref")),
        "authority": DERIVED_ONLY_AUTHORITY,
        "nodes": nodes,
        "edges": rows,
        "summary": {"node_count": len(nodes), "edge_count": len(rows)},
    }


__all__ = [
    "DERIVED_ONLY_AUTHORITY",
    "FOLLOW_PROJECTION_SCHEMA_VERSION",
    "FollowEdge",
    "FollowNode",
    "build_follow_projection",
    "project_follow_view",
]
