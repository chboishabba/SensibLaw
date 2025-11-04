"""Helpers for constructing the TiRCorder-focused subgraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from .models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType


class MissingNodeError(ValueError):
    """Raised when a requested node identifier cannot be found in the graph."""


class NodeTypeMismatchError(ValueError):
    """Raised when a node's type does not match an expected :class:`NodeType`."""


def _require_node(graph: LegalGraph, identifier: str, expected: NodeType) -> GraphNode:
    node = graph.get_node(identifier)
    if node is None:
        raise MissingNodeError(f"Node '{identifier}' is not present in the graph.")
    if node.type != expected:
        raise NodeTypeMismatchError(
            "Expected node '%s' to be of type '%s' but found '%s'" %
            (identifier, expected.value, node.type.value)
        )
    return node


def _add_edge(
    graph: LegalGraph,
    *,
    edge_type: EdgeType,
    source: str,
    target: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    edge = GraphEdge(
        type=edge_type,
        source=source,
        target=target,
        metadata=dict(metadata or {}),
        weight=weight,
    )
    graph.add_edge(edge)
    return edge


@dataclass
class TiRCorderBuilder:
    """Convenience API for emitting TiRCorder predicates."""

    graph: LegalGraph

    def articulates(
        self,
        *,
        case_id: str,
        concept_id: str,
        metadata: Optional[Dict[str, object]] = None,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Link a case to the concept or test it articulates."""

        _require_node(self.graph, case_id, NodeType.CASE)
        _require_node(self.graph, concept_id, NodeType.CONCEPT)
        return _add_edge(
            self.graph,
            edge_type=EdgeType.ARTICULATES,
            source=case_id,
            target=concept_id,
            metadata=metadata,
            weight=weight,
        )

    def has_element(
        self,
        *,
        concept_id: str,
        element_id: str,
        metadata: Optional[Dict[str, object]] = None,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Connect a concept to one of its constituent elements."""

        _require_node(self.graph, concept_id, NodeType.CONCEPT)
        _require_node(self.graph, element_id, NodeType.CONCEPT)
        return _add_edge(
            self.graph,
            edge_type=EdgeType.HAS_ELEMENT,
            source=concept_id,
            target=element_id,
            metadata=metadata,
            weight=weight,
        )

    def applies_to(
        self,
        *,
        concept_id: str,
        provision_id: str,
        metadata: Optional[Dict[str, object]] = None,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Indicate that a concept is applied when interpreting a provision."""

        _require_node(self.graph, concept_id, NodeType.CONCEPT)
        _require_node(self.graph, provision_id, NodeType.PROVISION)
        return _add_edge(
            self.graph,
            edge_type=EdgeType.APPLIES_TO,
            source=concept_id,
            target=provision_id,
            metadata=metadata,
            weight=weight,
        )

    def interprets(
        self,
        *,
        case_id: str,
        provision_id: str,
        metadata: Optional[Dict[str, object]] = None,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Connect a case to the statutory provision it interprets."""

        _require_node(self.graph, case_id, NodeType.CASE)
        _require_node(self.graph, provision_id, NodeType.PROVISION)
        return _add_edge(
            self.graph,
            edge_type=EdgeType.INTERPRETS,
            source=case_id,
            target=provision_id,
            metadata=metadata,
            weight=weight,
        )

    def controls(
        self,
        *,
        leading_case_id: str,
        following_case_id: str,
        metadata: Optional[Dict[str, object]] = None,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Record that one case controls the outcome of another."""

        _require_node(self.graph, leading_case_id, NodeType.CASE)
        _require_node(self.graph, following_case_id, NodeType.CASE)
        return _add_edge(
            self.graph,
            edge_type=EdgeType.CONTROLS,
            source=leading_case_id,
            target=following_case_id,
            metadata=metadata,
            weight=weight,
        )


def build_tircorder_edges(
    graph: LegalGraph,
    *,
    articulates: Iterable[Dict[str, str]] = (),
    has_elements: Iterable[Dict[str, str]] = (),
    applies_to: Iterable[Dict[str, str]] = (),
    interprets: Iterable[Dict[str, str]] = (),
    controls: Iterable[Dict[str, str]] = (),
) -> None:
    """Bulk helper to emit TiRCorder predicates from simple mappings."""

    builder = TiRCorderBuilder(graph)
    for record in articulates:
        builder.articulates(
            case_id=record["case_id"],
            concept_id=record["concept_id"],
            metadata=record.get("metadata"),
            weight=record.get("weight", 1.0),
        )
    for record in has_elements:
        builder.has_element(
            concept_id=record["concept_id"],
            element_id=record["element_id"],
            metadata=record.get("metadata"),
            weight=record.get("weight", 1.0),
        )
    for record in applies_to:
        builder.applies_to(
            concept_id=record["concept_id"],
            provision_id=record["provision_id"],
            metadata=record.get("metadata"),
            weight=record.get("weight", 1.0),
        )
    for record in interprets:
        builder.interprets(
            case_id=record["case_id"],
            provision_id=record["provision_id"],
            metadata=record.get("metadata"),
            weight=record.get("weight", 1.0),
        )
    for record in controls:
        builder.controls(
            leading_case_id=record["leading_case_id"],
            following_case_id=record["following_case_id"],
            metadata=record.get("metadata"),
            weight=record.get("weight", 1.0),
        )


def articulates(
    graph: LegalGraph,
    *,
    case_id: str,
    concept_id: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    """Module-level convenience wrapper for :meth:`TiRCorderBuilder.articulates`."""

    return TiRCorderBuilder(graph).articulates(
        case_id=case_id,
        concept_id=concept_id,
        metadata=metadata,
        weight=weight,
    )


def has_element(
    graph: LegalGraph,
    *,
    concept_id: str,
    element_id: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    """Module-level convenience wrapper for :meth:`TiRCorderBuilder.has_element`."""

    return TiRCorderBuilder(graph).has_element(
        concept_id=concept_id,
        element_id=element_id,
        metadata=metadata,
        weight=weight,
    )


def applies_to(
    graph: LegalGraph,
    *,
    concept_id: str,
    provision_id: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    """Module-level convenience wrapper for :meth:`TiRCorderBuilder.applies_to`."""

    return TiRCorderBuilder(graph).applies_to(
        concept_id=concept_id,
        provision_id=provision_id,
        metadata=metadata,
        weight=weight,
    )


def interprets(
    graph: LegalGraph,
    *,
    case_id: str,
    provision_id: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    """Module-level convenience wrapper for :meth:`TiRCorderBuilder.interprets`."""

    return TiRCorderBuilder(graph).interprets(
        case_id=case_id,
        provision_id=provision_id,
        metadata=metadata,
        weight=weight,
    )


def controls(
    graph: LegalGraph,
    *,
    leading_case_id: str,
    following_case_id: str,
    metadata: Optional[Dict[str, object]] = None,
    weight: float = 1.0,
) -> GraphEdge:
    """Module-level convenience wrapper for :meth:`TiRCorderBuilder.controls`."""

    return TiRCorderBuilder(graph).controls(
        leading_case_id=leading_case_id,
        following_case_id=following_case_id,
        metadata=metadata,
        weight=weight,
    )


__all__ = [
    "MissingNodeError",
    "NodeTypeMismatchError",
    "TiRCorderBuilder",
    "build_tircorder_edges",
    "articulates",
    "has_element",
    "applies_to",
    "interprets",
    "controls",
]
