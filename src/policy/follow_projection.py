"""Generic, derived-only follow projection carriers.

Follow projections are relational materialised views over canonical PNF and Domain IR
state.  They are challengeable, add no truth, and carry no execution authority.
Lane wrappers may choose profiles and labels but may not create a second semantic
identity or deserialize presentation JSON as input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256

FOLLOW_PROJECTION_SCHEMA_VERSION = "sl.pnf.follow_projection.v0_1"
FOLLOW_PROJECTION_AUTHORITY = "derived_only"
_ADMISSIBILITY_STATES = {
    "admitted",
    "rejected",
    "blocked",
    "undetermined",
    "inapplicable",
}


def _refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class FollowNode:
    node_ref: str
    node_kind: str
    label: str
    ordinal: int
    factor_ref: str | None = None
    factor_revision_ref: str | None = None
    assessment_ref: str | None = None
    admissibility_receipt_ref: str | None = None
    resolution_ref: str | None = None
    domain_ir_ref: str | None = None
    source_revision_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.node_ref or not self.node_kind or not self.label:
            raise ValueError("follow nodes require ref, kind, and label")
        if self.ordinal < 0:
            raise ValueError("follow node ordinal must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "derived_only": True}


@dataclass(frozen=True)
class FollowEdge:
    edge_ref: str
    source_node_ref: str
    target_node_ref: str
    relation_kind: str
    admissibility_state: str
    ordinal: int
    evidence_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    admissibility_ground_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.edge_ref, self.source_node_ref, self.target_node_ref, self.relation_kind)):
            raise ValueError("follow edges require identity and endpoints")
        if self.admissibility_state not in _ADMISSIBILITY_STATES:
            raise ValueError("unsupported follow-edge admissibility state")
        if self.ordinal < 0:
            raise ValueError("follow edge ordinal must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "evidence_refs": list(_refs(self.evidence_refs)),
            "provenance_refs": list(_refs(self.provenance_refs)),
            "admissibility_ground_refs": list(_refs(self.admissibility_ground_refs)),
            "derived_only": True,
            "challengeable": True,
            "promotes_truth": False,
            "execution_authority": False,
        }


@dataclass(frozen=True)
class FollowProjection:
    document_ref: str
    profile_ref: str
    scope_ref: str
    projection_kind: str
    nodes: tuple[FollowNode, ...]
    edges: tuple[FollowEdge, ...]
    source_graph_ref: str | None = None
    source_resolution_ref: str | None = None

    def __post_init__(self) -> None:
        if not all((self.document_ref, self.profile_ref, self.scope_ref, self.projection_kind)):
            raise ValueError("follow projection requires document, profile, scope, and kind")
        node_refs = {row.node_ref for row in self.nodes}
        if len(node_refs) != len(self.nodes):
            raise ValueError("follow node refs must be unique")
        for edge in self.edges:
            if edge.source_node_ref not in node_refs or edge.target_node_ref not in node_refs:
                raise ValueError("follow edge endpoint is not present in projection")

    @property
    def projection_ref(self) -> str:
        return "follow-projection:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": FOLLOW_PROJECTION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "profile_ref": self.profile_ref,
            "scope_ref": self.scope_ref,
            "projection_kind": self.projection_kind,
            "source_graph_ref": self.source_graph_ref,
            "source_resolution_ref": self.source_resolution_ref,
            "nodes": [row.to_dict() for row in sorted(self.nodes, key=lambda value: (value.ordinal, value.node_ref))],
            "edges": [row.to_dict() for row in sorted(self.edges, key=lambda value: (value.ordinal, value.edge_ref))],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "projection_ref": self.projection_ref,
            "authority": FOLLOW_PROJECTION_AUTHORITY,
            "derived_only": True,
            "challengeable": True,
            "promotes_truth": False,
            "execution_authority": False,
        }


def build_follow_projection(
    *,
    document_ref: str,
    profile_ref: str,
    scope_ref: str,
    projection_kind: str,
    node_rows: Sequence[Mapping[str, Any]],
    edge_rows: Sequence[Mapping[str, Any]],
    source_graph_ref: str | None = None,
    source_resolution_ref: str | None = None,
) -> FollowProjection:
    nodes = tuple(
        FollowNode(
            node_ref=str(row["node_ref"]),
            node_kind=str(row["node_kind"]),
            label=str(row["label"]),
            ordinal=int(row.get("ordinal", index)),
            factor_ref=str(row["factor_ref"]) if row.get("factor_ref") else None,
            factor_revision_ref=str(row["factor_revision_ref"]) if row.get("factor_revision_ref") else None,
            assessment_ref=str(row["assessment_ref"]) if row.get("assessment_ref") else None,
            admissibility_receipt_ref=str(row["admissibility_receipt_ref"]) if row.get("admissibility_receipt_ref") else None,
            resolution_ref=str(row["resolution_ref"]) if row.get("resolution_ref") else None,
            domain_ir_ref=str(row["domain_ir_ref"]) if row.get("domain_ir_ref") else None,
            source_revision_ref=str(row["source_revision_ref"]) if row.get("source_revision_ref") else None,
        )
        for index, row in enumerate(node_rows)
    )
    edges = tuple(
        FollowEdge(
            edge_ref=str(row["edge_ref"]),
            source_node_ref=str(row["source_node_ref"]),
            target_node_ref=str(row["target_node_ref"]),
            relation_kind=str(row["relation_kind"]),
            admissibility_state=str(row.get("admissibility_state") or "undetermined"),
            ordinal=int(row.get("ordinal", index)),
            evidence_refs=_refs(row.get("evidence_refs") or ()),
            provenance_refs=_refs(row.get("provenance_refs") or ()),
            admissibility_ground_refs=_refs(row.get("admissibility_ground_refs") or ()),
        )
        for index, row in enumerate(edge_rows)
    )
    return FollowProjection(
        document_ref=document_ref,
        profile_ref=profile_ref,
        scope_ref=scope_ref,
        projection_kind=projection_kind,
        source_graph_ref=source_graph_ref,
        source_resolution_ref=source_resolution_ref,
        nodes=nodes,
        edges=edges,
    )


__all__ = [
    "FOLLOW_PROJECTION_AUTHORITY",
    "FOLLOW_PROJECTION_SCHEMA_VERSION",
    "FollowEdge",
    "FollowNode",
    "FollowProjection",
    "build_follow_projection",
]
