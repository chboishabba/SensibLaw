from __future__ import annotations

import json
from pathlib import Path

from scripts.wiki_candidates_extract import main as candidates_main
from scripts.wiki_timeline_extract import main as timeline_main


def _write_snapshot(tmp_path: Path, *, name: str, categories: list[str]) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "wiki": "enwiki",
                "title": "Category Test Article",
                "pageid": 1,
                "revid": 100,
                "source_url": "https://en.wikipedia.org/wiki/Category_Test_Article",
                "wikitext": "== History ==\nOn March 19, 2003, it happened.",
                "categories": categories,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_timeline_extract_maps_categories_to_events(tmp_path: Path, capsys) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="test_snapshot.json",
        categories=[
            "Category:1980 births",
            "Category:1999 to 2005 deployments",
            "Category:Non-event metadata",
        ],
    )
    out_path = tmp_path / "timeline.json"
    
    exit_code = timeline_main(["--snapshot", str(snapshot_path), "--out", str(out_path)])
    
    assert exit_code == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    
    events = payload.get("events")
    assert isinstance(events, list)
    
    # 1 prose event + 2 category events mapped to anchors
    # "1980 births" maps to DateAnchor 1980
    # "1999 to 2005 deployments" maps to DateAnchor 1999
    # "Non-event metadata" gets dropped (no weak year/anchor)
    assert len(events) == 3
    
    cat_events = [e for e in events if e.get("section") == "(categories)"]
    assert len(cat_events) == 2
    
    anchors = [e["anchor"] for e in cat_events]
    assert any(a["year"] == 1980 for a in anchors)
    assert any(a["year"] == 1999 for a in anchors)
    
    assert all(e.get("lane") == "category" for e in cat_events)


def test_candidates_extract_honors_include_categories(tmp_path: Path, capsys) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="test_snapshot2.json",
        categories=[
            "Category:1980 births",
        ],
    )
    out_path = tmp_path / "candidates.json"
    
    # First verify it correctly excludes without flag
    candidates_main(["--in", str(snapshot_path), "--out", str(out_path)])
    payload_no_cats = json.loads(out_path.read_text(encoding="utf-8"))
    assert not any("1980 births" in r["title"] for r in payload_no_cats.get("rows", []))
    
    # Then verify it includes when flag is passed
    candidates_main(["--in", str(snapshot_path), "--out", str(out_path), "--include-categories"])
    payload_cats = json.loads(out_path.read_text(encoding="utf-8"))
    
    # The title counts in candidate extract should now have the category (if the rank survives)
    assert any("1980 births" in r["title"] or "Category:1980 births" in r["title"] for r in payload_cats.get("rows", []))
