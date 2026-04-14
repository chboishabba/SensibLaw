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

from src.reporting.observation_lanes import (
    build_observation_summary,
    get_observation_lane,
    load_observation_activity_rows,
    load_observation_import_runs,
    query_observation_captures,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query observation-lane imports from itir.sqlite.")
    parser.add_argument("--lane", required=True, help="Observation lane key, for example openrecall or worldmonitor")
    parser.add_argument("--itir-db-path", type=Path, default=Path(".cache_local/itir.sqlite"), help="Path to target ITIR SQLite DB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    runs_parser = subparsers.add_parser("runs", help="List latest import runs")
    runs_parser.add_argument("--limit", type=int, default=10, help="Max runs to return")

    summary_parser = subparsers.add_parser("summary", help="Summarize imported captures")
    summary_parser.add_argument("--import-run-id", default=None, help="Optional import_run_id filter")
    summary_parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    summary_parser.add_argument("--source-kind", default=None, help="Optional source-kind/app filter")

    captures_parser = subparsers.add_parser("captures", help="List recent imported captures")
    captures_parser.add_argument("--import-run-id", default=None, help="Optional import_run_id filter")
    captures_parser.add_argument("--date", default=None, help="Optional captured_date filter (YYYY-MM-DD)")
    captures_parser.add_argument("--source-kind", default=None, help="Optional source kind/app filter")
    captures_parser.add_argument("--text-query", default=None, help="Optional text filter")
    captures_parser.add_argument("--limit", type=int, default=25, help="Max captures to return")

    activity_parser = subparsers.add_parser("activity", help="List activity rows by date")
    activity_parser.add_argument("--date", required=True, help="Captured date (YYYY-MM-DD)")
    activity_parser.add_argument("--limit", type=int, default=100, help="Max rows to return")

    args = parser.parse_args(argv)
    lane = get_observation_lane(args.lane)
    if lane is None:
        raise ValueError(f"Unknown observation lane: {args.lane}")

    with _connect(args.itir_db_path) as conn:
        lane.ensure_schema(conn)
        payload: dict[str, object]
        if args.command == "runs":
            payload = {
                "ok": True,
                "lane": lane.key,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "runs": load_observation_import_runs(conn, lane.key, limit=args.limit),
            }
        elif args.command == "summary":
            payload = {
                "ok": True,
                "lane": lane.key,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "summary": build_observation_summary(
                    conn,
                    lane.key,
                    import_run_id=args.import_run_id,
                    date=args.date,
                    source_kind=args.source_kind,
                ),
            }
        elif args.command == "activity":
            payload = {
                "ok": True,
                "lane": lane.key,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "activityRows": load_observation_activity_rows(conn, lane.key, date=args.date, limit=args.limit),
            }
        else:
            payload = {
                "ok": True,
                "lane": lane.key,
                "itirDbPath": str(args.itir_db_path.resolve()),
                "captures": query_observation_captures(
                    conn,
                    lane.key,
                    import_run_id=args.import_run_id,
                    date=args.date,
                    source_kind=args.source_kind,
                    text_query=args.text_query,
                    limit=args.limit,
                ),
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
