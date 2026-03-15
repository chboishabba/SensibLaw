from __future__ import annotations

import json
from pathlib import Path

from scripts.wiki_timeline_aoo_extract import main as aoo_main


def test_actor_fallback_when_action_has_no_actor(tmp_path: Path) -> None:
    timeline = {
        "events": [
            {
                "event_id": "ev:0001",
                "section": "History",
                "text": "On May 5, 2021, performed surgery on the plaintiff.",
                "anchor": {"year": 2021, "month": 5, "day": 5, "precision": "day", "kind": "explicit"},
                "links": [],
                "links_para": [],
            }
        ],
        "source_timeline": {"path": "dummy", "snapshot": {}},
    }
    timeline_path = tmp_path / "timeline.json"
    out_path = tmp_path / "aoo.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    aoo_main(["--timeline", str(timeline_path), "--out", str(out_path), "--max-events", "8", "--no-db"])
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    assert events, "expected events in output"
    actors = events[0].get("actors") or []
    assert actors, "expected fallback actor to be populated"
    provenances = [a.get("provenance", {}) for a in actors]
    assert any(p.get("actor_fallback") for p in provenances), "expected actor_fallback provenance flag"
