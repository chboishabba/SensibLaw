#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _sum_length(conn: sqlite3.Connection, query: str, params: tuple[object, ...]) -> int:
    row = conn.execute(query, params).fetchone()
    return int((row[0] or 0) if row else 0)


def main() -> None:
    p = argparse.ArgumentParser(description="Report normalized wiki timeline storage stats.")
    p.add_argument("--db-path", default=".cache_local/itir.sqlite")
    p.add_argument("--run-id", required=True)
    args = p.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    sb_root = Path(__file__).resolve().parents[1]
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))
    from src.wiki_timeline.sqlite_store import _ensure_schema, load_run_payload_from_normalized  # noqa: PLC0415

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        run_id = str(args.run_id)
        load_run_payload_from_normalized(conn, run_id)
        event_count = int(conn.execute("SELECT COUNT(*) FROM wiki_timeline_aoo_events WHERE run_id = ?", (run_id,)).fetchone()[0] or 0)
        legacy_blob_bytes = _sum_length(conn, "SELECT SUM(LENGTH(event_json)) FROM wiki_timeline_aoo_events WHERE run_id = ?", (run_id,))
        residual_bytes = _sum_length(conn, "SELECT SUM(LENGTH(COALESCE(residual_json, '')) + LENGTH(COALESCE(action_meta_json, '')) + LENGTH(COALESCE(anchor_text, '')) + LENGTH(COALESCE(section, '')) + LENGTH(COALESCE(text, '')) + LENGTH(COALESCE(action_surface, '')) + LENGTH(COALESCE(purpose, ''))) FROM wiki_timeline_aoo_events WHERE run_id = ?", (run_id,))
        actor_bytes = _sum_length(conn, "SELECT SUM(LENGTH(COALESCE(label, '')) + LENGTH(COALESCE(resolved, '')) + LENGTH(COALESCE(role, '')) + LENGTH(COALESCE(source, ''))) FROM wiki_timeline_event_actors WHERE run_id = ?", (run_id,))
        link_bytes = _sum_length(conn, "SELECT SUM(LENGTH(title) + LENGTH(lane)) FROM wiki_timeline_event_links WHERE run_id = ?", (run_id,))
        object_bytes = _sum_length(conn, "SELECT SUM(LENGTH(COALESCE(title, '')) + LENGTH(COALESCE(source, '')) + LENGTH(object_lane) + LENGTH(COALESCE(resolver_hints_json, ''))) FROM wiki_timeline_event_objects WHERE run_id = ?", (run_id,))
        step_bytes = _sum_length(conn, "SELECT SUM(LENGTH(COALESCE(action_surface, '')) + LENGTH(COALESCE(action_meta_json, '')) + LENGTH(COALESCE(purpose, '')) + LENGTH(COALESCE(residual_json, ''))) FROM wiki_timeline_event_steps WHERE run_id = ?", (run_id,))
        step_subject_bytes = _sum_length(conn, "SELECT SUM(LENGTH(label)) FROM wiki_timeline_step_subjects WHERE run_id = ?", (run_id,))
        step_object_bytes = _sum_length(conn, "SELECT SUM(LENGTH(title) + LENGTH(object_lane) + LENGTH(COALESCE(source, ''))) FROM wiki_timeline_step_objects WHERE run_id = ?", (run_id,))
        event_list_bytes = _sum_length(conn, "SELECT SUM(LENGTH(list_name) + LENGTH(item_json)) FROM wiki_timeline_event_lists WHERE run_id = ?", (run_id,))
        run_list_bytes = _sum_length(conn, "SELECT SUM(LENGTH(list_name) + LENGTH(item_json)) FROM wiki_timeline_run_lists WHERE run_id = ?", (run_id,))
        normalized_total = residual_bytes + actor_bytes + link_bytes + object_bytes + step_bytes + step_subject_bytes + step_object_bytes + event_list_bytes + run_list_bytes

        payload = {
            "run_id": run_id,
            "event_count": event_count,
            "legacy_blob_bytes": legacy_blob_bytes,
            "normalized_bytes_estimate": normalized_total,
            "bytes_per_event_legacy": (legacy_blob_bytes / event_count) if event_count else 0.0,
            "bytes_per_event_normalized_estimate": (normalized_total / event_count) if event_count else 0.0,
            "component_bytes": {
                "event_core_and_residual": residual_bytes,
                "actors": actor_bytes,
                "links": link_bytes,
                "objects": object_bytes,
                "steps": step_bytes,
                "step_subjects": step_subject_bytes,
                "step_objects": step_object_bytes,
                "event_lists": event_list_bytes,
                "run_lists": run_list_bytes,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
