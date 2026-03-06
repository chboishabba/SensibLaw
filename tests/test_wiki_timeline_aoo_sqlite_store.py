import json
import sqlite3
from pathlib import Path

from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run


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
                "text": (
                    "Civil Liability Act 2002 (NSW) s 5B(2)(a). "
                    "Art 5 applies under the Constitution. "
                    "Later discussions referenced the India–United States Civil Nuclear Agreement."
                ),
                "actors": [{"label": "A", "resolved": "A", "role": "subject", "source": "x"}],
                "action": "happen",
                "steps": [{"action": "happen", "subjects": ["A"], "objects": ["B"]}],
                "objects": [{"title": "B", "source": "wikilink"}],
                "links": ["B"],
                "citations": [{"text": "cite"}],
            }
        ],
        "fact_timeline": [{"fact_id": "f1"}],
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
        row = conn.execute(
            """
            SELECT event_id, anchor_year, anchor_month, anchor_day, anchor_precision, anchor_kind,
                   anchor_text, section, text, event_json, residual_json
            FROM wiki_timeline_aoo_events
            WHERE run_id = ?
            """,
            (res1.run_id,),
        ).fetchone()
        assert row is not None
        assert row["event_id"] == "e1"
        assert row["anchor_year"] == 2001
        assert row["anchor_month"] == 9
        assert row["anchor_day"] == 11
        assert row["anchor_precision"] == "day"
        assert row["anchor_kind"] == "explicit"
        assert row["anchor_text"] == "September 11, 2001"
        assert row["section"] == "2001"
        assert row["text"] == (
            "Civil Liability Act 2002 (NSW) s 5B(2)(a). "
            "Art 5 applies under the Constitution. "
            "Later discussions referenced the India–United States Civil Nuclear Agreement."
        )
        assert row["event_json"] == "{}"
        assert row["residual_json"] in (None, "{}")

        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_event_actors WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_event_links WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_event_objects WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_event_steps WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_event_lists WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wiki_timeline_run_lists WHERE run_id = ?", (res1.run_id,)).fetchone()[0] == 1
        structural_atoms = conn.execute(
            """
            SELECT a.norm_text, a.norm_kind
            FROM wiki_timeline_structural_atoms AS a
            JOIN wiki_timeline_event_structural_atoms AS o ON o.atom_id = a.atom_id
            WHERE o.run_id = ? AND o.event_id = ?
            ORDER BY o.occ_id
            """,
            (res1.run_id, "e1"),
        ).fetchall()
        assert [(row["norm_text"], row["norm_kind"]) for row in structural_atoms] == [
            ("act:civil_liability_act_2002_nsw", "act_ref"),
            ("sec:5b", "section_ref"),
            ("subsec:2", "subsection_ref"),
            ("para:a", "paragraph_ref"),
            ("art:5", "article_ref"),
            ("instrument:india_united_states_civil_nuclear_agreement", "instrument_ref"),
        ]

        payload = load_run_payload_from_normalized(conn, res1.run_id)
        assert payload is not None
        assert payload["events"][0]["event_id"] == "e1"
        assert payload["events"][0]["actors"][0]["label"] == "A"
        assert payload["events"][0]["steps"][0]["objects"] == ["B"]
        assert payload["fact_timeline"] == [{"fact_id": "f1"}]
