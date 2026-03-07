from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.au_semantic.linkage import (
    build_au_semantic_linkage_report,
    ensure_au_semantic_schema,
    import_au_semantic_seed_payload,
    run_au_semantic_linkage,
)
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_au_semantic_seed_import_and_matching(tmp_path: Path) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 1992, "text": "1992"},
                "section": "Native title",
                "text": "In Mabo [No 2], the High Court rejected terra nullius and recognized native title against the Crown."
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "In Plaintiff S157/2002 v Commonwealth the High Court challenged the Migration Act privative clause as part of judicial review."
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Criminal appeal",
                "text": "In House v The King the appellant brought an appeal and the matter was heard by the High Court."
            },
            {
                "event_id": "ev4",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Generic court mention",
                "text": "The High Court heard the appeal."
            },
            {
                "event_id": "ev5",
                "anchor": {"year": 2002, "text": "2002"},
                "section": "Duty and liability",
                "text": "The Civil Liability Act 2002 (NSW) and New South Wales v Lepore are discussed for non-delegable duties and vicarious liability."
            },
        ],
    }

    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_au_semantic_schema(conn)
        imported = import_au_semantic_seed_payload(conn, payload)
        assert imported["seed_count"] == 7
        result = run_au_semantic_linkage(conn)
        assert result["matched_event_count"] >= 3
        report = build_au_semantic_linkage_report(conn, run_id=result["run_id"])

    matched_seed_ids = {row["seed_id"] for row in report["per_seed"] if row["matched_count"] > 0}
    candidate_seed_ids = {row["seed_id"] for row in report["per_seed"] if row["candidate_count"] > 0}
    assert "au_semantic:mabo_native_title" in matched_seed_ids
    assert "au_semantic:plaintiff_s157_judicial_review" in matched_seed_ids
    assert "au_semantic:house_error_of_principle" in matched_seed_ids
    assert "au_semantic:lepore_non_delegable_duty_lane" in candidate_seed_ids
    assert "au_semantic:civil_liability_act_lane" in candidate_seed_ids
    per_event = {row["event_id"]: row for row in report["per_event"]}
    assert "ev4" not in per_event
