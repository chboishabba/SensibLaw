#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _pick_best_run_for_timeline_suffix(conn: sqlite3.Connection, suffix: str) -> str | None:
    rows = conn.execute(
        """
        SELECT run_id, generated_at, n_events, timeline_path
        FROM wiki_timeline_aoo_runs
        WHERE timeline_path LIKE ?
        ORDER BY generated_at DESC, n_events DESC, run_id ASC
        """,
        (f"%{suffix}",),
    ).fetchall()
    if not rows:
        return None
    return str(rows[0]["run_id"])


def _resolve_db_path() -> Path:
    raw = (
        os.environ.get("ITIR_DB_PATH")
        or os.environ.get("SL_WIKI_TIMELINE_DB")
        or os.environ.get("SL_WIKI_TIMELINE_AOO_DB")
        or ".cache_local/itir.sqlite"
    )
    return Path(raw).expanduser().resolve()


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
    g.add_argument("--source-key", help="Named source key resolved through the Python wiki timeline source registry.")
    g.add_argument("--list-runs", action="store_true", help="List available runs.")
    args = p.parse_args()

    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else _resolve_db_path()
    if not db_path.exists():
        sys.stdout.write("null\n")
        return

    sb_root = Path(__file__).resolve().parents[1]
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    from src.wiki_timeline.fact_timeline_projection import build_fact_timeline_projection  # noqa: PLC0415
    from src.wiki_timeline.numeric_projection import apply_numeric_projection  # noqa: PLC0415
    from src.wiki_timeline.source_registry import resolve_source_config  # noqa: PLC0415
    from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized  # noqa: PLC0415
    from src.wiki_timeline.timeline_view_projection import build_timeline_view_projection  # noqa: PLC0415

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

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
        source_meta: dict[str, str] | None = None
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
            run_id = _pick_best_run_for_timeline_suffix(conn, timeline_suffix)
        if not run_id:
            sys.stdout.write("null\n")
            return

        payload: dict[str, Any] | None = load_run_payload_from_normalized(conn, run_id)
        if payload is not None:
            payload = apply_numeric_projection(payload)
        if payload is not None and args.projection == "timeline_view":
            payload = build_timeline_view_projection(payload)
        if payload is not None and args.projection == "fact_timeline":
            payload = build_fact_timeline_projection(payload)
        result: Any = payload
        if payload is not None and args.with_source_meta and source_meta is not None:
            result = {
                "source": source_meta["source"],
                "rel_path": source_meta["rel_path"],
                "timeline_suffix": source_meta["timeline_suffix"],
                "payload": payload,
            }
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) if result is not None else "null")
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
