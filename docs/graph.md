# Graph Module

The `graph` package provides simple data structures for building in-memory
networks of legal entities. Nodes and edges are represented using dataclasses
and typed with enumerations for clarity.

## Node and Edge Types

`NodeType` and `EdgeType` enumerate the supported entities and relationships.
These can be extended as the project grows.

## Creating Nodes and Edges

```python
from graph import (
    GraphNode,
    GraphEdge,
    LegalGraph,
    NodeType,
    EdgeType,
)
from datetime import date

# Create a new graph
lg = LegalGraph()

# Add two document nodes
case = GraphNode(
    type=NodeType.DOCUMENT,
    identifier="case-1",
    metadata={"title": "Example Case"},
    date=date(2020, 1, 1),
)
statute = GraphNode(type=NodeType.DOCUMENT, identifier="statute-1")
lg.add_node(case)
lg.add_node(statute)

# Connect the nodes with a citation edge
edge = GraphEdge(
    type=EdgeType.CITES,
    source=case.identifier,
    target=statute.identifier,
    weight=1.0,
)
lg.add_edge(edge)
```

The `LegalGraph` manager provides `add_node` and `add_edge` helpers along with
query methods like `get_node` and `find_edges` for exploring the network.
