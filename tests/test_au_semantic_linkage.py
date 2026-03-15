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
                "text": "In Mabo [No 2], the High Court rejected terra nullius and recognized native title against the Commonwealth of Australia."
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
            {
                "event_id": "ev6",
                "anchor": {"year": 1994, "text": "1994"},
                "section": "State statute",
                "text": "The State of New South Wales enacted the Native Title (New South Wales) Act 1994."
            },
            {
                "event_id": "ev7",
                "anchor": {"year": 2002, "text": "2002"},
                "section": "State liability statute",
                "text": "The State of New South Wales relied on the Civil Liability Act 2002 (NSW) in the liability dispute."
            },
        ],
    }

    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_au_semantic_schema(conn)
        imported = import_au_semantic_seed_payload(conn, payload)
        assert imported["seed_count"] == 7
        stored_refs = conn.execute(
            """
            SELECT seed_id, ref_kind, canonical_ref
            FROM au_semantic_linkage_seed_refs
            ORDER BY seed_id, ref_kind, ref_order
            """
        ).fetchall()
        result = run_au_semantic_linkage(conn)
        assert result["matched_event_count"] >= 3
        report = build_au_semantic_linkage_report(conn, run_id=result["run_id"])

    ref_tuples = {(row["seed_id"], row["ref_kind"], row["canonical_ref"]) for row in stored_refs}
    assert (
        "au_semantic:mabo_native_title",
        "jurisdiction_ref",
        "jurisdiction:commonwealth_of_australia",
    ) in ref_tuples
    assert (
        "au_semantic:mabo_native_title",
        "organization_ref",
        "organization:commonwealth_of_australia",
    ) in ref_tuples
    assert (
        "au_semantic:native_title_nsw_act_lane",
        "jurisdiction_ref",
        "jurisdiction:state_of_new_south_wales",
    ) in ref_tuples
    assert not any(
        row[1] == "institution_ref"
        and row[2] in {"institution:commonwealth_of_australia", "institution:state_of_new_south_wales"}
        for row in ref_tuples
    )

    matched_seed_ids = {row["seed_id"] for row in report["per_seed"] if row["matched_count"] > 0}
    candidate_seed_ids = {row["seed_id"] for row in report["per_seed"] if row["candidate_count"] > 0}
    per_seed = {row["seed_id"]: row for row in report["per_seed"]}
    assert "au_semantic:mabo_native_title" in matched_seed_ids
    assert "au_semantic:plaintiff_s157_judicial_review" in matched_seed_ids
    assert "au_semantic:house_error_of_principle" in matched_seed_ids
    assert "au_semantic:native_title_nsw_act_lane" in matched_seed_ids
    assert "au_semantic:civil_liability_act_lane" in matched_seed_ids
    assert "au_semantic:lepore_non_delegable_duty_lane" in candidate_seed_ids
    assert "au_semantic:introvigne_vicarious_lane" not in matched_seed_ids
    assert {
        (row["ref_kind"], row["canonical_ref"])
        for row in per_seed["au_semantic:mabo_native_title"]["seed_refs"]
    } >= {
        ("court_ref", "court:high_court_of_australia"),
        ("jurisdiction_ref", "jurisdiction:commonwealth_of_australia"),
        ("organization_ref", "organization:commonwealth_of_australia"),
    }
    assert {
        (row["ref_kind"], row["canonical_ref"])
        for row in per_seed["au_semantic:native_title_nsw_act_lane"]["seed_refs"]
    } >= {
        ("jurisdiction_ref", "jurisdiction:state_of_new_south_wales"),
    }
    per_event = {row["event_id"]: row for row in report["per_event"]}
    assert "ev4" not in per_event
    ev1_receipts = {
        (item["reason_kind"], item["reason_value"])
        for item in next(match for match in per_event["ev1"]["matches"] if match["seed_id"] == "au_semantic:mabo_native_title")["receipts"]
    }
    assert ("jurisdiction_ref", "jurisdiction:commonwealth_of_australia") in ev1_receipts
    assert ("organization_ref", "organization:commonwealth_of_australia") in ev1_receipts
    ev6_receipts = {
        (item["reason_kind"], item["reason_value"])
        for item in next(match for match in per_event["ev6"]["matches"] if match["seed_id"] == "au_semantic:native_title_nsw_act_lane")["receipts"]
    }
    assert ("jurisdiction_ref", "jurisdiction:state_of_new_south_wales") in ev6_receipts
    ev7_receipts = {
        (item["reason_kind"], item["reason_value"])
        for item in next(match for match in per_event["ev7"]["matches"] if match["seed_id"] == "au_semantic:civil_liability_act_lane")["receipts"]
    }
    assert ("jurisdiction_ref", "jurisdiction:state_of_new_south_wales") in ev7_receipts
