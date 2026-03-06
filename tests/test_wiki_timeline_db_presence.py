from __future__ import annotations

import os
import sqlite3
from pathlib import Path


SUFFIXES = [
    "wiki_timeline_gwb.json",
    "wiki_timeline_gwb_public_bios_v1.json",
    "wiki_timeline_hca_s942025_aoo.json",
    "wiki_timeline_legal_principles_au_v1.json",
    "wiki_timeline_legal_principles_au_v1_follow.json",
]


def _pick_best_run(conn: sqlite3.Connection, suffix: str) -> str | None:
    row = conn.execute(
        """
        SELECT run_id
        FROM wiki_timeline_aoo_runs
        WHERE timeline_path LIKE ?
        ORDER BY generated_at DESC, n_events DESC, run_id ASC
        LIMIT 1
        """,
        (f"%{suffix}",),
    ).fetchone()
    return str(row["run_id"]) if row else None


def test_db_contains_all_required_timelines():
    repo_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("ITIR_DB_PATH")
        or os.environ.get("SL_WIKI_TIMELINE_DB")
        or os.environ.get("SL_WIKI_TIMELINE_AOO_DB")
        or repo_root / ".cache_local" / "itir.sqlite"
    )
    assert db_path.exists(), f"DB missing at {db_path}"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for suffix in SUFFIXES:
            run_id = _pick_best_run(conn, suffix)
            assert run_id, f"Missing DB run for suffix {suffix}"
            ev_count = conn.execute("SELECT COUNT(*) AS c FROM wiki_timeline_aoo_events WHERE run_id=?", (run_id,)).fetchone()["c"]
            assert ev_count > 0, f"No events for run {run_id} ({suffix})"
