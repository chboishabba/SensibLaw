"""Graph ingestion utilities for legal documents.

This module provides a very small in-memory graph representation along with
helpers to populate the graph from :class:`~src.models.document.Document`
instances.  The graph is intentionally lightweight – it only tracks nodes and
edges using Python data structures so that it can be easily used in tests
without any external dependencies.

Nodes are identified by a unique ``id`` and may carry arbitrary attributes.
Edges capture relationships between nodes and are labelled with a ``type``
string.  The ingestion helpers focus on creating nodes for documents,
provisions contained within those documents, and any cited authorities.  Two
edge types are currently emitted:

``INTERPRETS``
    Connects a case document to a provision that it interprets.

``CITES``
    Connects a case document to another case that it cites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Iterable

from ..models.document import Document


# ---------------------------------------------------------------------------
# Basic graph primitives
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """Representation of a graph node."""

    id: str
    label: str
    properties: Dict[str, object] = field(default_factory=dict)


@dataclass
class Edge:
    """Representation of a directed edge between two nodes."""

    source: str
    target: str
    type: str
    properties: Dict[str, object] = field(default_factory=dict)


class Graph:
    """A trivial in-memory property graph."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []

    # ------------------------------------------------------------------
    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    # ------------------------------------------------------------------
    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    # ------------------------------------------------------------------
    def ensure_node(self, node_id: str, label: str, **props: object) -> Node:
        """Get or create a node."""
        node = self.nodes.get(node_id)
        if node is None:
            node = Node(id=node_id, label=label, properties=dict(props))
            self.add_node(node)
        else:
            node.properties.update(props)
        return node


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _iter_cited_authorities(doc: Document) -> Iterable[str]:
    """Yield identifiers for authorities cited by ``doc``.

    ``Document`` currently has no dedicated field for citations, but tests may
    attach a ``cited_authorities`` attribute dynamically.  This helper yields
    any such identifiers if present.
    """

    cites = getattr(doc, "cited_authorities", [])
    for item in cites:
        if isinstance(item, Document):
            yield item.metadata.citation
        else:
            yield str(item)


def ingest_document(doc: Document, graph: Graph) -> None:
    """Populate ``graph`` with nodes and edges derived from ``doc``.

    Parameters
    ----------
    doc:
        The :class:`~src.models.document.Document` to ingest.  A node will be
        created for the document itself, for each provision within the
        document, and for any cited authorities.  Edges will link the document
        to its provisions via ``INTERPRETS`` and to cited authorities via
        ``CITES``.
    graph:
        Graph instance to which nodes and edges will be added.
    """

    doc_id = doc.metadata.canonical_id or doc.metadata.citation
    graph.ensure_node(
        doc_id,
        label="Case",
        citation=doc.metadata.citation,
        jurisdiction=doc.metadata.jurisdiction,
    )

    # Provisions interpreted by this document
    for idx, provision in enumerate(doc.provisions):
        prov_id = provision.identifier or f"{doc_id}:p{idx}"
        graph.ensure_node(prov_id, label="Provision", text=provision.text)
        graph.add_edge(Edge(source=doc_id, target=prov_id, type="INTERPRETS"))

    # Cited authorities
    for authority in _iter_cited_authorities(doc):
        graph.ensure_node(authority, label="Case")
        graph.add_edge(Edge(source=doc_id, target=authority, type="CITES"))


__all__ = ["Graph", "Node", "Edge", "ingest_document"]
