#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

def main() -> None:
    p = argparse.ArgumentParser(description="Query wiki timeline payloads from the canonical SQLite store.")
    p.add_argument("--db-path", help="Path to canonical ITIR sqlite database.")
    p.add_argument(
        "--projection",
        choices=["raw", "fact_timeline", "timeline_view"],
        default="raw",
        help="Optional projection view over the loaded payload.",
    )
    p.add_argument(
        "--with-source-meta",
        action="store_true",
        help="Wrap the result as {source, rel_path, timeline_suffix, payload}.",
    )
    p.add_argument(
        "--source-variant",
        choices=["timeline", "aoo", "aoo_all"],
        help="Optional source-registry variant override when using --source-key.",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id", help="Exact run_id to load.")
    g.add_argument("--timeline-path-suffix", help="Pick best run whose stored timeline_path ends with this suffix.")
    g.add_argument("--rel-path", help="Resolve raw payload by canonical rel_path using Python suffix-candidate policy.")
    g.add_argument("--source-key", help="Named source key resolved through the Python wiki timeline source registry.")
    g.add_argument("--list-runs", action="store_true", help="List available runs.")
    args = p.parse_args()

    sb_root = Path(__file__).resolve().parents[1]
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    from src.storage.sqlite_runtime import connect_sqlite  # noqa: PLC0415
    from src.wiki_timeline.query_runtime import (  # noqa: PLC0415
        load_projection_payload,
        load_rel_path_envelope,
        load_source_meta_envelope,
        pick_best_run_for_timeline_suffix,
        resolve_query_db_path,
    )
    from src.wiki_timeline.source_registry import resolve_source_config  # noqa: PLC0415

    db_path = resolve_query_db_path(args.db_path)
    if not db_path.exists():
        sys.stdout.write("null\n")
        return

    with connect_sqlite(db_path) as conn:

        if args.list_runs:
            rows = conn.execute(
                """
                SELECT run_id, generated_at, timeline_path, n_events
                FROM wiki_timeline_aoo_runs
                ORDER BY generated_at DESC, n_events DESC, run_id ASC
                """
            ).fetchall()
            out = [
                {
                    "run_id": str(r["run_id"]),
                    "generated_at": str(r["generated_at"]),
                    "timeline_path": str(r["timeline_path"] or ""),
                    "n_events": int(r["n_events"] or 0),
                }
                for r in rows
            ]
            sys.stdout.write(json.dumps(out, indent=2, sort_keys=True))
            sys.stdout.write("\n")
            return

        run_id = str(args.run_id) if args.run_id else None
        if args.rel_path:
            result = load_rel_path_envelope(
                conn,
                rel_path=str(args.rel_path),
                projection=args.projection,
            )
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) if result is not None else "null")
            sys.stdout.write("\n")
            return

        if args.source_key and args.with_source_meta:
            fallback = "gwb" if args.projection == "timeline_view" else "hca"
            result = load_source_meta_envelope(
                conn,
                source_key=args.source_key,
                projection=args.projection,
                fallback=fallback,
                variant=args.source_variant,
            )
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) if result is not None else "null")
            sys.stdout.write("\n")
            return

        timeline_suffix = str(args.timeline_path_suffix) if args.timeline_path_suffix else None
        if args.source_key:
            fallback = "gwb" if args.projection == "timeline_view" else "hca"
            source_meta = resolve_source_config(
                args.source_key,
                projection=args.projection,
                fallback=fallback,
                variant=args.source_variant,
            )
            timeline_suffix = source_meta["timeline_suffix"]
        if not run_id and timeline_suffix:
            run_id = pick_best_run_for_timeline_suffix(conn, timeline_suffix)
        if not run_id:
            sys.stdout.write("null\n")
            return

        result: Any = load_projection_payload(conn, run_id=run_id, projection=args.projection)
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) if result is not None else "null")
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
