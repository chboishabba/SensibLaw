from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from src.wiki_timeline.numeric_projection import apply_numeric_projection
from src.wiki_timeline.source_registry import normalize_source_key, resolve_source_config
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized
from src.wiki_timeline.timeline_view_projection import build_timeline_view_projection


def resolve_query_db_path(explicit_db_path: str | None = None) -> Path:
    raw = (
        (explicit_db_path or "").strip()
        or os.environ.get("ITIR_DB_PATH")
        or os.environ.get("SL_WIKI_TIMELINE_DB")
        or os.environ.get("SL_WIKI_TIMELINE_AOO_DB")
        or ".cache_local/itir.sqlite"
    )
    return Path(raw).expanduser().resolve()


def pick_best_run_for_timeline_suffix(conn: sqlite3.Connection, suffix: str) -> str | None:
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


def timeline_suffix_candidates_for_rel_path(rel_path: str) -> list[str]:
    base = Path(rel_path).name
    candidates = {base}
    if base.endswith("_aoo.json"):
        candidates.add(f"{base[: -len('_aoo.json')]}.json")
    return [item for item in candidates if item]


def load_projection_payload(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    projection: str,
) -> dict[str, Any] | None:
    payload = load_run_payload_from_normalized(conn, run_id)
    if payload is None:
        return None
    payload = apply_numeric_projection(payload)
    if projection == "timeline_view":
        return build_timeline_view_projection(payload)
    if projection == "fact_timeline":
        from src.wiki_timeline.fact_timeline_projection import build_fact_timeline_projection

        return build_fact_timeline_projection(payload)
    return payload


def load_source_meta_envelope(
    conn: sqlite3.Connection,
    *,
    source_key: Any,
    projection: str,
    fallback: str,
    variant: str | None = None,
) -> dict[str, Any] | None:
    normalized_source = normalize_source_key(source_key, fallback=fallback)
    source_meta = resolve_source_config(
        normalized_source,
        projection=projection,
        fallback=fallback,
        variant=variant,
    )
    run_id = pick_best_run_for_timeline_suffix(conn, source_meta["timeline_suffix"])
    if not run_id:
        return None
    payload = load_projection_payload(conn, run_id=run_id, projection=projection)
    if payload is None:
        return None
    return {
        "source": source_meta["source"],
        "rel_path": source_meta["rel_path"],
        "timeline_suffix": source_meta["timeline_suffix"],
        "payload": payload,
    }


def load_rel_path_envelope(
    conn: sqlite3.Connection,
    *,
    rel_path: str,
    projection: str,
) -> dict[str, Any] | None:
    for suffix in timeline_suffix_candidates_for_rel_path(rel_path):
        run_id = pick_best_run_for_timeline_suffix(conn, suffix)
        if not run_id:
            continue
        payload = load_projection_payload(conn, run_id=run_id, projection=projection)
        if payload is None:
            continue
        return {
            "rel_path": rel_path,
            "timeline_suffix": suffix,
            "payload": payload,
        }
    return None
