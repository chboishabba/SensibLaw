import json
import sqlite3
from pathlib import Path

from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_wiki_timeline_aoo_sqlite_persist_is_idempotent(tmp_path: Path) -> None:
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps({"snapshot": {"rev": 1}, "events": []}, sort_keys=True), encoding="utf-8")

    extractor_path = tmp_path / "extractor.py"
    extractor_path.write_text("# extractor\n", encoding="utf-8")

    out = {
        "ok": True,
        "generated_at": "2026-02-14T00:00:00Z",
        "parser": {"name": "spacy", "model": "en_core_web_sm", "version": "0.0"},
        "extraction_profile": {"profile_id": "test", "profile_version": "1.0.0"},
        "source_timeline": {"path": str(timeline_path), "snapshot": {"rev": 1}},
        "events": [
            {
                "event_id": "e1",
                "anchor": {"year": 2001, "month": 9, "day": 11, "precision": "day", "kind": "explicit", "text": "September 11, 2001"},
                "section": "2001",
                "text": "Test event",
                "actors": [],
                "action": "happen",
                "steps": [],
                "objects": [],
            }
        ],
    }

    db_path = tmp_path / "wiki_timeline_aoo.sqlite"
    res1 = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=out,
        timeline_path=timeline_path,
        profile_path=None,
        candidates_path=None,
        extractor_path=extractor_path,
    )
    res2 = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=out,
        timeline_path=timeline_path,
        profile_path=None,
        candidates_path=None,
        extractor_path=extractor_path,
    )

    assert res1.run_id == res2.run_id
    assert res1.n_events == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        runs = conn.execute("SELECT run_id, n_events FROM wiki_timeline_aoo_runs").fetchall()
        assert len(runs) == 1
        assert runs[0]["run_id"] == res1.run_id
        assert runs[0]["n_events"] == 1

        events = conn.execute(
            """
            SELECT event_id, anchor_year, anchor_month, anchor_day, anchor_precision, anchor_kind, section, text
            FROM wiki_timeline_aoo_events
            WHERE run_id = ?
            """,
            (res1.run_id,),
        ).fetchall()
        assert len(events) == 1
        row = events[0]
        assert row["event_id"] == "e1"
        assert row["anchor_year"] == 2001
        assert row["anchor_month"] == 9
        assert row["anchor_day"] == 11
        assert row["anchor_precision"] == "day"
        assert row["anchor_kind"] == "explicit"
        assert row["section"] == "2001"
        assert row["text"] == "Test event"

