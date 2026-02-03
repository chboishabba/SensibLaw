"""Deterministic structural logic tree builder.

The logic tree is a purely structural, deterministic intermediate
representation. It maps a token stream to an acyclic tree with stable IDs,
round-trip-safe persistence, and deterministic DOT export.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from src.pipeline.tokens import Token as PipelineToken, TokenStream

LOGIC_TREE_VERSION = "logic-tree-v1"
_OFFSETS_DISABLED = os.getenv("LOGIC_TREE_DISABLE_OFFSETS", "").lower() in {"1", "true", "yes", "on"}


class NodeType(str, Enum):
    ROOT = "ROOT"
    CLAUSE = "CLAUSE"
    CONDITION = "CONDITION"
    ACTION = "ACTION"
    MODAL = "MODAL"
    EXCEPTION = "EXCEPTION"
    REFERENCE = "REFERENCE"
    TOKEN = "TOKEN"


class EdgeType(str, Enum):
    SEQUENCE = "SEQUENCE"
    DEPENDS_ON = "DEPENDS_ON"
    QUALIFIES = "QUALIFIES"
    EXCEPTS = "EXCEPTS"


EDGE_ORDER = {
    EdgeType.SEQUENCE: 0,
    EdgeType.DEPENDS_ON: 1,
    EdgeType.QUALIFIES: 2,
    EdgeType.EXCEPTS: 3,
}

NODE_COLOR = {
    NodeType.ROOT: "#111827",
    NodeType.CLAUSE: "#2563eb",
    NodeType.CONDITION: "#059669",
    NodeType.ACTION: "#0ea5e9",
    NodeType.MODAL: "#a855f7",
    NodeType.EXCEPTION: "#dc2626",
    NodeType.REFERENCE: "#f59e0b",
    NodeType.TOKEN: "#6b7280",
}

EXCEPTION_TRIGGERS = {"unless", "except", "excluding", "save"}
CONDITION_TRIGGERS = {"if", "when", "where", "provided", "subject", "until", "upon"}
MODAL_TRIGGERS = {"must", "shall", "may", "should", "will", "would", "can", "cannot"}


@dataclass(frozen=True)
class Node:
    """Node within the logic tree."""

    id: str
    node_type: NodeType
    span: Tuple[int, int] | None
    text: str | None
    source_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "span": list(self.span) if self.span is not None else None,
            "text": self.text,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Node":
        span_value = data.get("span")
        span_tuple: Tuple[int, int] | None
        if isinstance(span_value, (list, tuple)):
            span_tuple = (int(span_value[0]), int(span_value[1]))
        else:
            span_tuple = None

        return cls(
            id=str(data["id"]),
            node_type=NodeType(str(data["node_type"])),
            span=span_tuple,
            text=data.get("text"),
            source_id=str(data.get("source_id", "unknown")),
        )


@dataclass(frozen=True)
class Edge:
    """Directed relationship between two nodes."""

    parent_id: str
    child_id: str
    edge_type: EdgeType

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "edge_type": self.edge_type.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Edge":
        return cls(
            parent_id=str(data["parent_id"]),
            child_id=str(data["child_id"]),
            edge_type=EdgeType(str(data["edge_type"])),
        )


class LogicTree:
    """Structured representation of a deterministic logic tree.

    Ordering invariants:
    - ROOT is emitted first for readability but does not influence child ordering.
    - Children are ordered by child span start, then edge-type priority, then ID.
    - Traversal order follows edge ordering; node list order is incidental.
    """

    def __init__(self, *, version: str, root_id: str, nodes: List[Node], edges: List[Edge]) -> None:
        self.version = version
        self.root_id = root_id
        self.nodes = nodes
        self.edges = edges
        self._node_index: Dict[str, Node] = {node.id: node for node in nodes}
        self._span_lookup: Dict[str, int] = {
            node.id: node.span[0] if node.span is not None else 99_999_999 for node in nodes
        }
        self._children: Dict[str, List[Edge]] = _build_children_map(edges, self._span_lookup)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "root_id": self.root_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LogicTree":
        nodes = [Node.from_dict(node) for node in data.get("nodes", [])]
        edges = [Edge.from_dict(edge) for edge in data.get("edges", [])]
        return cls(
            version=str(data.get("version", LOGIC_TREE_VERSION)),
            root_id=str(data.get("root_id", "n0")),
            nodes=nodes,
            edges=edges,
        )

    def to_dot(self, *, include_tokens: bool = False, include_sequence_edges: bool = False) -> str:
        """Return a deterministic Graphviz DOT representation of the tree.

        - By default, hides TOKEN nodes to emphasise structure.
        - SEQUENCE edges are rendered with constraint=false to avoid flattening layout.
        """

        include_node = (
            lambda n: include_tokens or n.node_type is not NodeType.TOKEN
        )

        lines = ["digraph LogicTree {", "  rankdir=TB;"]
        for node in sorted(self.nodes, key=_node_sort_key):
            if not include_node(node):
                continue
            label = node.node_type.value
            if node.text:
                label = f"{label}: {node.text}"
            color = NODE_COLOR.get(node.node_type)
            attr_parts = [f'label="{label}"']
            if color:
                attr_parts.append('style="filled"')
                attr_parts.append(f'fillcolor="{color}"')
            attrs = " ".join(attr_parts)
            lines.append(f'  "{node.id}" [{attrs}];')

        for edge in sorted(self.edges, key=lambda e: _edge_sort_key(e, self._span_lookup)):
            parent = self._node_index.get(edge.parent_id)
            child = self._node_index.get(edge.child_id)
            if parent is None or child is None:
                continue
            if not include_node(parent) or not include_node(child):
                continue

            attrs: list[str] = [f'label="{edge.edge_type.value}"']
            if edge.edge_type is EdgeType.SEQUENCE:
                if not include_sequence_edges:
                    attrs.append('constraint=false')
                    attrs.append('style="dotted"')
                    attrs.append('color="#9ca3af"')
            lines.append(f'  "{edge.parent_id}" -> "{edge.child_id}" [{\" \".join(attrs)}];')

        lines.append("}")
        return "\n".join(lines)

    def children_of(self, node_id: str) -> List[Edge]:
        return self._children.get(node_id, [])

    def node(self, node_id: str) -> Node:
        return self._node_index[node_id]


def _build_children_map(edges: Iterable[Edge], span_lookup: Mapping[str, int]) -> Dict[str, List[Edge]]:
    children: MutableMapping[str, List[Edge]] = {}
    for edge in edges:
        children.setdefault(edge.parent_id, []).append(edge)
    for edge_list in children.values():
        edge_list.sort(key=lambda e: _edge_sort_key(e, span_lookup))
    return dict(children)


def _id_sort_value(identifier: str) -> Tuple[int, str]:
    numeric_part = identifier[1:] if identifier.startswith("n") else identifier
    try:
        return (int(numeric_part), identifier)
    except ValueError:
        return (99_999_999, identifier)


def _node_sort_key(node: Node) -> Tuple[int, int, str]:
    start = node.span[0] if node.span is not None else -1
    numeric_id, identifier = _id_sort_value(node.id)
    return (start, numeric_id, identifier)


def _edge_sort_key(edge: Edge, span_lookup: Mapping[str, int]) -> Tuple[int, int, int, str]:
    order = EDGE_ORDER.get(edge.edge_type, 99)
    start = span_lookup.get(edge.child_id, 99_999_999)
    numeric_child, identifier = _id_sort_value(edge.child_id)
    return (start, order, numeric_child, identifier)


def prepare_logic_tree_schema(connection: sqlite3.Connection) -> None:
    """Create minimal tables for projecting logic trees into SQLite."""

    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            version_id TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logic_nodes (
            node_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            span_i INTEGER,
            span_j INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logic_edges (
            doc_id TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            child_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            ord INTEGER NOT NULL,
            PRIMARY KEY (doc_id, parent_id, ord)
        )
        """
    )
    connection.commit()


def project_logic_tree_to_sqlite(tree: LogicTree, connection: sqlite3.Connection, *, doc_id: str | None = None) -> None:
    """Project a logic tree into SQLite, preserving child order via `ord` per parent.

    SQLite remains a projection only; JSON is canonical. Existing rows for the
    document are replaced to keep projections idempotent.
    """

    inferred_doc_id = doc_id or tree.nodes[0].source_id if tree.nodes else "unknown"
    cursor = connection.cursor()
    prepare_logic_tree_schema(connection)

    cursor.execute("DELETE FROM logic_edges WHERE doc_id = ?", (inferred_doc_id,))
    cursor.execute("DELETE FROM logic_nodes WHERE doc_id = ?", (inferred_doc_id,))
    cursor.execute(
        "INSERT OR REPLACE INTO documents (doc_id, version_id) VALUES (?, ?)",
        (inferred_doc_id, tree.version),
    )

    cursor.executemany(
        "INSERT INTO logic_nodes (node_id, doc_id, node_type, span_i, span_j) VALUES (?, ?, ?, ?, ?)",
        [
            (node.id, inferred_doc_id, node.node_type.value, node.span[0] if node.span else None, node.span[1] if node.span else None)
            for node in tree.nodes
        ],
    )

    ord_rows: List[Tuple[str, str, str, str, int]] = []
    for parent_id in {edge.parent_id for edge in tree.edges}:
        for ord_index, edge in enumerate(tree.children_of(parent_id)):
            ord_rows.append(
                (
                    inferred_doc_id,
                    edge.parent_id,
                    edge.child_id,
                    edge.edge_type.value,
                    ord_index,
                )
            )
    cursor.executemany(
        "INSERT INTO logic_edges (doc_id, parent_id, child_id, edge_type, ord) VALUES (?, ?, ?, ?, ?)",
        ord_rows,
    )

    connection.commit()


def rehydrate_logic_tree_from_sqlite(connection: sqlite3.Connection, *, doc_id: str) -> LogicTree:
    """Rehydrate a logic tree from its SQLite projection.

    Restores IDs, node types, spans, and parent→child ordering via `ord`.
    SQLite remains a projection-only index; no text or semantic reconstruction occurs here.
    """

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT node_id, node_type, span_i, span_j FROM logic_nodes WHERE doc_id = ?
        """,
        (doc_id,),
    )
    node_rows = cursor.fetchall()
    if not node_rows:
        raise ValueError(f"No logic_nodes found for doc_id={doc_id}")

    nodes = []
    for node_id, node_type, span_i, span_j in node_rows:
        span = (int(span_i), int(span_j)) if span_i is not None and span_j is not None else None
        nodes.append(
            Node(
                id=str(node_id),
                node_type=NodeType(str(node_type)),
                span=span,
                text=None,
                source_id=doc_id,
            )
        )

    cursor.execute(
        """
        SELECT parent_id, child_id, edge_type FROM logic_edges
        WHERE doc_id = ?
        ORDER BY parent_id, ord
        """,
        (doc_id,),
    )
    edges = [
        Edge(parent_id=str(parent_id), child_id=str(child_id), edge_type=EdgeType(str(edge_type)))
        for parent_id, child_id, edge_type in cursor.fetchall()
    ]

    root_nodes = [node for node in nodes if node.node_type is NodeType.ROOT]
    if len(root_nodes) != 1:
        raise ValueError(f"Expected exactly one ROOT for doc_id={doc_id}, found {len(root_nodes)}")

    return LogicTree(version=LOGIC_TREE_VERSION, root_id=root_nodes[0].id, nodes=nodes, edges=edges)


def prepare_fts_schema(connection: sqlite3.Connection) -> None:
    """Create an FTS5 table for document text (stored once per doc)."""

    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            doc_id UNINDEXED,
            raw_text
        )
        """
    )
    connection.commit()


def index_tokens_for_fts(connection: sqlite3.Connection, *, doc_id: str, tokens: Sequence[Any]) -> None:
    """Index document text for FTS using the token texts joined once.

    This avoids duplicating node text; raw_text is the canonical token string for search.
    """

    prepare_fts_schema(connection)
    raw_text = " ".join(_token_text(token) for token in tokens)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    cursor.execute("INSERT INTO docs_fts (doc_id, raw_text) VALUES (?, ?)", (doc_id, raw_text))
    connection.commit()


def _parse_fts_offsets(offsets_value: str) -> List[Tuple[int, int]]:
    """Parse SQLite FTS offsets() output into token span tuples (start, end)."""

    parts = [int(part) for part in offsets_value.split()]
    spans: List[Tuple[int, int]] = []
    for idx in range(0, len(parts), 4):
        # columns: column, term, token_offset, token_length
        token_offset = parts[idx + 2]
        token_length = parts[idx + 3]
        spans.append((token_offset, token_offset + token_length))
    return spans


def search_fts_over_logic_tree(
    connection: sqlite3.Connection, query: str, *, limit: int = 20, use_offsets: bool = True
) -> List[Dict[str, Any]]:
    """Search FTS index and resolve hits to logic tree node IDs via span overlap.

    Returns a list of results with doc_id, node_ids, spans, and snippets reconstructed
    from the token string stored in FTS. No node text is stored or duplicated.
    """

    cursor = connection.cursor()
    rows: List[Tuple[Any, ...]] = []
    with_offsets = False
    effective_use_offsets = use_offsets and not _OFFSETS_DISABLED
    if effective_use_offsets:
        try:
            cursor.execute(
                "SELECT doc_id, raw_text, offsets(docs_fts) FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
                (query, limit),
            )
            rows = cursor.fetchall()
            with_offsets = True
        except sqlite3.OperationalError:
            rows = []
            with_offsets = False
    if not rows:
        cursor.execute(
            "SELECT doc_id, raw_text FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?",
            (query, limit),
        )
        rows = cursor.fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        doc_id = row[0]
        raw_text = row[1]
        if with_offsets:
            spans = _parse_fts_offsets(str(row[2]))
        else:
            tokens = raw_text.split()
            query_tokens = query.split()
            spans = []
            k = len(query_tokens)
            for idx in range(len(tokens) - k + 1):
                if [t.lower() for t in tokens[idx : idx + k]] == [t.lower() for t in query_tokens]:
                    spans.append((idx, idx + k))
        tokens = raw_text.split()
        snippets = [" ".join(tokens[start:end]) for start, end in spans if 0 <= start < len(tokens)]
        node_ids: set[str] = set()
        for start, end in spans:
            for (node_id,) in connection.execute(
                """
                SELECT node_id
                FROM logic_nodes
                WHERE doc_id = ?
                  AND span_i IS NOT NULL
                  AND span_j IS NOT NULL
                  AND span_i < ?
                  AND span_j > ?
                """,
                (doc_id, end, start),
            ):
                node_ids.add(str(node_id))
        results.append(
            {
                "doc_id": doc_id,
                "node_ids": sorted(node_ids),
                "spans": spans,
                "snippets": snippets,
            }
        )
    return results


def _token_text(token: Any) -> str:
    return getattr(token, "text", None) or str(token)


def _token_lemma(token: Any) -> str:
    return getattr(token, "lemma", None) or getattr(token, "lemma_", None) or _token_text(token)


def _token_pos(token: Any) -> str:
    return getattr(token, "pos", None) or getattr(token, "pos_", None) or ""


def _token_dep(token: Any) -> str:
    return getattr(token, "dep", None) or getattr(token, "dep_", None) or ""


def _token_ent_type(token: Any) -> str:
    return getattr(token, "ent_type", None) or getattr(token, "ent_type_", None) or ""


def _is_clause_boundary(token: Any) -> bool:
    text = _token_text(token)
    return text.endswith(".") or text.endswith(";") or text in {".", ";"}


def _classify_token(token: Any) -> NodeType:
    lemma = _token_lemma(token).lower()
    text = _token_text(token).lower()
    pos = _token_pos(token).upper()
    dep = _token_dep(token).upper()
    ent_type = _token_ent_type(token)

    if lemma in EXCEPTION_TRIGGERS or text in EXCEPTION_TRIGGERS:
        return NodeType.EXCEPTION
    if lemma in CONDITION_TRIGGERS or text in CONDITION_TRIGGERS:
        return NodeType.CONDITION
    if lemma in MODAL_TRIGGERS or text in MODAL_TRIGGERS or pos == "AUX":
        return NodeType.MODAL
    if pos == "VERB" or dep == "ROOT":
        return NodeType.ACTION
    if ent_type:
        return NodeType.REFERENCE
    return NodeType.TOKEN


def _edge_type_for_child(node_type: NodeType) -> EdgeType:
    if node_type is NodeType.EXCEPTION:
        return EdgeType.EXCEPTS
    if node_type is NodeType.CONDITION:
        return EdgeType.DEPENDS_ON
    if node_type is NodeType.MODAL:
        return EdgeType.QUALIFIES
    return EdgeType.SEQUENCE


def _clause_spans(tokens: Sequence[Any]) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    if not tokens:
        return spans

    start = 0
    for idx, token in enumerate(tokens):
        if _is_clause_boundary(token):
            spans.append((start, idx))
            start = idx + 1
    if start < len(tokens):
        spans.append((start, len(tokens) - 1))
    return spans


def build(tokens: Sequence[PipelineToken] | TokenStream, *, source_id: str = "unknown") -> LogicTree:
    """Build a deterministic logic tree from a token sequence."""

    root_node = Node(id="n0", node_type=NodeType.ROOT, span=None, text=None, source_id=source_id)
    if not tokens:
        return LogicTree(version=LOGIC_TREE_VERSION, root_id=root_node.id, nodes=[root_node], edges=[])

    nodes: List[Node] = [root_node]
    edges: List[Edge] = []
    next_id = 1

    spans = _clause_spans(tokens)
    for clause_start, clause_end in spans:
        clause_id = f"n{next_id}"
        next_id += 1
        clause_tokens = tokens[clause_start : clause_end + 1]
        clause_text = " ".join(_token_text(token) for token in clause_tokens)
        clause_node = Node(
            id=clause_id,
            node_type=NodeType.CLAUSE,
            span=(clause_start, clause_end + 1),
            text=clause_text,
            source_id=source_id,
        )
        nodes.append(clause_node)
        edges.append(Edge(parent_id=root_node.id, child_id=clause_id, edge_type=EdgeType.SEQUENCE))

        for idx in range(clause_start, clause_end + 1):
            token = tokens[idx]
            node_type = _classify_token(token)
            token_node = Node(
                id=f"n{next_id}",
                node_type=node_type,
                span=(idx, idx + 1),
                text=_token_text(token),
                source_id=source_id,
            )
            next_id += 1
            nodes.append(token_node)
            edges.append(
                Edge(parent_id=clause_id, child_id=token_node.id, edge_type=_edge_type_for_child(node_type))
            )

    return LogicTree(version=LOGIC_TREE_VERSION, root_id=root_node.id, nodes=nodes, edges=edges)


def walk_preorder(tree: LogicTree) -> Iterable[Node]:
    """Yield nodes in preorder (parent before children)."""

    def _walk(node_id: str) -> Iterable[Node]:
        yield tree.node(node_id)
        for edge in tree.children_of(node_id):
            yield from _walk(edge.child_id)

    return _walk(tree.root_id)


def walk_postorder(tree: LogicTree) -> Iterable[Node]:
    """Yield nodes in postorder (children before parent)."""

    def _walk(node_id: str) -> Iterable[Node]:
        for edge in tree.children_of(node_id):
            yield from _walk(edge.child_id)
        yield tree.node(node_id)

    return _walk(tree.root_id)


def walk_root_to_leaves(tree: LogicTree) -> Iterable[List[Node]]:
    """Yield root-to-leaf paths as lists of nodes."""

    def _walk(node_id: str, path: List[Node]) -> Iterable[List[Node]]:
        node = tree.node(node_id)
        children = tree.children_of(node_id)
        if not children:
            yield path + [node]
            return
        for edge in children:
            yield from _walk(edge.child_id, path + [node])

    return _walk(tree.root_id, [])


__all__ = [
    "Edge",
    "EdgeType",
    "LogicTree",
    "LOGIC_TREE_VERSION",
    "Node",
    "NodeType",
    "build",
    "prepare_logic_tree_schema",
    "project_logic_tree_to_sqlite",
    "rehydrate_logic_tree_from_sqlite",
    "prepare_fts_schema",
    "index_tokens_for_fts",
    "search_fts_over_logic_tree",
    "walk_postorder",
    "walk_preorder",
    "walk_root_to_leaves",
]
