from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from src.wiki_timeline.numeric_projection import apply_numeric_projection
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_apply_numeric_projection_normalizes_event_and_step_numeric_objects() -> None:
    payload = {
        "events": [
            {
                "event_id": "ev:1",
                "text": "Example event",
                "anchor": {"year": 2001, "month": 1, "day": 2, "precision": "day", "kind": "mention", "text": "2001-01-02"},
                "numeric_objects": ["per cent", "$5 million", "US$5 million"],
                "steps": [{"action": "said", "numeric_objects": ["A$1,000", "1,000aud"]}],
            }
        ]
    }

    out = apply_numeric_projection(payload)
    event = out["events"][0]
    step = event["steps"][0]

    assert sorted(event["numeric_objects"]) == ["5 million usd", "percent"]
    assert step["numeric_objects"] == ["1,000 aud"]
    assert event["numeric_mentions"] == [{"key": "5e6|usd", "label": "5 million usd"}]


def test_query_wiki_timeline_aoo_db_raw_applies_numeric_projection(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_hca_s942025_aoo.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-30T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "root_actor": {"label": "Root", "surname": "Actor"},
        "events": [
            {
                "event_id": "ev:1",
                "anchor": {"year": 2001, "month": 9, "day": 11, "precision": "day", "kind": "mention", "text": "September 11, 2001"},
                "section": "Narrative",
                "text": "Example event",
                "party": "party-a",
                "actors": [],
                "objects": [],
                "numeric_objects": ["per cent", "$5 million"],
                "steps": [{"action": "said", "subjects": ["Alice"], "objects": ["Budget"], "numeric_objects": ["A$1,000"]}],
                "links": [],
            }
        ],
    }

    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/query_wiki_timeline_aoo_db.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--timeline-path-suffix",
            timeline_path.name,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert sorted(parsed["events"][0]["numeric_objects"]) == ["5 million usd", "percent"]
    assert parsed["events"][0]["steps"][0]["numeric_objects"] == ["1,000 aud"]
    assert parsed["events"][0]["numeric_mentions"][0]["key"] == "5e6|usd"


def test_query_wiki_timeline_aoo_db_rel_path_envelope_uses_python_suffix_policy(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_hca_s942025_aoo.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-30T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "root_actor": {"label": "Root", "surname": "Actor"},
        "events": [],
    }

    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/query_wiki_timeline_aoo_db.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--rel-path",
            "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed["timeline_suffix"] == "wiki_timeline_hca_s942025_aoo.json"
    assert parsed["rel_path"] == "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json"
    assert parsed["payload"]["root_actor"]["label"] == "Root"
