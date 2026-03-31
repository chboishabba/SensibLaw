from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from src.wiki_timeline.fact_timeline_projection import build_fact_timeline_projection
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_build_fact_timeline_projection_synthesizes_and_coalesces_rows() -> None:
    payload = {
        "root_actor": {"label": "Root", "surname": "Actor"},
        "parser": {"name": "demo"},
        "events": [
            {
                "event_id": "ev:1",
                "anchor": {"year": 2001, "month": 1, "day": 2, "precision": "day", "text": "2001-01-02", "kind": "mention"},
                "section": "Section A",
                "text": "Event one",
                "party": "party-a",
                "actors": [],
                "objects": [],
                "steps": [
                    {"action": "said", "subjects": ["Alice"], "objects": ["Budget"], "purpose": "Explain"},
                    {"action": "said", "subjects": ["Alice"], "objects": ["Budget"], "purpose": "Explain"},
                ],
            }
        ],
        "propositions": [
            {
                "proposition_id": "prop:1",
                "event_id": "ev:1",
                "proposition_kind": "assertion",
                "predicate_key": "said",
                "arguments": [{"role": "subject", "value": "Alice"}],
                "receipts": [{"kind": "source", "value": "citation"}],
            }
        ],
        "proposition_links": [
            {
                "link_id": "link:1",
                "event_id": "ev:1",
                "source_proposition_id": "prop:1",
                "target_proposition_id": "prop:1",
                "link_kind": "supports",
                "receipts": [{"kind": "source", "value": "citation"}],
            }
        ],
    }

    result = build_fact_timeline_projection(payload)

    assert result["root_actor"]["label"] == "Root"
    assert result["diagnostics"]["event_count"] == 1
    assert result["diagnostics"]["fact_row_source"] == "synthesized_from_steps"
    assert result["diagnostics"]["raw_fact_rows"] == 2
    assert result["diagnostics"]["output_fact_rows"] == 2
    assert len(result["facts"]) == 2
    assert result["facts"][0]["subjects"] == ["Alice"]
    assert result["facts"][0]["objects"] == ["Budget"]
    assert len(result["propositions"]) == 1
    assert len(result["proposition_links"]) == 1


def test_query_wiki_timeline_aoo_db_fact_timeline_projection(tmp_path: Path) -> None:
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
                "steps": [{"action": "said", "subjects": ["Alice"], "objects": ["Budget"], "purpose": "Explain"}],
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
            "--projection",
            "fact_timeline",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed["root_actor"]["label"] == "Root"
    assert parsed["diagnostics"]["fact_row_source"] == "synthesized_from_steps"
    assert parsed["diagnostics"]["output_fact_rows"] == 1
    assert parsed["facts"][0]["event_id"] == "ev:1"
