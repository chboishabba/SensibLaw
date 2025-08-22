from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("LEDGER_DB", "corrections.db"))


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS corrections (
            node_id TEXT NOT NULL,
            before_hash TEXT NOT NULL,
            after_hash TEXT NOT NULL,
            reason TEXT NOT NULL,
            reporter TEXT NOT NULL,
            prev_hash TEXT,
            this_hash TEXT NOT NULL
        )
        """
    )


def append_correction(
    node_id: str,
    before_hash: str,
    after_hash: str,
    reason: str,
    reporter: str,
    prev_hash: str | None,
) -> str:
    """Append a correction entry to the ledger.

    The entry body is a pipe-separated string of the provided fields. A SHA-256
    hash of this body is computed and stored as ``this_hash``. The new entry is
    inserted into the ``corrections`` table of the SQLite database configured by
    the ``LEDGER_DB`` environment variable (default ``corrections.db``).

    Returns the computed ``this_hash``.
    """

    body = "|".join(
        [node_id, before_hash, after_hash, reason, reporter, prev_hash or ""]
    )
    this_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    with sqlite3.connect(DB_PATH) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO corrections (
                node_id, before_hash, after_hash, reason, reporter, prev_hash, this_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                before_hash,
                after_hash,
                reason,
                reporter,
                prev_hash,
                this_hash,
            ),
        )
    return this_hash
