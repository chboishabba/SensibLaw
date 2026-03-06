from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_migrate_wiki_timeline_to_itir_db(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_gwb.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    source_db = tmp_path / "wiki_timeline_aoo.sqlite"
    dest_db = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "events": [
            {
                "event_id": "ev:1",
                "anchor": {"year": 2001, "month": 9, "day": 11, "precision": "day", "kind": "mention", "text": "September 11, 2001"},
                "section": "Narrative",
                "text": "Example event",
                "actors": [],
                "objects": [],
                "steps": [],
                "links": [],
            }
        ],
    }

    persist_wiki_timeline_aoo_run(
        db_path=source_db,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/migrate_wiki_timeline_to_itir_db.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-db",
            str(source_db),
            "--dest-db",
            str(dest_db),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1  # required suffix set is incomplete in this synthetic fixture
    assert dest_db.exists()
    with sqlite3.connect(dest_db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute(
            "SELECT run_id, n_events FROM wiki_timeline_aoo_runs WHERE timeline_path LIKE ?",
            ("%wiki_timeline_gwb.json",),
        ).fetchone()
        assert run is not None
        assert int(run["n_events"]) == 1
