# Graph Module

The `graph` package provides simple data structures for building in-memory
networks of legal entities. Nodes and edges are represented using dataclasses
and typed with enumerations for clarity.

## Node and Edge Types

`NodeType` and `EdgeType` enumerate the supported entities and relationships.
`NodeType` now includes a `CASE` variant for judicial decisions, while
`EdgeType` offers additional relationships such as `FOLLOWS`, `APPLIES`,
`CONSIDERS`, `DISTINGUISHES` and `OVERRULES`. These can be extended as the
project grows.

## Creating Nodes and Edges

```python
from graph import (
    CaseNode,
    GraphNode,
    GraphEdge,
    LegalGraph,
    NodeType,
    EdgeType,
)
from datetime import date

# Create a new graph
lg = LegalGraph()

# Add a case and a statute
case = CaseNode(
    identifier="case-1",
    metadata={"title": "Example Case"},
    date=date(2020, 1, 1),
    court_rank=2,
    panel_size=3,
)
statute = GraphNode(type=NodeType.DOCUMENT, identifier="statute-1")
lg.add_node(case)
lg.add_node(statute)

# Connect the nodes with a citation edge
edge = GraphEdge(
    type=EdgeType.APPLIES,
    source=case.identifier,
    target=statute.identifier,
    weight=1.0,
)
lg.add_edge(edge)
```

The `LegalGraph` manager provides `add_node` and `add_edge` helpers along with
query methods like `get_node` and `find_edges` for exploring the network.

## Extrinsic material and weights

Parliamentary contributions or other extrinsic materials can be modelled with
an `ExtrinsicNode`. Each node records the speaker's role (e.g. *Minister*) and
the legislative stage (e.g. *2nd reading*). The ingestion helper computes a
weight that reflects the relative influence of the contribution.

```python
from graph import LegalGraph, NodeType, GraphNode, ingest_extrinsic

graph = LegalGraph()
bill = GraphNode(type=NodeType.DOCUMENT, identifier="bill-1")
graph.add_node(bill)

# Minister during the second reading carries more weight than a backbencher
ingest_extrinsic(
    graph,
    identifier="speech-1",
    role="Minister",
    stage="2nd reading",
    target=bill.identifier,
)

heavy_edges = graph.find_edges(min_weight=2.0)
```

Filtering by `min_weight` allows consumers to focus on more authoritative
extrinsic statements when interpreting legislation.
