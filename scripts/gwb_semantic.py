#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/report the deterministic GWB semantic pipeline.")
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--timeline-suffix", default="wiki_timeline_gwb.json")
    run_p.add_argument("--run-id", default="")

    report_p = sub.add_parser("report")
    report_p.add_argument("--timeline-suffix", default="wiki_timeline_gwb.json")
    report_p.add_argument("--run-id", default="")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.gwb_us_law.semantic import (  # noqa: PLC0415
        build_gwb_semantic_report,
        ensure_gwb_semantic_schema,
        run_gwb_semantic_pipeline,
    )

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        if args.cmd == "run":
            payload = run_gwb_semantic_pipeline(
                conn,
                timeline_suffix=args.timeline_suffix,
                run_id=args.run_id or None,
            )
        else:
            if args.run_id:
                active_run_id = args.run_id
            else:
                run_payload = run_gwb_semantic_pipeline(
                    conn,
                    timeline_suffix=args.timeline_suffix,
                    run_id=None,
                )
                active_run_id = str(run_payload["run_id"])
            payload = build_gwb_semantic_report(conn, run_id=active_run_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
