from __future__ import annotations

import sqlite3

from src.storage import VersionedStore


def test_receipts_indexes_are_created_for_existing_database(tmp_path) -> None:
    db_path = tmp_path / "store.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                simhash TEXT,
                minhash TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = VersionedStore(str(db_path))
    try:
        rows = store.conn.execute("PRAGMA index_list('receipts')").fetchall()
        index_names = {row["name"] for row in rows}

        assert "idx_receipts_simhash" in index_names
        assert "idx_receipts_minhash" in index_names
    finally:
        store.conn.close()
