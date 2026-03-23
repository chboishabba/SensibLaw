from __future__ import annotations

import json
from pathlib import Path

from scripts.wiki_timeline_extract import main as timeline_main
from scripts.wiki_candidates_extract import main as candidates_main

def _write_mock_snapshot(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "wiki": "enwiki",
                "title": "Large Scale Import Subject",
                "pageid": 1001,
                "revid": 99999,
                "source_url": "https://en.wikipedia.org/wiki/Subject",
                "wikitext": "== 2021 ==\nOn January 1, 2021, an event occurred.\n== 2022 ==\nIn 2022, another event happened.",
                "categories": [
                    "Category:1990 births",
                    "Category:2021 in spaceflight",
                    "Category:Non-event metadata category"
                ],
                "links": ["SpaceX", "NASA"]
            }
        ),
        encoding="utf-8"
    )
    return path

def test_wiki_timeline_extraction_consistency(tmp_path: Path, capsys) -> None:
    """Verify that multiple runs of timeline extraction yield identical, deterministic results."""
    snapshot_path = tmp_path / "snap.json"
    _write_mock_snapshot(snapshot_path)
    
    out1 = tmp_path / "out1.json"
    out2 = tmp_path / "out2.json"
    
    exit1 = timeline_main(["--snapshot", str(snapshot_path), "--out", str(out1)])
    exit2 = timeline_main(["--snapshot", str(snapshot_path), "--out", str(out2)])
    
    assert exit1 == 0
    assert exit2 == 0
    
    data1 = json.loads(out1.read_text("utf-8"))
    data2 = json.loads(out2.read_text("utf-8"))
    
    # Generated_at will differ, but events should match exactly
    assert data1["events"] == data2["events"]
    assert len(data1["events"]) > 0

def test_category_event_reliability(tmp_path: Path, capsys) -> None:
    """Verify that category-to-event mapping is reliable for high-volume category formats."""
    snapshot_path = tmp_path / "snap.json"
    _write_mock_snapshot(snapshot_path)
    
    out = tmp_path / "out.json"
    exit_code = timeline_main(["--snapshot", str(snapshot_path), "--out", str(out)])
    assert exit_code == 0
    
    data = json.loads(out.read_text("utf-8"))
    events = data["events"]
    
    category_events = [e for e in events if e.get("lane") == "category"]
    
    # 1990 births -> Year 1990
    # 2021 in spaceflight -> Year 2021
    # Non-event metadata category -> No year anchor, dropped
    assert len(category_events) == 2
    
    anchors = [e["anchor"] for e in category_events]
    assert any(a["year"] == 1990 for a in anchors)
    assert any(a["year"] == 2021 for a in anchors)
    
    # Ensure they are distinct from prose events
    assert all(e.get("section") == "(categories)" for e in category_events)

def test_wiki_timeline_statibaker_receipt_integration(tmp_path: Path) -> None:
    """Verify wiki_timeline outputs provide the necessary fields for StatiBaker receipt ingestion."""
    snapshot_path = tmp_path / "snap.json"
    _write_mock_snapshot(snapshot_path)
    
    out = tmp_path / "timeline.json"
    timeline_main(["--snapshot", str(snapshot_path), "--out", str(out)])
    
    data = json.loads(out.read_text("utf-8"))
    
    # StatiBaker expects structured provenance and bounded events
    assert "snapshot" in data
    assert data["snapshot"]["wiki"] == "enwiki"
    assert data["snapshot"]["revid"] == 99999
    
    # Ensure each event contains anchors which are crucial for StatiBaker timeline overlays
    for event in data["events"]:
        assert "anchor" in event
        assert "year" in event["anchor"]
        assert "event_id" in event
        assert "text" in event
