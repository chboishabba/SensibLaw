from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jsonschema
import yaml

from src.fact_intake import (
    EVENT_ASSEMBLER_VERSION,
    FACT_REVIEW_BUNDLE_VERSION,
    build_fact_intake_payload_from_transcript_report,
    build_transcript_fact_review_bundle,
    persist_fact_intake_payload,
    record_fact_workflow_link,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.structure_report import TextUnit
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


def test_fact_review_bundle_example_validates() -> None:
    schema = yaml.safe_load(Path("schemas/fact.review.bundle.v1.schema.yaml").read_text(encoding="utf-8"))
    payload = json.loads(Path("examples/fact_review_bundle_minimal.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def test_transcript_semantic_report_adapts_into_fact_review_bundle() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "hearing-1", "transcript_file", "Q: Where were you?"),
        TextUnit("u2", "hearing-1", "transcript_file", "A: At home."),
        TextUnit("u3", "hearing-1", "transcript_file", "[5/3/26 8:52 pm] Alice: Thanks."),
    ]
    result = run_transcript_semantic_pipeline(
        conn,
        units,
        known_participants_by_source={"hearing-1": ["counsel", "witness"]},
        run_id="transcript-fact-review-v1",
    )
    semantic_report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
    payload = build_fact_intake_payload_from_transcript_report(semantic_report)

    persist_summary = persist_fact_intake_payload(conn, payload)
    record_fact_workflow_link(
        conn,
        workflow_kind="transcript_semantic",
        workflow_run_id=result["run_id"],
        fact_run_id=payload["run"]["run_id"],
        source_label=payload["run"]["source_label"],
    )
    bundle = build_transcript_fact_review_bundle(conn, fact_run_id=payload["run"]["run_id"], semantic_report=semantic_report)

    schema = yaml.safe_load(Path("schemas/fact.review.bundle.v1.schema.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(bundle, schema)

    assert payload["run"]["run_id"].startswith("factrun:")
    assert payload["run"]["source_label"] == f"transcript_semantic:{result['run_id']}"
    assert persist_summary["source_count"] == 1
    assert persist_summary["statement_count"] == 3
    assert persist_summary["fact_count"] == 3
    assert persist_summary["observation_count"] >= 5
    assert persist_summary["event_count"] >= 1

    observation_predicates = {row["predicate_key"] for row in bundle["observations"]}
    assert {"actor", "communicated", "acted_on"} <= observation_predicates

    communication_event = next(event for event in bundle["events"] if event["event_type"] == "communication")
    assert communication_event["assembler_version"] == EVENT_ASSEMBLER_VERSION
    assert communication_event["status"] == "candidate"
    assert set(communication_event["source_event_ids"]) >= {"u2"}
    assert {row["role"] for row in communication_event["evidence"]} >= {"event_type", "primary_actor", "object_text"}

    chronology_event = next(row for row in bundle["chronology"] if row["event_type"] == "communication")
    assert set(chronology_event["source_event_ids"]) >= {"u2"}
    assert chronology_event["order"] == 1

    assert bundle["version"] == FACT_REVIEW_BUNDLE_VERSION
    assert bundle["run"]["semantic_run_id"] == result["run_id"]
    assert bundle["run"]["workflow_link"]["workflow_kind"] == "transcript_semantic"
    assert bundle["summary"]["source_document_count"] == 1
    assert bundle["summary"]["event_count"] >= 1
    assert len(bundle["review_queue"]) == 3
    assert bundle["review_queue"][0]["reason_codes"]
    assert "primary_contested_reason_text" in bundle["review_queue"][0]
    assert bundle["review_queue"][0]["chronology_bucket"] in {"dated", "undated", "no_event"}
    assert bundle["chronology_groups"]["undated_events"]
    assert "intake_triage" in bundle["operator_views"]
    assert bundle["semantic_context"]["workflow"]["workflow_kind"] == "transcript_semantic"
    assert bundle["abstentions"]["counts"] == {
        "statement_abstentions": 0,
        "observation_abstentions": 0,
        "fact_abstentions": 0,
    }
    assert bundle["semantic_context"]["summary"]["relation_candidate_count"] >= 1
