from __future__ import annotations

import sqlite3
import json
import difflib
from datetime import date
from pathlib import Path
from typing import Optional

from ..models.document import Document, DocumentMetadata


class VersionedStore:
    """SQLite-backed store maintaining versioned documents using FTS5."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                );

                CREATE TABLE IF NOT EXISTS revisions (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    effective_date TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source_url TEXT,
                    retrieved_at TEXT,
                    checksum TEXT,
                    licence TEXT,
                    document_json TEXT,
                    PRIMARY KEY (doc_id, rev_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS revisions_fts USING fts5(
                    body, metadata, content='revisions', content_rowid='rowid'
                );
                """
            )

            # Migration: ensure the revisions table has a document_json column
            columns = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(revisions)")
            }
            if "document_json" not in columns:
                self.conn.execute(
                    "ALTER TABLE revisions ADD COLUMN document_json TEXT"
                )

    # ------------------------------------------------------------------
    # ID generation and revision storage
    # ------------------------------------------------------------------
    def generate_id(self) -> int:
        """Generate and return a new unique document ID."""
        with self.conn:
            cur = self.conn.execute("INSERT INTO documents DEFAULT VALUES")
            lastrowid = cur.lastrowid
            assert lastrowid is not None
            return lastrowid

    def add_revision(
        self, doc_id: int, document: Document, effective_date: date
    ) -> int:
        """Add a new revision for a document.

        Args:
            doc_id: Identifier of the document to update.
            document: Document content to store.
            effective_date: Date this revision takes effect.

        Returns:
            The revision number assigned to the stored revision.
        """
        metadata_json = json.dumps(document.metadata.to_dict())
        retrieved_at = (
            document.metadata.retrieved_at.isoformat()
            if document.metadata.retrieved_at
            else None
        )
        document_json = document.to_json()
        with self.conn:
            cur = self.conn.execute(
                "SELECT COALESCE(MAX(rev_id), 0) + 1 FROM revisions WHERE doc_id = ?",
                (doc_id,),
            )
            rev_id = cur.fetchone()[0]
            self.conn.execute(
                """
                INSERT INTO revisions (
                    doc_id, rev_id, effective_date, metadata, body,
                    source_url, retrieved_at, checksum, licence, document_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    rev_id,
                    effective_date.isoformat(),
                    metadata_json,
                    document.body,
                    document.metadata.source_url,
                    retrieved_at,
                    document.metadata.checksum,
                    document.metadata.licence,
                    document_json,
                ),
            )
            # keep FTS table in sync
            self.conn.execute(
                "INSERT INTO revisions_fts(rowid, body, metadata) VALUES (last_insert_rowid(), ?, ?)",
                (document.body, metadata_json),
            )
        return rev_id

    # ------------------------------------------------------------------
    # Retrieval and diff utilities
    # ------------------------------------------------------------------
    def snapshot(self, doc_id: int, as_at: date) -> Optional[Document]:
        """Return the document state as of a given date.

        Args:
            doc_id: Document identifier.
            as_at: Date for which the snapshot should be taken.
        """
        row = self.conn.execute(
            """
            SELECT metadata, body, document_json FROM revisions
            WHERE doc_id = ? AND effective_date <= ?
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            (doc_id, as_at.isoformat()),
        ).fetchone()
        if row is None:
            return None
        return self._document_from_row(row)

    def get_by_canonical_id(self, canonical_id: str) -> Optional[Document]:
        """Return the latest revision for a document by its canonical ID."""

        rows = self.conn.execute(
            """
            SELECT r.metadata, r.body, r.document_json
            FROM revisions r
            JOIN (
                SELECT doc_id, MAX(rev_id) AS rev_id
                FROM revisions
                GROUP BY doc_id
            ) latest ON r.doc_id = latest.doc_id AND r.rev_id = latest.rev_id
            """
        )
        for row in rows:
            document = self._document_from_row(row)
            if document.metadata.canonical_id == canonical_id:
                return document
        return None

    def _document_from_row(self, row: sqlite3.Row) -> Document:
        """Deserialize a document row, preferring the stored JSON payload."""

        keys = row.keys() if hasattr(row, "keys") else []
        document_json = row["document_json"] if "document_json" in keys else None

        if document_json:
            return Document.from_json(document_json)

        metadata = DocumentMetadata.from_dict(json.loads(row["metadata"]))
        return Document(metadata=metadata, body=row["body"])

    def diff(self, doc_id: int, rev_a: int, rev_b: int) -> str:
        """Return a unified diff between two revisions of a document."""
        row_a = self.conn.execute(
            "SELECT body FROM revisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_a),
        ).fetchone()
        row_b = self.conn.execute(
            "SELECT body FROM revisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_b),
        ).fetchone()
        if row_a is None or row_b is None:
            raise ValueError("Revision not found")
        a_lines = row_a["body"].splitlines()
        b_lines = row_b["body"].splitlines()
        diff = difflib.unified_diff(
            a_lines,
            b_lines,
            fromfile=f"rev{rev_a}",
            tofile=f"rev{rev_b}",
            lineterm="",
        )
        return "\n".join(diff)

    def close(self) -> None:
        self.conn.close()
