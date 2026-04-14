from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.ingestion.media_adapter import ParsedEnvelope, SegmentKind


@dataclass(frozen=True)
class SegmentGraphNode:
    node_id: str
    node_kind: str
    segment_id: str | None = None
    role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "segment_id": self.segment_id,
            "role": self.role,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SegmentGraphEdge:
    edge_kind: str
    source_id: str
    target_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_kind": self.edge_kind,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }


@dataclass(frozen=True)
class SegmentGraph:
    graph_id: str
    nodes: tuple[SegmentGraphNode, ...]
    edges: tuple[SegmentGraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def _segment_role(segment_kind: str) -> str:
    if segment_kind == SegmentKind.HEADING.value:
        return "heading"
    if segment_kind == SegmentKind.LIST.value:
        return "list_item"
    if segment_kind == SegmentKind.QUOTE.value:
        return "quote_block"
    if segment_kind == SegmentKind.TABLE.value:
        return "table_block"
    if segment_kind == SegmentKind.CODE_BLOCK.value:
        return "code_block"
    return "body"


def build_segment_graph(parsed_envelope: ParsedEnvelope) -> SegmentGraph:
    root_id = f"{parsed_envelope.envelope_id}:root"
    nodes: list[SegmentGraphNode] = [
        SegmentGraphNode(
            node_id=root_id,
            node_kind="segment_node",
            role="root",
            metadata={"text_id": parsed_envelope.canonical_text.text_id},
        )
    ]
    edges: list[SegmentGraphEdge] = []
    segment_nodes: list[SegmentGraphNode] = []

    for segment in parsed_envelope.parsed_segments:
        node = SegmentGraphNode(
            node_id=f"{parsed_envelope.envelope_id}:segment:{segment.order_index}",
            node_kind="segment_node",
            segment_id=segment.segment_id,
            role=_segment_role(segment.segment_kind),
            metadata={
                "segment_kind": segment.segment_kind,
                "order_index": segment.order_index,
            },
        )
        nodes.append(node)
        segment_nodes.append(node)
        edges.append(
            SegmentGraphEdge(
                edge_kind="contains",
                source_id=root_id,
                target_id=node.node_id,
            )
        )

    for previous, current in zip(segment_nodes, segment_nodes[1:]):
        edges.append(
            SegmentGraphEdge(
                edge_kind="follows",
                source_id=previous.node_id,
                target_id=current.node_id,
            )
        )

    for index, node in enumerate(segment_nodes):
        if node.role != "heading":
            continue
        for candidate in segment_nodes[index + 1 :]:
            if candidate.role == "heading":
                break
            edges.append(
                SegmentGraphEdge(
                    edge_kind="heads",
                    source_id=node.node_id,
                    target_id=candidate.node_id,
                )
            )
            break

    return SegmentGraph(
        graph_id=f"{parsed_envelope.envelope_id}:segment_graph",
        nodes=tuple(nodes),
        edges=tuple(edges),
    )


__all__ = [
    "SegmentGraph",
    "SegmentGraphEdge",
    "SegmentGraphNode",
    "build_segment_graph",
]
