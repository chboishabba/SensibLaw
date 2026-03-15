from __future__ import annotations

import json
from pathlib import Path

from scripts.wiki_timeline_extract import main as extract_main


def _write_snapshot(tmp_path: Path, *, name: str, title: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "wiki": "enwiki",
                "title": title,
                "pageid": 1,
                "revid": 100,
                "source_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "wikitext": text,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_inline_bare_year_emits_weak_anchor(tmp_path: Path) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="bare_year.json",
        title="Bare Year Example",
        text="He joined the band in 1999 and toured extensively.",
    )
    out_path = tmp_path / "out.json"
    extract_main(["--snapshot", str(snapshot_path), "--out", str(out_path)])
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    anchors = [ev.get("anchor", {}) for ev in payload.get("events", [])]
    assert anchors, "expected at least one anchor"
    weak_years = [a for a in anchors if a.get("kind") == "weak" and a.get("precision") == "year"]
    assert weak_years, "expected weak year anchor from inline bare year"
    assert any(a.get("year") == 1999 for a in weak_years)


def test_section_year_heading_emits_weak_anchor(tmp_path: Path) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="section_year.json",
        title="Section Year Example",
        text="== 2004 ==\nReleased the debut album to critical acclaim.",
    )
    out_path = tmp_path / "out2.json"
    extract_main(["--snapshot", str(snapshot_path), "--out", str(out_path)])
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    anchors = [ev.get("anchor", {}) for ev in payload.get("events", [])]
    assert anchors, "expected anchors from section year heading"
    assert any(a.get("year") == 2004 and a.get("kind") == "weak" for a in anchors)
