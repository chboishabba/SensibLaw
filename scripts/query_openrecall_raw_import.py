#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.reporting.openrecall_raw_import import (
    ensure_openrecall_raw_row_schema,
    load_openrecall_raw_import_runs,
    query_openrecall_raw_rows,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_openrecall_raw_row_schema(conn)
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query raw OpenRecall row staging from itir.sqlite.")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Path to target ITIR SQLite DB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    runs_parser = subparsers.add_parser("runs", help="List latest raw-row import runs")
    runs_parser.add_argument("--limit", type=int, default=10, help="Max runs to return")

    rows_parser = subparsers.add_parser("rows", help="List recent imported raw rows")
    rows_parser.add_argument("--import-run-id", default=None, help="Optional import-run filter")
    rows_parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    rows_parser.add_argument("--app-name", default=None, help="Optional app-name filter")
    rows_parser.add_argument("--text-query", default=None, help="Optional OCR/title/app substring filter")
    rows_parser.add_argument("--limit", type=int, default=25, help="Max rows to return")

    args = parser.parse_args(argv)
    with _connect(args.itir_db_path) as conn:
        if args.command == "runs":
            payload = {
                "ok": True,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "runs": load_openrecall_raw_import_runs(conn, limit=args.limit),
            }
        else:
            payload = {
                "ok": True,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "rows": query_openrecall_raw_rows(
                    conn,
                    import_run_id=args.import_run_id,
                    date=args.date,
                    app_name=args.app_name,
                    text_query=args.text_query,
                    limit=args.limit,
                ),
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
