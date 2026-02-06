from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .migrations import MIGRATIONS_DIR, MigrationRunner


@dataclass
class LegalSourceRecord:
    id: int
    legal_system_code: str
    norm_source_category_code: str
    citation: str
    title: Optional[str]
    source_url: Optional[str]
    summary: Optional[str]


@dataclass
class ActorClassRecord:
    id: int
    code: str
    label: str
    description: Optional[str]


@dataclass
class ContextFieldRecord:
    context_id: str
    context_type: str
    source: str | None
    retrieved_at: str | None
    location: str | None
    time_start: str | None
    time_end: str | None
    symbolic: bool
    payload: Any
    provenance: Any


class BaseDAO:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def _fetchone(self, query: str, params: Iterable[Any]) -> Optional[sqlite3.Row]:
        self.connection.row_factory = sqlite3.Row
        cursor = self.connection.execute(query, params)
        return cursor.fetchone()

    def _fetchall(self, query: str, params: Iterable[Any]) -> list[sqlite3.Row]:
        self.connection.row_factory = sqlite3.Row
        cursor = self.connection.execute(query, params)
        return list(cursor.fetchall())

    def _resolve_legal_system_id(self, code: str) -> int:
        row = self._fetchone("SELECT id FROM legal_systems WHERE code = ?", (code,))
        if not row:
            msg = f"Unknown legal system code: {code}"
            raise ValueError(msg)
        return int(row["id"])

    def _resolve_norm_source_category_id(self, code: str) -> int:
        row = self._fetchone(
            "SELECT id FROM norm_source_categories WHERE code = ?",
            (code,),
        )
        if not row:
            msg = f"Unknown norm source category code: {code}"
            raise ValueError(msg)
        return int(row["id"])


class LegalSourceDAO(BaseDAO):
    """CRUD helpers for :class:`legal_sources` rows."""

    def create_source(
        self,
        *,
        legal_system_code: str,
        norm_source_category_code: str,
        citation: str,
        title: str | None = None,
        source_url: str | None = None,
        promulgation_date: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
    ) -> int:
        legal_system_id = self._resolve_legal_system_id(legal_system_code)
        category_id = self._resolve_norm_source_category_id(norm_source_category_code)
        cursor = self.connection.execute(
            """
            INSERT INTO legal_sources (
                legal_system_id, norm_source_category_id, citation, title, source_url, promulgation_date, summary, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                legal_system_id,
                category_id,
                citation,
                title,
                source_url,
                promulgation_date,
                summary,
                notes,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def upsert_source(
        self,
        *,
        legal_system_code: str,
        norm_source_category_code: str,
        citation: str,
        title: str | None = None,
        source_url: str | None = None,
        promulgation_date: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
    ) -> int:
        legal_system_id = self._resolve_legal_system_id(legal_system_code)
        category_id = self._resolve_norm_source_category_id(norm_source_category_code)
        cursor = self.connection.execute(
            """
            INSERT INTO legal_sources (
                legal_system_id, norm_source_category_id, citation, title, source_url, promulgation_date, summary, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(legal_system_id, citation) DO UPDATE SET
                norm_source_category_id=excluded.norm_source_category_id,
                title=excluded.title,
                source_url=excluded.source_url,
                promulgation_date=excluded.promulgation_date,
                summary=excluded.summary,
                notes=excluded.notes
            """,
            (
                legal_system_id,
                category_id,
                citation,
                title,
                source_url,
                promulgation_date,
                summary,
                notes,
            ),
        )
        self.connection.commit()
        row_id = cursor.lastrowid
        if row_id == 0:
            existing = self._fetchone(
                "SELECT id FROM legal_sources WHERE legal_system_id = ? AND citation = ?",
                (legal_system_id, citation),
            )
            if existing:
                row_id = int(existing["id"])
        return int(row_id)

    def delete_source(self, source_id: int) -> None:
        self.connection.execute("DELETE FROM legal_sources WHERE id = ?", (source_id,))
        self.connection.commit()

    def get_by_citation(self, *, legal_system_code: str, citation: str) -> Optional[LegalSourceRecord]:
        legal_system_id = self._resolve_legal_system_id(legal_system_code)
        row = self._fetchone(
            """
            SELECT ls.id, ls.citation, ls.title, ls.source_url, ls.summary,
                   sys.code AS legal_system_code, cat.code AS norm_source_category_code
            FROM legal_sources ls
            JOIN legal_systems sys ON sys.id = ls.legal_system_id
            JOIN norm_source_categories cat ON cat.id = ls.norm_source_category_id
            WHERE ls.legal_system_id = ? AND ls.citation = ?
            """,
            (legal_system_id, citation),
        )
        if not row:
            return None
        return LegalSourceRecord(
            id=int(row["id"]),
            legal_system_code=str(row["legal_system_code"]),
            norm_source_category_code=str(row["norm_source_category_code"]),
            citation=str(row["citation"]),
            title=row["title"],
            source_url=row["source_url"],
            summary=row["summary"],
        )

    def list_sources(
        self,
        *,
        legal_system_code: str | None = None,
        norm_source_category_code: str | None = None,
    ) -> list[LegalSourceRecord]:
        conditions = []
        params: list[Any] = []
        if legal_system_code:
            conditions.append("sys.code = ?")
            params.append(legal_system_code)
        if norm_source_category_code:
            conditions.append("cat.code = ?")
            params.append(norm_source_category_code)
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        rows = self._fetchall(
            f"""
            SELECT ls.id, ls.citation, ls.title, ls.source_url, ls.summary,
                   sys.code AS legal_system_code, cat.code AS norm_source_category_code
            FROM legal_sources ls
            JOIN legal_systems sys ON sys.id = ls.legal_system_id
            JOIN norm_source_categories cat ON cat.id = ls.norm_source_category_id
            {where}
            ORDER BY sys.code, ls.citation
            """,
            params,
        )
        return [
            LegalSourceRecord(
                id=int(row["id"]),
                legal_system_code=str(row["legal_system_code"]),
                norm_source_category_code=str(row["norm_source_category_code"]),
                citation=str(row["citation"]),
                title=row["title"],
                source_url=row["source_url"],
                summary=row["summary"],
            )
            for row in rows
        ]


class ActorMappingDAO(BaseDAO):
    """Lookup helpers that connect extracted actors to canonical vocabularies."""

    def list_actor_classes(self, *, legal_system_code: str | None = None) -> list[ActorClassRecord]:
        params: list[Any] = []
        where = ""
        if legal_system_code:
            where = "WHERE sys.code = ?"
            params.append(legal_system_code)
        rows = self._fetchall(
            f"""
            SELECT ac.id, ac.code, ac.label, ac.description
            FROM actor_classes ac
            LEFT JOIN role_markers rm ON rm.actor_class_id = ac.id
            LEFT JOIN legal_systems sys ON rm.legal_system_id = sys.id
            {where}
            GROUP BY ac.id
            ORDER BY ac.code
            """,
            params,
        )
        return [
            ActorClassRecord(
                id=int(row["id"]),
                code=str(row["code"]),
                label=str(row["label"]),
                description=row["description"],
            )
            for row in rows
        ]

    def lookup_by_marker(
        self, marker: str, *, legal_system_code: str | None = None
    ) -> Optional[ActorClassRecord]:
        params: list[Any] = [marker.lower()]
        system_filter = ""
        if legal_system_code:
            system_filter = "AND (sys.code = ? OR sys.code IS NULL)"
            params.append(legal_system_code)
        rows = self._fetchall(
            f"""
            SELECT ac.id, ac.code, ac.label, ac.description
            FROM role_markers rm
            JOIN actor_classes ac ON ac.id = rm.actor_class_id
            LEFT JOIN legal_systems sys ON sys.id = rm.legal_system_id
            WHERE lower(rm.marker) = ? {system_filter}
            ORDER BY sys.code IS NULL, sys.code DESC
            LIMIT 1
            """,
            params,
        )
        if not rows:
            return None
        row = rows[0]
        return ActorClassRecord(
            id=int(row["id"]),
            code=str(row["code"]),
            label=str(row["label"]),
            description=row["description"],
        )

    def relationship_kinds(self, *, legal_system_code: str | None = None) -> list[str]:
        params: list[Any] = []
        where = ""
        if legal_system_code:
            where = "WHERE sys.code = ? OR sys.code IS NULL"
            params.append(legal_system_code)
        rows = self._fetchall(
            f"""
            SELECT rk.code
            FROM relationship_kinds rk
            LEFT JOIN legal_systems sys ON sys.id = rk.legal_system_id
            {where}
            ORDER BY rk.code
            """,
            params,
        )
        return [str(row["code"]) for row in rows]


class ContextFieldDAO(BaseDAO):
    """Read/write helpers for context_fields overlays (non-authoritative)."""

    def upsert_context_field(
        self,
        *,
        context_id: str,
        context_type: str,
        source: str | None = None,
        retrieved_at: str | None = None,
        location: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        payload: Any | None = None,
        provenance: Any | None = None,
        symbolic: bool = False,
    ) -> None:
        payload_json = json.dumps(payload) if payload is not None else None
        provenance_json = json.dumps(provenance) if provenance is not None else None
        self.connection.execute(
            """
            INSERT INTO context_fields (
                context_id, context_type, source, retrieved_at, location, time_start, time_end, payload, provenance, symbolic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(context_id) DO UPDATE SET
                context_type=excluded.context_type,
                source=excluded.source,
                retrieved_at=excluded.retrieved_at,
                location=excluded.location,
                time_start=excluded.time_start,
                time_end=excluded.time_end,
                payload=excluded.payload,
                provenance=excluded.provenance,
                symbolic=excluded.symbolic,
                updated_at=datetime('now')
            """,
            (
                context_id,
                context_type,
                source,
                retrieved_at,
                location,
                time_start,
                time_end,
                payload_json,
                provenance_json,
                1 if symbolic else 0,
            ),
        )
        self.connection.commit()

    def get(self, context_id: str) -> ContextFieldRecord | None:
        row = self._fetchone(
            """
            SELECT context_id, context_type, source, retrieved_at, location,
                   time_start, time_end, payload, provenance, symbolic
            FROM context_fields WHERE context_id = ?
            """,
            (context_id,),
        )
        if not row:
            return None
        return ContextFieldRecord(
            context_id=str(row["context_id"]),
            context_type=str(row["context_type"]),
            source=row["source"],
            retrieved_at=row["retrieved_at"],
            location=row["location"],
            time_start=row["time_start"],
            time_end=row["time_end"],
            symbolic=bool(row["symbolic"]),
            payload=json.loads(row["payload"]) if row["payload"] else None,
            provenance=json.loads(row["provenance"]) if row["provenance"] else None,
        )

    def list_by_type(self, context_type: str) -> list[ContextFieldRecord]:
        rows = self._fetchall(
            """
            SELECT context_id, context_type, source, retrieved_at, location,
                   time_start, time_end, payload, provenance, symbolic
            FROM context_fields
            WHERE context_type = ?
            ORDER BY time_start
            """,
            (context_type,),
        )
        records: list[ContextFieldRecord] = []
        for row in rows:
            records.append(
                ContextFieldRecord(
                    context_id=str(row["context_id"]),
                    context_type=str(row["context_type"]),
                    source=row["source"],
                    retrieved_at=row["retrieved_at"],
                    location=row["location"],
                    time_start=row["time_start"],
                    time_end=row["time_end"],
                    symbolic=bool(row["symbolic"]),
                    payload=json.loads(row["payload"]) if row["payload"] else None,
                    provenance=json.loads(row["provenance"]) if row["provenance"] else None,
                )
            )
        return records


def ensure_database(connection: sqlite3.Connection) -> None:
    """Apply bundled migrations to a sqlite3 connection if needed."""

    if not MIGRATIONS_DIR.exists():
        msg = f"Migration path missing: {MIGRATIONS_DIR}"
        raise FileNotFoundError(msg)
    runner = MigrationRunner(connection)
    runner.apply_all()
