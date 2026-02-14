#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _load_run_payload(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT run_id, generated_at, out_meta_json, parser_json, n_events, timeline_path
        FROM wiki_timeline_aoo_runs
        WHERE run_id=?
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return None

    out_meta = json.loads(row["out_meta_json"]) if row["out_meta_json"] else {}
    parser = json.loads(row["parser_json"]) if row["parser_json"] else {}

    ev_rows = conn.execute(
        """
        SELECT event_id, anchor_year, anchor_month, anchor_day, event_json
        FROM wiki_timeline_aoo_events
        WHERE run_id=?
        """,
        (run_id,),
    ).fetchall()

    events: list[dict[str, Any]] = []
    for r in ev_rows:
        try:
            ev = json.loads(r["event_json"])
        except Exception:
            continue
        if isinstance(ev, dict):
            events.append(ev)

    # Deterministic order: anchor ymd then event_id.
    def sort_key(ev: dict[str, Any]) -> tuple[int, int, int, str]:
        a = ev.get("anchor") if isinstance(ev.get("anchor"), dict) else {}
        y = int(a.get("year") or 0) if a else 0
        m = int(a.get("month") or 99) if a else 99
        d = int(a.get("day") or 99) if a else 99
        eid = str(ev.get("event_id") or "")
        # Unknown year sorts last
        y2 = y if y > 0 else 9999
        return (y2, m, d, eid)

    events.sort(key=sort_key)

    payload = dict(out_meta)
    payload["parser"] = parser
    payload["events"] = events
    payload["run_id"] = str(row["run_id"])
    payload["generated_at"] = str(out_meta.get("generated_at") or row["generated_at"] or "unknown")
    payload["source_timeline"] = payload.get("source_timeline") or {"path": row["timeline_path"], "snapshot": None}
    return payload


def _pick_best_run_for_timeline_suffix(conn: sqlite3.Connection, suffix: str) -> str | None:
    # Prefer runs whose timeline_path ends with the suffix. timeline_path is stored as a string (usually absolute).
    # Deterministic selection: newest generated_at (ISO lexical) then n_events desc then run_id.
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


def main() -> None:
    p = argparse.ArgumentParser(description="Query wiki timeline AAO payloads from the canonical SQLite store.")
    p.add_argument("--db-path", required=True, help="Path to wiki_timeline_aoo.sqlite")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id", help="Exact run_id to load.")
    g.add_argument(
        "--timeline-path-suffix",
        help="Pick best run whose stored timeline_path ends with this suffix (e.g. wiki_timeline_gwb_public_bios_v1.json).",
    )
    g.add_argument("--list-runs", action="store_true", help="List available runs (run_id + timeline_path + generated_at + n_events).")
    args = p.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.exists():
        sys.stdout.write("null\n")
        return

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
        if not run_id and args.timeline_path_suffix:
            run_id = _pick_best_run_for_timeline_suffix(conn, str(args.timeline_path_suffix))

        if not run_id:
            sys.stdout.write("null\n")
            return

        payload = _load_run_payload(conn, run_id)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) if payload is not None else "null")
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()

