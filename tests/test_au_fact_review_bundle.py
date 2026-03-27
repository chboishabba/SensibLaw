from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import jsonschema
import yaml

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline
from src.fact_intake import (
    EVENT_ASSEMBLER_VERSION,
    FACT_REVIEW_BUNDLE_VERSION,
    build_au_fact_review_bundle,
    build_fact_intake_payload_from_au_semantic_report,
    persist_fact_intake_payload,
    persist_authority_ingest_receipt,
    record_fact_workflow_link,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run


def _seed_au_fixture_db(db_path: Path) -> str:
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(db_path.parent / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 1992, "text": "1992"},
                "section": "Native title",
                "text": "In Mabo [No 2], the High Court rejected terra nullius and recognized native title against the Commonwealth of Australia.",
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "In Plaintiff S157/2002 v Commonwealth the High Court challenged the Migration Act privative clause as part of judicial review.",
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Criminal appeal",
                "text": "In House v The King the appellant brought an appeal and the matter was heard by the High Court.",
            },
        ],
    }
    persisted = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=timeline_payload,
        timeline_path=db_path.parent / "wiki_timeline_hca_s942025_aoo.json",
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        import_au_semantic_seed_payload(conn, seed_payload)
    return persisted.run_id


def test_au_semantic_report_adapts_into_fact_review_bundle(tmp_path: Path) -> None:
    db_path = tmp_path / "itir.sqlite"
    timeline_run_id = _seed_au_fixture_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        result = run_au_semantic_pipeline(conn)
        persist_authority_ingest_receipt(
            conn,
            {
                "version": "authority.ingest.v1",
                "authority_kind": "austlii",
                "ingest_mode": "known_authority_fetch",
                "citation": "[1936] HCA 40",
                "selection_reason": "by_citation:[1936] HCA 40",
                "resolved_url": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                "content_type": "text/html",
                "content_length": 120,
                "content_sha256": hashlib.sha256(b"house-v-the-king").hexdigest(),
                "body_preview_text": "House v The King judgment excerpt discussing the High Court appeal.",
                "segments": [
                    {
                        "segment_kind": "paragraph",
                        "paragraph_number": 1,
                        "segment_text": "House v The King concerned an appeal heard by the High Court.",
                    }
                ],
            },
        )
        semantic_report = build_au_semantic_report(conn, run_id=result["run_id"])
        source_payload = load_run_payload_from_normalized(conn, timeline_run_id) or {}
        source_events = source_payload.get("events") if isinstance(source_payload.get("events"), list) else []
        payload = build_fact_intake_payload_from_au_semantic_report(semantic_report, timeline_events=source_events)
        persist_summary = persist_fact_intake_payload(conn, payload)
        record_fact_workflow_link(
            conn,
            workflow_kind="au_semantic",
            workflow_run_id=result["run_id"],
            fact_run_id=payload["run"]["run_id"],
            source_label=payload["run"]["source_label"],
        )
        bundle = build_au_fact_review_bundle(
            conn,
            fact_run_id=payload["run"]["run_id"],
            semantic_report=semantic_report,
            source_events=source_events,
        )

    schema = yaml.safe_load(Path("schemas/fact.review.bundle.v1.schema.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(bundle, schema)

    assert payload["run"]["run_id"].startswith("factrun:")
    assert payload["run"]["source_label"] == f"au_semantic:{result['run_id']}"
    assert persist_summary["statement_count"] == 3
    assert persist_summary["fact_count"] == 3
    assert persist_summary["observation_count"] >= 6
    assert persist_summary["event_count"] >= 2

    observation_predicates = {row["predicate_key"] for row in bundle["observations"]}
    assert {"actor", "performed_action", "acted_on", "event_date"} <= observation_predicates
    assert {"appealed", "challenged", "heard_by"} & observation_predicates

    appeal_like_event = next(
        event for event in bundle["events"] if event["event_type"] in {"appealed", "challenged", "heard by", "decided by", "applied"}
    )
    assert appeal_like_event["assembler_version"] == EVENT_ASSEMBLER_VERSION
    assert appeal_like_event["status"] == "candidate"
    assert appeal_like_event["source_event_ids"]
    assert {row["role"] for row in appeal_like_event["evidence"]} >= {"event_type", "primary_actor"}

    assert bundle["version"] == FACT_REVIEW_BUNDLE_VERSION
    assert bundle["run"]["semantic_run_id"] == result["run_id"]
    assert bundle["run"]["workflow_link"]["workflow_kind"] == "au_semantic"
    assert bundle["summary"]["source_document_count"] == 1
    assert bundle["summary"]["event_count"] >= 2
    assert len(bundle["review_queue"]) == 3
    assert any(row["legal_procedural_predicates"] for row in bundle["review_queue"])
    assert any(row["has_legal_procedural_observations"] for row in bundle["review_queue"])
    assert bundle["chronology_groups"]["dated_events"] or bundle["chronology_groups"]["approximate_events"]
    assert bundle["chronology_summary"]["approximate_event_count"] >= 1
    assert "procedural_posture" in bundle["operator_views"]
    assert "authority_follow" in bundle["operator_views"]
    assert bundle["abstentions"]["counts"]["observation_abstentions"] >= 0
    assert bundle["semantic_context"]["summary"]["relation_candidate_count"] >= 1
    assert "au_linkage" in bundle["semantic_context"]
    assert bundle["semantic_context"]["authority_receipts"]["summary"]["authority_receipt_count"] >= 1
    assert bundle["semantic_context"]["authority_receipts"]["summary"]["linked_receipt_count"] >= 1
    assert bundle["semantic_context"]["authority_receipts"]["items"][0]["structured_summary"]["selected_paragraph_numbers"] == [1]
    assert bundle["operator_views"]["authority_follow"]["available"] is True
    assert bundle["operator_views"]["authority_follow"]["control_plane"]["version"] == "follow.control.v1"
    assert bundle["operator_views"]["authority_follow"]["control_plane"]["source_family"] == "au_authority"
    assert bundle["operator_views"]["authority_follow"]["summary"]["authority_receipt_count"] >= 1
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["route_target_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["resolution_status_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["queue"], list)
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["title"]
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["resolution_status"] == "open"
    assert bundle["semantic_context"]["workflow"]["workflow_kind"] == "au_semantic"
    assert {"appealed", "challenged", "heard_by"} & set(bundle["semantic_context"]["legal_procedural_summary"]["predicates"])
