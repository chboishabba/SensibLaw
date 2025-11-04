from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _has_document_json_column(conn: sqlite3.Connection) -> bool:
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(revisions)")
    }
    return "document_json" in columns


def _fts_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'revisions_fts'"
    ).fetchall()
    return [row["name"] for row in rows]


def drop_document_json_column(conn: sqlite3.Connection) -> bool:
    """Drop the legacy ``document_json`` column if it exists."""

    if not _has_document_json_column(conn):
        return False

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        with conn:
            conn.execute("ALTER TABLE revisions RENAME TO revisions_with_json")
            conn.executescript(
                """
                CREATE TABLE revisions (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    effective_date TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source_url TEXT,
                    retrieved_at TEXT,
                    checksum TEXT,
                    licence TEXT,
                    PRIMARY KEY (doc_id, rev_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(id)
                );
                """
            )
            conn.execute(
                """
                INSERT INTO revisions(rowid, doc_id, rev_id, effective_date, metadata, body,
                                      source_url, retrieved_at, checksum, licence)
                SELECT rowid, doc_id, rev_id, effective_date, metadata, body,
                       source_url, retrieved_at, checksum, licence
                FROM revisions_with_json
                """
            )
            conn.execute("DROP TABLE revisions_with_json")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    if _fts_tables(conn):
        conn.execute("INSERT INTO revisions_fts(revisions_fts) VALUES('rebuild')")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Drop the legacy revisions.document_json column."
    )
    parser.add_argument("database", type=Path, help="Path to the SQLite database file")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.database))
    conn.row_factory = sqlite3.Row
    try:
        dropped = drop_document_json_column(conn)
    finally:
        conn.close()

    if dropped:
        print("Removed revisions.document_json column")
    else:
        print("No document_json column present; no changes made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
