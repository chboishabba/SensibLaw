# Graph Module

The `graph` package provides simple data structures for building in-memory
networks of legal entities. Nodes and edges are represented using dataclasses
and typed with enumerations for clarity.

## Node and Edge Types

`NodeType` and `EdgeType` enumerate the supported entities and relationships.
In addition to documents, provisions and people, the graph can now capture
case law and abstract concepts via ``CASE`` and ``CONCEPT`` node types.
Edges may represent legal treatments between cases such as ``FOLLOWS`` and
``DISTINGUISHES`` alongside general relationships like ``CITES`` and
``REFERENCES``. These enumerations can be extended as the project grows.

The TiRCorder subgraph introduces a set of domain-specific predicates that
describe how cases, concepts and provisions interact. The helper functions in
`src.graph.tircorder` validate node types before emitting the corresponding
edges; the expected source and target kinds are summarised below:

| Predicate      | Source node type | Target node type | Typical usage |
| -------------- | ---------------- | ---------------- | ------------- |
| `ARTICULATES`  | `CASE`           | `CONCEPT`        | A decision articulates the legal test or doctrinal concept. |
| `HAS_ELEMENT`  | `CONCEPT`        | `CONCEPT`        | A complex test has one or more constituent elements. |
| `APPLIES_TO`   | `CONCEPT`        | `PROVISION`      | A legal test is applied when construing a statutory provision. |
| `INTERPRETS`   | `CASE`           | `PROVISION`      | A decision interprets a particular statutory provision. |
| `CONTROLS`     | `CASE`           | `CASE`           | A precedent controls the outcome of a subsequent decision. |

Use the :class:`~src.graph.tircorder.TiRCorderBuilder` (or the module-level
wrapper functions) when creating TiRCorder edges so that callers do not need to
handcraft :class:`~src.graph.models.GraphEdge` instances.
In addition to documents, provisions and people, the graph can capture case law,
abstract concepts, and finer-grained TiRCorder structures such as judge
opinions, principles, elements of legal tests, specific statute sections, legal
issues, and orders. `EdgeType` covers legal treatments between cases such as
``FOLLOWS`` and ``DISTINGUISHES`` alongside general relationships like
``CITES`` and ``REFERENCES``. These enumerations can be extended as the project
grows.
 

## Creating Nodes and Edges

```python
from src.graph import (
    CaseNode,
    EdgeType,
    GraphEdge,
    GraphNode,
    IssueNode,
    JudgeOpinionNode,
    LegalGraph,
    NodeType,
    OrderNode,
    PrincipleNode,
    StatuteSectionNode,
    TestElementNode,
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

# TiRCorder builders can add richer analytical nodes succinctly
opinion = JudgeOpinionNode(identifier="case-1-majority")
principle = PrincipleNode(identifier="principle-duty-of-care")
test_element = TestElementNode(identifier="caparo-foreseeability")
section = StatuteSectionNode(identifier="statute-1-s12")
issue = IssueNode(identifier="issue-economic-loss")
order = OrderNode(identifier="order-dismiss-appeal")

for node in (opinion, principle, test_element, section, issue, order):
    lg.add_node(node)

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
from src.graph import LegalGraph, NodeType, GraphNode, ingest_extrinsic

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

## Relational graph embeddings

The :mod:`src.graph.rgcn` module adds an end-to-end pipeline for generating
relational graph convolutional network (R-GCN) embeddings. Install the optional
dependencies with ``pip install "sensiblaw[graph]"`` to pull in CPU builds of
PyTorch and DGL before working with the trainer.

```python
from pathlib import Path

from src.graph import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType
from src.graph.rgcn import RGCNConfig, RGCNTrainer, export_embeddings

graph = LegalGraph()
graph.add_node(GraphNode(type=NodeType.CASE, identifier="Case#Example"))
graph.add_node(GraphNode(type=NodeType.CASE, identifier="Case#FollowUp"))
graph.add_edge(
    GraphEdge(
        type=EdgeType.FOLLOWS,
        source="Case#FollowUp",
        target="Case#Example",
    )
)

config = RGCNConfig(
    epochs=50,
    hidden_dim=32,
    checkpoint_path=Path("artifacts/rgcn.pt"),
    metadata_key="rgcn_vector",
)

trainer = RGCNTrainer(graph, config)
result = trainer.train()
export_embeddings(result, Path("artifacts/embeddings.json"))
```

During training the trainer performs a validation split, samples negative edges
for a lightweight link-prediction objective, and persists the best-performing
checkpoint. By default embeddings are attached directly to each
``GraphNode.metadata`` entry under the ``metadata_key`` supplied in the config;
downstream clients (such as the Streamlit dashboard) can then read the vectors
without re-running the training loop.

## Streamlit embedding exploration

The Knowledge Graph tab in ``streamlit_app.py`` now understands embedding JSON
exports. Load a saved mapping or reuse vectors stored on nodes to:

* Visualise a two-dimensional projection of the embedding space using PCA.
* Request nearest-neighbour recommendations for a chosen node.

The tab reports whether embeddings are sourced from the in-memory graph or an
uploaded file, and surfaces the nearest neighbour table alongside the scatter
plot. This makes it easy to explore clusters of related authorities without
leaving the Streamlit console.
