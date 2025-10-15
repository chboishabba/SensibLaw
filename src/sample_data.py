from __future__ import annotations

from datetime import date
from typing import List, Optional

from graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
)
from models.provision import Provision

# Sample in-memory data used by both the API and CLI. This keeps the
# implementation lightweight while still exercising the graph and
# provision models.

GRAPH = LegalGraph()

# Documents
GRAPH.add_node(
    GraphNode(type=NodeType.DOCUMENT, identifier="doc1", metadata={"title": "Doc 1"})
)
GRAPH.add_node(
    GraphNode(type=NodeType.DOCUMENT, identifier="doc2", metadata={"title": "Doc 2"})
)

# Provisions are also represented as graph nodes for reference edges
GRAPH.add_node(
    GraphNode(
        type=NodeType.PROVISION,
        identifier="prov1",
        metadata={"text": "Provision 1"},
    )
)

# Edges between documents and provisions
GRAPH.add_edge(
    GraphEdge(type=EdgeType.CITES, source="doc1", target="doc2", weight=1.0)
)
GRAPH.add_edge(
    GraphEdge(type=EdgeType.REFERENCES, source="doc1", target="prov1", weight=1.0)
)

DOCUMENTS = {
    "doc1": [Provision("Provision 1", identifier="prov1")],
    "doc2": [Provision("Provision 2", identifier="prov2")],
}


def _node_to_dict(node: GraphNode) -> dict:
    return {
        "type": node.type.value,
        "identifier": node.identifier,
        "metadata": node.metadata,
        "date": node.date.isoformat() if node.date else None,
    }


def _edge_to_dict(edge: GraphEdge) -> dict:
    return {
        "type": edge.type.value,
        "source": edge.source,
        "target": edge.target,
        "identifier": edge.identifier,
        "metadata": edge.metadata,
        "date": edge.date.isoformat() if edge.date else None,
        "weight": edge.weight,
    }


def build_subgraph(nodes: Optional[List[str]], limit: int, offset: int) -> dict:
    """Return a subgraph containing the requested nodes and connecting edges."""

    node_ids = set(nodes) if nodes else set(GRAPH.nodes.keys())
    selected_nodes = [
        _node_to_dict(GRAPH.nodes[n]) for n in node_ids if n in GRAPH.nodes
    ]
    edges = [
        e
        for e in GRAPH.edges
        if e.source in node_ids and e.target in node_ids
    ]
    paginated_edges = edges[offset : offset + limit]
    return {
        "nodes": selected_nodes,
        "edges": [_edge_to_dict(e) for e in paginated_edges],
    }


def treatments_for(doc: str, limit: int, offset: int) -> List[dict]:
    """Return edges involving the given document."""

    edges = [e for e in GRAPH.edges if e.source == doc or e.target == doc]
    paginated = edges[offset : offset + limit]
    return [_edge_to_dict(e) for e in paginated]


def get_provision(doc: str, identifier: str) -> Optional[dict]:
    provisions = DOCUMENTS.get(doc, [])
    for p in provisions:
        if p.identifier == identifier:
            return p.to_dict()
    return None


def subgraph_to_dot(data: dict) -> str:
    """Render a subgraph dictionary as a GraphViz DOT string."""

    lines = ["digraph G {"]
    for node in data["nodes"]:
        lines.append(f'    "{node["identifier"]}" [label="{node["identifier"]}"];')
    for edge in data["edges"]:
        lines.append(
            f'    "{edge["source"]}" -> "{edge["target"]}" [label="{edge["type"]}"];'
        )
    lines.append("}")
    return "\n".join(lines)


__all__ = [
    "GRAPH",
    "DOCUMENTS",
    "build_subgraph",
    "treatments_for",
    "get_provision",
    "subgraph_to_dot",
]
