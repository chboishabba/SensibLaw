from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from concepts.cloud import build_cloud
from graph.models import GraphNode, LegalGraph, NodeType


class TextIndex:
    """Simple SQLite FTS5-backed search index for graph nodes.

    The index stores text for cases, provisions, extrinsic materials and story
    items. Each entry records a node identifier, its type and the associated
    text. Queries return typed results along with a minimal subgraph centred on
    the hit node.
    """

    def __init__(self, path: str | Path, graph: Optional[LegalGraph] = None) -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        # ``graph`` allows callers to associate additional relational
        # information with nodes so that minimal subgraphs can be produced on
        # search results. A fresh ``LegalGraph`` is created if none is provided.
        self.graph = graph or LegalGraph()
        self._init_schema()
        self._load_graph()

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
                    identifier UNINDEXED,
                    type UNINDEXED,
                    text,
                    tokenize='porter'
                );
                """
            )

    def _load_graph(self) -> None:
        cur = self.conn.execute("SELECT identifier, type FROM node_fts")
        for row in cur.fetchall():
            try:
                enum_type = NodeType[row["type"].upper()]
            except KeyError:
                enum_type = NodeType.DOCUMENT
            node = GraphNode(type=enum_type, identifier=row["identifier"])
            self.graph.add_node(node)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------
    def index_node(
        self, identifier: str, node_type: str, text: str, *, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add or replace a node in the search index.

        Parameters
        ----------
        identifier:
            Stable identifier for the node.
        node_type:
            Type label such as ``"case"`` or ``"provision"``.
        text:
            Natural language content associated with the node.
        metadata:
            Optional metadata for the node. When a :class:`LegalGraph` is being
            maintained, the node is also added (or replaced) within that graph
            using the supplied metadata.
        """

        with self.conn:
            # Remove any existing entry to keep identifiers unique
            self.conn.execute("DELETE FROM node_fts WHERE identifier = ?", (identifier,))
            self.conn.execute(
                "INSERT INTO node_fts(identifier, type, text) VALUES (?, ?, ?)",
                (identifier, node_type, text),
            )

        try:
            enum_type = NodeType[node_type.upper()]
        except KeyError:
            enum_type = NodeType.DOCUMENT
        node = GraphNode(type=enum_type, identifier=identifier, metadata=metadata or {})
        self.graph.add_node(node)

    # ------------------------------------------------------------------
    # Search API
    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return typed search results and minimal subgraphs.

        Parameters
        ----------
        query:
            Search expression compatible with SQLite FTS5.
        limit:
            Maximum number of rows to return.

        Returns
        -------
        List[Dict[str, Any]]
            A list of dictionaries where each entry contains ``id``, ``type``,
            ``snippet`` and ``subgraph`` keys. ``subgraph`` contains a minimal
            representation centred on the result node.
        """

        cur = self.conn.execute(
            """
            SELECT
                identifier,
                type,
                snippet(node_fts, 2, '<b>', '</b>', '...', 20) AS snippet,
                bm25(node_fts) AS score
            FROM node_fts
            WHERE node_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, limit),
        )
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            node_id = row["identifier"]
            node_type = row["type"]
            # Build a minimal subgraph around the hit node. ``build_cloud``
            # conveniently returns the node and any directly connected edges
            # present in ``self.graph``.
            subgraph = build_cloud([(node_id, {})], self.graph, limit=1)
            results.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "snippet": row["snippet"],
                    "score": row["score"],
                    "subgraph": subgraph,
                }
            )
        return results

    def close(self) -> None:
        self.conn.close()


__all__ = ["TextIndex"]