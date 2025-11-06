"""Initialise the corrections ledger schema.

This script creates the ``corrections`` table used by the append-only
ledger utilities. It mirrors the schema expected by ``src.ledger.write``
and can be invoked from the command line with the path to the SQLite
database file.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS corrections (
    node_id TEXT NOT NULL,
    before_hash TEXT NOT NULL,
    after_hash TEXT NOT NULL,
    reason TEXT NOT NULL,
    reporter TEXT NOT NULL,
    prev_hash TEXT,
    this_hash TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_corrections_hash
ON corrections(this_hash);
"""


def create_schema(database: Path) -> None:
    """Create the ledger schema in ``database`` if it does not exist."""

    connection = sqlite3.connect(str(database))
    try:
        connection.executescript(DDL)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise the corrections ledger database")
    parser.add_argument(
        "database",
        type=Path,
        help="Path to the SQLite database file that should host the corrections ledger",
    )
    args = parser.parse_args()

    create_schema(args.database)
    print(f"Initialised corrections ledger schema in {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
