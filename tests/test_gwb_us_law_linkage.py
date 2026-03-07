from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.gwb_us_law.linkage import (
    build_gwb_us_law_linkage_report,
    ensure_gwb_us_law_schema,
    import_gwb_us_law_seed_payload,
    run_gwb_us_law_linkage,
)
from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_gwb_us_law_seed_import_and_matching(tmp_path: Path) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "gwb_us_law_linkage_seed_v1.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_gwb.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 2002, "text": "2002"},
                "section": "Domestic policy",
                "text": "In 2002, Bush proposed the Clear Skies Act of 2003, which aimed at amending the Clean Air Act."
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2006, "text": "July 19, 2006"},
                "section": "Stem cell research",
                "text": "On July 19, 2006, Bush used his veto power for the first time in his presidency to veto the Stem Cell Research Enhancement Act."
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 2007, "text": "July 6, 2007"},
                "section": "Surveillance",
                "text": "The ruling was vacated by the United States Court of Appeals for the Sixth Circuit on the grounds that the plaintiffs lacked standing in the NSA electronic surveillance program case."
            },
        ],
    }

    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_gwb.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_us_law_schema(conn)
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        imported = import_gwb_us_law_seed_payload(conn, payload)
        assert imported["seed_count"] >= 8
        result = run_gwb_us_law_linkage(conn)
        assert result["matched_event_count"] >= 3
        report = build_gwb_us_law_linkage_report(conn, run_id=result["run_id"])

    matched_seed_ids = {row["seed_id"] for row in report["per_seed"]}
    assert "gwb_us_law:clear_skies_2003" in matched_seed_ids
    assert "gwb_us_law:stem_cell_research_enhancement_act" in matched_seed_ids
    assert "gwb_us_law:nsa_surveillance_review" in matched_seed_ids

    per_event = {row["event_id"]: row for row in report["per_event"]}
    assert any(match["seed_id"] == "gwb_us_law:clear_skies_2003" and match["matched"] for match in per_event["ev1"]["matches"])
    assert any(match["seed_id"] == "gwb_us_law:stem_cell_research_enhancement_act" and match["matched"] for match in per_event["ev2"]["matches"])
    assert any(match["seed_id"] == "gwb_us_law:nsa_surveillance_review" for match in per_event["ev3"]["matches"])
