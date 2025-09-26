from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..text.similarity import minhash as compute_minhash, simhash as compute_simhash


@dataclass
class Node:
    id: Optional[int]
    type: str
    data: Dict[str, Any]
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_from: str | None = None
    recorded_to: str | None = None


@dataclass
class Edge:
    id: Optional[int]
    source: int
    target: int
    type: str
    data: Optional[Dict[str, Any]] = None
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_from: str | None = None
    recorded_to: str | None = None


@dataclass
class Frame:
    id: Optional[int]
    node_id: int
    data: Dict[str, Any]


@dataclass
class ActionTemplate:
    id: Optional[int]
    name: str
    template: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Correction:
    id: Optional[int]
    node_id: int
    suggestion: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class GlossaryEntry:
    id: Optional[int]
    term: str
    definition: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Receipt:
    id: Optional[int]
    data: Dict[str, Any]
    simhash: str
    minhash: str


class Storage:
    """SQLite backed storage with simple CRUD helpers."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            self.conn.executescript(f.read())

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    def insert_node(
        self,
        type: str,
        data: Dict[str, Any],
        *,
        valid_from: str | None = None,
        valid_to: str | None = None,
        recorded_from: str | None = None,
        recorded_to: str | None = None,
    ) -> int:
        valid_from = valid_from or "1970-01-01"
        recorded_from = recorded_from or valid_from
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO nodes(type, data, valid_from, valid_to, recorded_from, recorded_to) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    type,
                    json.dumps(data),
                    valid_from,
                    valid_to,
                    recorded_from,
                    recorded_to,
                ),
            )
            return cur.lastrowid

    def get_node(self, node_id: int) -> Optional[Node]:
        row = self.conn.execute(
            "SELECT id, type, data, valid_from, valid_to, recorded_from, recorded_to FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return Node(
            id=row["id"],
            type=row["type"],
            data=json.loads(row["data"]),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            recorded_from=row["recorded_from"],
            recorded_to=row["recorded_to"],
        )

    def update_node(
        self,
        node_id: int,
        *,
        type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        recorded_from: Optional[str] = None,
        recorded_to: Optional[str] = None,
    ) -> None:
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(node_id)
        type = type if type is not None else node.type
        data = data if data is not None else node.data
        valid_from = valid_from if valid_from is not None else node.valid_from
        valid_to = valid_to if valid_to is not None else node.valid_to
        recorded_from = (
            recorded_from if recorded_from is not None else node.recorded_from
        )
        recorded_to = recorded_to if recorded_to is not None else node.recorded_to
        with self.conn:
            self.conn.execute(
                "UPDATE nodes SET type = ?, data = ?, valid_from = ?, valid_to = ?, recorded_from = ?, recorded_to = ? WHERE id = ?",
                (
                    type,
                    json.dumps(data),
                    valid_from,
                    valid_to,
                    recorded_from,
                    recorded_to,
                    node_id,
                ),
            )

    def delete_node(self, node_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))

    def fetch_node_as_at(self, node_id: int, as_at: str) -> Optional[Node]:
        row = self.conn.execute(
            """
            SELECT id, type, data, valid_from, valid_to, recorded_from, recorded_to
            FROM nodes
            WHERE id = ? AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
            """,
            (node_id, as_at, as_at),
        ).fetchone()
        if row is None:
            return None
        return Node(
            id=row["id"],
            type=row["type"],
            data=json.loads(row["data"]),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            recorded_from=row["recorded_from"],
            recorded_to=row["recorded_to"],
        )

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------
    def insert_edge(
        self,
        source: int,
        target: int,
        type: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        valid_from: str | None = None,
        valid_to: str | None = None,
        recorded_from: str | None = None,
        recorded_to: str | None = None,
    ) -> int:
        valid_from = valid_from or "1970-01-01"
        recorded_from = recorded_from or valid_from
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO edges(source, target, type, data, valid_from, valid_to, recorded_from, recorded_to) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source,
                    target,
                    type,
                    json.dumps(data) if data is not None else None,
                    valid_from,
                    valid_to,
                    recorded_from,
                    recorded_to,
                ),
            )
            return cur.lastrowid

    def get_edge(self, edge_id: int) -> Optional[Edge]:
        row = self.conn.execute(
            "SELECT id, source, target, type, data, valid_from, valid_to, recorded_from, recorded_to FROM edges WHERE id = ?",
            (edge_id,),
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row["data"]) if row["data"] is not None else None
        return Edge(
            id=row["id"],
            source=row["source"],
            target=row["target"],
            type=row["type"],
            data=data,
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            recorded_from=row["recorded_from"],
            recorded_to=row["recorded_to"],
        )

    def update_edge(
        self,
        edge_id: int,
        *,
        source: Optional[int] = None,
        target: Optional[int] = None,
        type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        recorded_from: Optional[str] = None,
        recorded_to: Optional[str] = None,
    ) -> None:
        edge = self.get_edge(edge_id)
        if edge is None:
            raise KeyError(edge_id)
        source = source if source is not None else edge.source
        target = target if target is not None else edge.target
        type = type if type is not None else edge.type
        data = data if data is not None else edge.data
        valid_from = valid_from if valid_from is not None else edge.valid_from
        valid_to = valid_to if valid_to is not None else edge.valid_to
        recorded_from = (
            recorded_from if recorded_from is not None else edge.recorded_from
        )
        recorded_to = recorded_to if recorded_to is not None else edge.recorded_to
        with self.conn:
            self.conn.execute(
                """
                UPDATE edges
                SET source = ?, target = ?, type = ?, data = ?,
                    valid_from = ?, valid_to = ?, recorded_from = ?, recorded_to = ?
                WHERE id = ?
                """,
                (
                    source,
                    target,
                    type,
                    json.dumps(data) if data is not None else None,
                    valid_from,
                    valid_to,
                    recorded_from,
                    recorded_to,
                    edge_id,
                ),
            )

    def delete_edge(self, edge_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))

    def fetch_edges_as_at(self, node_id: int, as_at: str) -> list[Edge]:
        rows = self.conn.execute(
            """
            SELECT id, source, target, type, data, valid_from, valid_to, recorded_from, recorded_to
            FROM edges
            WHERE (source = ? OR target = ?)
              AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
            """,
            (node_id, node_id, as_at, as_at),
        ).fetchall()
        edges: list[Edge] = []
        for row in rows:
            data = json.loads(row["data"]) if row["data"] is not None else None
            edges.append(
                Edge(
                    id=row["id"],
                    source=row["source"],
                    target=row["target"],
                    type=row["type"],
                    data=data,
                    valid_from=row["valid_from"],
                    valid_to=row["valid_to"],
                    recorded_from=row["recorded_from"],
                    recorded_to=row["recorded_to"],
                )
            )
        return edges

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------
    def insert_frame(self, node_id: int, data: Dict[str, Any]) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO frames(node_id, data) VALUES (?, ?)",
                (node_id, json.dumps(data)),
            )
            return cur.lastrowid

    def get_frame(self, frame_id: int) -> Optional[Frame]:
        row = self.conn.execute(
            "SELECT id, node_id, data FROM frames WHERE id = ?",
            (frame_id,),
        ).fetchone()
        if row is None:
            return None
        return Frame(id=row["id"], node_id=row["node_id"], data=json.loads(row["data"]))

    def update_frame(
        self,
        frame_id: int,
        *,
        node_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        frame = self.get_frame(frame_id)
        if frame is None:
            raise KeyError(frame_id)
        node_id = node_id if node_id is not None else frame.node_id
        data = data if data is not None else frame.data
        with self.conn:
            self.conn.execute(
                "UPDATE frames SET node_id = ?, data = ? WHERE id = ?",
                (node_id, json.dumps(data), frame_id),
            )

    def delete_frame(self, frame_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM frames WHERE id = ?", (frame_id,))

    # ------------------------------------------------------------------
    # Action templates
    # ------------------------------------------------------------------
    def insert_action_template(
        self,
        name: str,
        template: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO action_templates(name, template, metadata) VALUES (?, ?, ?)",
                (
                    name,
                    json.dumps(template),
                    json.dumps(metadata) if metadata is not None else None,
                ),
            )
            return cur.lastrowid

    def get_action_template(self, template_id: int) -> Optional[ActionTemplate]:
        row = self.conn.execute(
            "SELECT id, name, template, metadata FROM action_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if row is None:
            return None
        metadata = json.loads(row["metadata"]) if row["metadata"] is not None else None
        return ActionTemplate(
            id=row["id"],
            name=row["name"],
            template=json.loads(row["template"]),
            metadata=metadata,
        )

    def update_action_template(
        self,
        template_id: int,
        *,
        name: Optional[str] = None,
        template: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        current = self.get_action_template(template_id)
        if current is None:
            raise KeyError(template_id)
        name = name if name is not None else current.name
        template = template if template is not None else current.template
        metadata = metadata if metadata is not None else current.metadata
        with self.conn:
            self.conn.execute(
                "UPDATE action_templates SET name = ?, template = ?, metadata = ? WHERE id = ?",
                (
                    name,
                    json.dumps(template),
                    json.dumps(metadata) if metadata is not None else None,
                    template_id,
                ),
            )

    def delete_action_template(self, template_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM action_templates WHERE id = ?",
                (template_id,),
            )

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------
    def insert_correction(
        self,
        node_id: int,
        suggestion: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO corrections(node_id, suggestion, data) VALUES (?, ?, ?)",
                (node_id, suggestion, json.dumps(data) if data is not None else None),
            )
            return cur.lastrowid

    def get_correction(self, correction_id: int) -> Optional[Correction]:
        row = self.conn.execute(
            "SELECT id, node_id, suggestion, data FROM corrections WHERE id = ?",
            (correction_id,),
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row["data"]) if row["data"] is not None else None
        return Correction(
            id=row["id"],
            node_id=row["node_id"],
            suggestion=row["suggestion"],
            data=data,
        )

    def update_correction(
        self,
        correction_id: int,
        *,
        node_id: Optional[int] = None,
        suggestion: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        current = self.get_correction(correction_id)
        if current is None:
            raise KeyError(correction_id)
        node_id = node_id if node_id is not None else current.node_id
        suggestion = suggestion if suggestion is not None else current.suggestion
        data = data if data is not None else current.data
        with self.conn:
            self.conn.execute(
                "UPDATE corrections SET node_id = ?, suggestion = ?, data = ? WHERE id = ?",
                (
                    node_id,
                    suggestion,
                    json.dumps(data) if data is not None else None,
                    correction_id,
                ),
            )

    def delete_correction(self, correction_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM corrections WHERE id = ?", (correction_id,))

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------
    def insert_glossary_entry(
        self,
        term: str,
        definition: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO glossary(term, definition, metadata) VALUES (?, ?, ?)",
                (
                    term,
                    definition,
                    json.dumps(metadata) if metadata is not None else None,
                ),
            )
            return cur.lastrowid

    def get_glossary_entry(self, entry_id: int) -> Optional[GlossaryEntry]:
        row = self.conn.execute(
            "SELECT id, term, definition, metadata FROM glossary WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            return None
        metadata = json.loads(row["metadata"]) if row["metadata"] is not None else None
        return GlossaryEntry(
            id=row["id"],
            term=row["term"],
            definition=row["definition"],
            metadata=metadata,
        )

    def get_glossary_entry_by_term(self, term: str) -> Optional[GlossaryEntry]:
        term = term.strip()
        if not term:
            return None
        row = self.conn.execute(
            "SELECT id, term, definition, metadata FROM glossary WHERE lower(term) = lower(?)",
            (term,),
        ).fetchone()
        if row is None:
            return None
        metadata = json.loads(row["metadata"]) if row["metadata"] is not None else None
        return GlossaryEntry(
            id=row["id"],
            term=row["term"],
            definition=row["definition"],
            metadata=metadata,
        )

    def find_glossary_entry_by_definition(
        self, definition: str
    ) -> Optional[GlossaryEntry]:
        definition = definition.strip()
        if not definition:
            return None
        row = self.conn.execute(
            "SELECT id, term, definition, metadata FROM glossary WHERE lower(definition) = lower(?)",
            (definition,),
        ).fetchone()
        if row is None:
            return None
        metadata = json.loads(row["metadata"]) if row["metadata"] is not None else None
        return GlossaryEntry(
            id=row["id"],
            term=row["term"],
            definition=row["definition"],
            metadata=metadata,
        )

    def update_glossary_entry(
        self,
        entry_id: int,
        *,
        term: Optional[str] = None,
        definition: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        current = self.get_glossary_entry(entry_id)
        if current is None:
            raise KeyError(entry_id)
        term = term if term is not None else current.term
        definition = definition if definition is not None else current.definition
        metadata = metadata if metadata is not None else current.metadata
        with self.conn:
            self.conn.execute(
                "UPDATE glossary SET term = ?, definition = ?, metadata = ? WHERE id = ?",
                (
                    term,
                    definition,
                    json.dumps(metadata) if metadata is not None else None,
                    entry_id,
                ),
            )

    def delete_glossary_entry(self, entry_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM glossary WHERE id = ?", (entry_id,))

    # ------------------------------------------------------------------
    # Receipts
    # ------------------------------------------------------------------
    def insert_receipt(self, data: Dict[str, Any]) -> int:
        text = data.get("text") or json.dumps(data, sort_keys=True)
        sim = compute_simhash(text)
        m = compute_minhash(text)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO receipts(data, simhash, minhash) VALUES (?, ?, ?)",
                (json.dumps(data), sim, m),
            )
            return cur.lastrowid

    def get_receipt(self, receipt_id: int) -> Optional[Receipt]:
        row = self.conn.execute(
            "SELECT id, data, simhash, minhash FROM receipts WHERE id = ?",
            (receipt_id,),
        ).fetchone()
        if row is None:
            return None
        return Receipt(
            id=row["id"],
            data=json.loads(row["data"]),
            simhash=row["simhash"],
            minhash=row["minhash"],
        )

    def update_receipt(self, receipt_id: int, data: Dict[str, Any]) -> None:
        text = data.get("text") or json.dumps(data, sort_keys=True)
        sim = compute_simhash(text)
        m = compute_minhash(text)
        with self.conn:
            self.conn.execute(
                "UPDATE receipts SET data = ?, simhash = ?, minhash = ? WHERE id = ?",
                (json.dumps(data), sim, m, receipt_id),
            )

    def delete_receipt(self, receipt_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
