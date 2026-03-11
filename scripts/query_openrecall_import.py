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

from src.reporting.openrecall_import import (
    build_openrecall_capture_summary,
    ensure_openrecall_capture_schema,
    load_openrecall_import_runs,
    query_openrecall_captures,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_openrecall_capture_schema(conn)
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query imported OpenRecall captures from itir.sqlite.")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Path to target ITIR SQLite DB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    runs_parser = subparsers.add_parser("runs", help="List latest OpenRecall import runs")
    runs_parser.add_argument("--limit", type=int, default=10, help="Max runs to return")

    summary_parser = subparsers.add_parser("summary", help="Summarize imported captures")
    summary_parser.add_argument("--import-run-id", default=None, help="Optional import-run filter")
    summary_parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    summary_parser.add_argument("--app-name", default=None, help="Optional app-name filter")

    captures_parser = subparsers.add_parser("captures", help="List recent imported captures")
    captures_parser.add_argument("--import-run-id", default=None, help="Optional import-run filter")
    captures_parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    captures_parser.add_argument("--app-name", default=None, help="Optional app-name filter")
    captures_parser.add_argument("--text-query", default=None, help="Optional OCR/title/app substring filter")
    captures_parser.add_argument("--limit", type=int, default=25, help="Max captures to return")

    args = parser.parse_args(argv)
    with _connect(args.itir_db_path) as conn:
        payload: dict[str, object]
        if args.command == "runs":
            payload = {
                "ok": True,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "runs": load_openrecall_import_runs(conn, limit=args.limit),
            }
        elif args.command == "summary":
            payload = {
                "ok": True,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "summary": build_openrecall_capture_summary(
                    conn,
                    import_run_id=args.import_run_id,
                    date=args.date,
                    app_name=args.app_name,
                ),
            }
        else:
            payload = {
                "ok": True,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "captures": query_openrecall_captures(
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
