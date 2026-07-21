"""Inspect the tracked GWB SQLite artifact without assuming its schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any


_TEXT_COLUMN_HINTS = {
    "text",
    "content",
    "canonical_text",
    "body",
    "source_text",
    "payload",
    "raw_text",
    "excerpt",
    "snippet",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=3)
    return parser.parse_args()


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_inventory(
    connection: sqlite3.Connection, table: str, *, sample_limit: int
) -> dict[str, Any]:
    columns = [
        {
            "name": str(row[1]),
            "type": str(row[2]),
            "not_null": bool(row[3]),
            "primary_key_position": int(row[5]),
        }
        for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
    ]
    row_count = int(
        connection.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0]
    )
    text_columns = [
        column["name"]
        for column in columns
        if str(column["name"]).casefold() in _TEXT_COLUMN_HINTS
        or "text" in str(column["type"]).casefold()
        or "char" in str(column["type"]).casefold()
        or "clob" in str(column["type"]).casefold()
    ]
    samples: list[dict[str, object]] = []
    if text_columns and sample_limit > 0:
        selected = ", ".join(_quote(column) for column in text_columns)
        query = (
            f"SELECT {selected} FROM {_quote(table)} "
            f"LIMIT {max(sample_limit, 0)}"
        )
        for row in connection.execute(query):
            sample: dict[str, object] = {}
            for column, value in zip(text_columns, row, strict=True):
                if isinstance(value, bytes):
                    sample[column] = {
                        "binary_bytes": len(value),
                        "prefix_hex": value[:32].hex(),
                    }
                elif value is None:
                    sample[column] = None
                else:
                    text = str(value)
                    sample[column] = {
                        "characters": len(text),
                        "prefix": text[:240],
                    }
            samples.append(sample)
    return {
        "table": table,
        "row_count": row_count,
        "columns": columns,
        "text_columns": text_columns,
        "samples": samples,
    }


def inspect_database(path: Path, *, sample_limit: int = 3) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        tables = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        inventory = [
            _table_inventory(connection, table, sample_limit=sample_limit)
            for table in tables
        ]
    finally:
        connection.close()
    return {
        "database": str(path),
        "size_bytes": path.stat().st_size,
        "integrity_check": integrity,
        "table_count": len(tables),
        "tables": inventory,
    }


def main() -> int:
    args = _parse_args()
    result = inspect_database(args.database, sample_limit=args.sample_limit)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
