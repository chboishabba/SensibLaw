from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.gwb_us_law.linkage import ensure_gwb_us_law_schema, import_gwb_us_law_seed_payload
from src.gwb_us_law.semantic import build_gwb_semantic_report, ensure_gwb_semantic_schema, run_gwb_semantic_pipeline
from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_gwb_semantic_pipeline_promotes_actor_and_relation_rows(tmp_path: Path) -> None:
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
                "anchor": {"year": 2006, "text": "July 19, 2005"},
                "section": "Nominations",
                "text": "On July 19, 2005, Bush nominated John Roberts to the Supreme Court."
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2005, "text": "September 29, 2005"},
                "section": "Confirmations",
                "text": "John Roberts was confirmed by the Senate on September 29, 2005."
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 2006, "text": "October 17, 2006"},
                "section": "Legislation",
                "text": "On October 17, 2006, Bush signed the Military Commissions Act of 2006 into law."
            },
            {
                "event_id": "ev4",
                "anchor": {"year": 2006, "text": "July 19, 2006"},
                "section": "Legislation",
                "text": "On July 19, 2006, Bush vetoed the Stem Cell Research Enhancement Act."
            },
            {
                "event_id": "ev5",
                "anchor": {"year": 2006, "text": "Unknown"},
                "section": "Politics",
                "text": "The administration and the President were under pressure from the court."
            },
            {
                "event_id": "ev6",
                "anchor": {"year": 2008, "text": "July 31, 2008"},
                "section": "Litigation",
                "text": "On July 31, 2008, a United States district court judge ruled that the Military Commissions Act of 2006 was unconstitutional."
            },
        ],
    }
    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_gwb.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        ensure_gwb_us_law_schema(conn)
        ensure_gwb_semantic_schema(conn)
        import_gwb_us_law_seed_payload(conn, payload)
        result = run_gwb_semantic_pipeline(conn)
        report = build_gwb_semantic_report(conn, run_id=result["run_id"])

    promoted = {(row["predicate_key"], row["subject"]["canonical_key"], row["object"]["canonical_key"]) for row in report["promoted_relations"]}
    assert ("nominated", "actor:george_w_bush", "actor:john_roberts") in promoted
    assert ("confirmed_by", "actor:john_roberts", "actor:u_s_senate") in promoted
    assert ("signed", "actor:george_w_bush", "legal_ref:military_commissions_act_of_2006") in promoted
    assert ("vetoed", "actor:george_w_bush", "legal_ref:stem_cell_research_enhancement_act") in promoted
    assert ("ruled_by", "legal_ref:military_commissions_act_of_2006", "actor:united_states_district_court") in promoted

    unresolved_surfaces = {row["surface_text"] for row in report["unresolved_mentions"]}
    assert "the administration" in unresolved_surfaces
    assert "the President" in unresolved_surfaces
    assert "the court" in unresolved_surfaces

    per_entity = {row["entity"]["canonical_key"]: row for row in report["per_entity"]}
    assert per_entity["actor:george_w_bush"]["promoted_relation_count"] >= 3
    assert report["summary"]["candidate_only_relation_count"] >= 0
