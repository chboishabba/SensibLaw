from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jsonschema
import pytest
import yaml

from src.fact_intake import (
    EVENT_ASSEMBLER_VERSION,
    FACT_INTAKE_CONTRACT_VERSION,
    FACT_REVIEW_ZELPH_RULESET_VERSION,
    MARY_FACT_WORKFLOW_VERSION,
    OBSERVATION_PREDICATE_TO_FAMILY,
    build_fact_review_acceptance_report,
    build_fact_review_operator_views,
    build_fact_intake_payload_from_text_units,
    build_fact_intake_report,
    build_fact_review_run_summary,
    build_fact_review_workbench_payload,
    build_mary_fact_workflow_projection,
    persist_fact_intake_payload,
    find_latest_fact_workflow_link,
    list_fact_review_sources,
    record_fact_workflow_link,
    resolve_fact_run_id,
    resolve_fact_run_link,
)
from src.reporting.structure_report import TextUnit


def test_fact_intake_example_validates() -> None:
    schema = yaml.safe_load(Path("schemas/fact.intake.bundle.v1.schema.yaml").read_text(encoding="utf-8"))
    payload = json.loads(Path("examples/fact_intake_bundle_minimal.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def test_build_fact_intake_payload_from_text_units_is_deterministic() -> None:
    units = [
        TextUnit(
            unit_id="unit:1",
            source_id="source-a",
            source_type="chat_test_db",
            text="On 2024-01-02 Mary says the treatment timeline is incomplete.",
        ),
        TextUnit(
            unit_id="unit:2",
            source_id="source-a",
            source_type="chat_test_db",
            text="On 2024-01-03 the clinic note disputes that timeline.",
        ),
    ]

    payload_a = build_fact_intake_payload_from_text_units(units, source_label="mary_parity_demo", notes="demo")
    payload_b = build_fact_intake_payload_from_text_units(units, source_label="mary_parity_demo", notes="demo")

    assert payload_a == payload_b
    assert payload_a["run"]["contract_version"] == FACT_INTAKE_CONTRACT_VERSION
    assert payload_a["run"]["mary_projection_version"] == MARY_FACT_WORKFLOW_VERSION
    assert len(payload_a["sources"]) == 1
    assert len(payload_a["excerpts"]) == 2
    assert len(payload_a["statements"]) == 2
    assert payload_a["observations"] == []
    assert len(payload_a["fact_candidates"]) == 2
    assert payload_a["sources"][0]["source_type"] == "chat_test_db"


def test_persist_report_and_mary_projection_support_provenance_and_review_queue() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:1",
            source_id="mary-source",
            source_type="context_file",
            text="The injury occurred on 2024-01-01.",
        ),
        TextUnit(
            unit_id="unit:2",
            source_id="mary-source",
            source_type="context_file",
            text="A later note says the injury may have occurred on 2024-01-02.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="mary_parity_demo")
    first_fact_id = payload["fact_candidates"][0]["fact_id"]
    first_statement_id = payload["statements"][0]["statement_id"]
    payload["fact_candidates"][0]["canonical_label"] = "Initial injury date"
    payload["fact_candidates"][0]["chronology_sort_key"] = "2024-01-01"
    payload["fact_candidates"][0]["chronology_label"] = "2024-01-01"
    payload["fact_candidates"][0]["candidate_status"] = "candidate"
    payload["fact_candidates"][1]["canonical_label"] = "Disputed later injury date"
    payload["fact_candidates"][1]["chronology_sort_key"] = "2024-01-02"
    payload["fact_candidates"][1]["chronology_label"] = "2024-01-02"
    payload["fact_candidates"][1]["candidate_status"] = "candidate"
    payload["observations"].extend(
        [
            {
                "observation_id": "obs:actor:1",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 1,
                "predicate_key": "actor",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["actor"],
                "object_text": "Dr Smith",
                "object_type": "person",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
            {
                "observation_id": "obs:action:1",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 2,
                "predicate_key": "performed_action",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["performed_action"],
                "object_text": "surgery",
                "object_type": "action",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
            {
                "observation_id": "obs:object:1",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 3,
                "predicate_key": "acted_on",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["acted_on"],
                "object_text": "plaintiff",
                "object_type": "person",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
            {
                "observation_id": "obs:1",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 4,
                "predicate_key": "event_date",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["event_date"],
                "object_text": "2024-01-01",
                "object_type": "date",
                "object_ref": None,
                "subject_text": "injury",
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
            {
                "observation_id": "obs:2",
                "statement_id": payload["statements"][1]["statement_id"],
                "excerpt_id": payload["excerpts"][1]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 1,
                "predicate_key": "claimed",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["claimed"],
                "object_text": "injury occurred on 2024-01-02",
                "object_type": "fact_statement",
                "object_ref": None,
                "subject_text": "later note",
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
        ]
    )
    payload["contestations"].append(
        {
            "contestation_id": "contest:1",
            "fact_id": first_fact_id,
            "statement_id": first_statement_id,
            "contestation_status": "disputed",
            "reason_text": "Later note gives a different date.",
            "author": "reviewer@example",
            "provenance": {"source": "manual_review", "contestation_scope": "chronology"},
        }
    )
    payload["reviews"].append(
        {
            "review_id": "review:1",
            "fact_id": first_fact_id,
            "review_status": "needs_followup",
            "reviewer": "reviewer@example",
            "note": "Check primary clinical source.",
            "provenance": {"source": "manual_review"},
        }
    )

    persist_summary = persist_fact_intake_payload(conn, payload)
    workflow_link = record_fact_workflow_link(
        conn,
        workflow_kind="transcript_semantic",
        workflow_run_id="semantic:test:1",
        fact_run_id=payload["run"]["run_id"],
        source_label=payload["run"]["source_label"],
    )
    report = build_fact_intake_report(conn, run_id=payload["run"]["run_id"])
    projection = build_mary_fact_workflow_projection(conn, run_id=payload["run"]["run_id"])
    review_summary = build_fact_review_run_summary(conn, run_id=payload["run"]["run_id"])
    operator_views = build_fact_review_operator_views(conn, run_id=payload["run"]["run_id"])
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    acceptance = build_fact_review_acceptance_report(workbench, fixture_kind="synthetic")

    assert persist_summary == {
        "run_id": payload["run"]["run_id"],
        "source_count": 1,
        "excerpt_count": 2,
        "statement_count": 2,
        "observation_count": 5,
        "fact_count": 2,
        "contestation_count": 1,
        "review_count": 1,
        "event_count": 1,
        "event_attribute_count": 1,
        "event_evidence_count": 5,
    }
    assert report["summary"]["observation_count"] == 5
    assert report["summary"]["event_count"] == 1
    assert report["summary"]["fact_count"] == 2
    assert report["summary"]["contested_fact_count"] == 1
    assert report["summary"]["reviewed_fact_count"] == 1
    assert report["run"]["workflow_link"] == workflow_link
    assert {row["predicate_key"] for row in report["observations"]} == {
        "actor",
        "performed_action",
        "acted_on",
        "event_date",
        "claimed",
    }
    assert report["events"][0]["event_type"] == "surgery"
    assert report["events"][0]["primary_actor"] == "Dr Smith"
    assert report["events"][0]["object_text"] == "plaintiff"
    assert report["events"][0]["time_start"] == "2024-01-01"
    assert report["events"][0]["status"] == "candidate"
    assert report["events"][0]["assembler_version"] == EVENT_ASSEMBLER_VERSION
    assert report["events"][0]["attributes"][0]["attribute_type"] == "claimed"
    assert {row["role"] for row in report["events"][0]["evidence"]} >= {
        "event_type",
        "primary_actor",
        "object_text",
        "time_start",
        "attribute",
    }
    assert [fact["fact_id"] for fact in report["facts"]] == [
        payload["fact_candidates"][0]["fact_id"],
        payload["fact_candidates"][1]["fact_id"],
    ]
    assert report["facts"][0]["source_ids"] == [payload["sources"][0]["source_id"]]
    assert report["facts"][0]["excerpt_ids"] == [payload["excerpts"][0]["excerpt_id"]]
    assert report["facts"][0]["statement_ids"] == [payload["statements"][0]["statement_id"]]
    assert report["facts"][0]["event_ids"] == [report["events"][0]["event_id"]]
    assert {row["predicate_key"] for row in report["facts"][0]["observations"]} == {
        "actor",
        "performed_action",
        "acted_on",
        "event_date",
    }
    assert report["facts"][0]["contestations"][0]["contestation_status"] == "disputed"
    assert report["facts"][0]["reviews"][0]["review_status"] == "needs_followup"

    assert projection["version"] == MARY_FACT_WORKFLOW_VERSION
    assert projection["events"][0]["event_type"] == "surgery"
    assert projection["events"][0]["primary_actor"] == "Dr Smith"
    assert projection["events"][0]["time_start"] == "2024-01-01"
    assert [row["fact_id"] for row in projection["chronology"]] == [
        payload["fact_candidates"][0]["fact_id"],
        payload["fact_candidates"][1]["fact_id"],
    ]
    assert projection["facts"][0]["contested"] is True
    assert projection["facts"][0]["review_statuses"] == ["needs_followup"]
    assert set(projection["facts"][0]["observation_predicates"]) == {
        "actor",
        "performed_action",
        "acted_on",
        "event_date",
    }
    assert projection["facts"][0]["provenance"]["source_ids"] == [payload["sources"][0]["source_id"]]
    assert projection["facts"][0]["event_ids"] == [report["events"][0]["event_id"]]
    assert projection["review_queue"] == [
        {
            "fact_id": payload["fact_candidates"][0]["fact_id"],
            "label": "Initial injury date",
            "needs_review": True,
            "contestation_count": 1,
        },
        {
            "fact_id": payload["fact_candidates"][1]["fact_id"],
            "label": "Disputed later injury date",
            "needs_review": True,
            "contestation_count": 0,
        },
    ]
    assert review_summary["summary"]["review_queue_count"] == 2
    assert review_summary["summary"]["needs_followup_count"] == 1
    assert review_summary["summary"]["chronology_impacted_review_queue_count"] == 2
    assert review_summary["summary"]["legal_procedural_review_queue_count"] == 1
    assert review_summary["summary"]["missing_actor_review_queue_count"] == 1
    assert review_summary["summary"]["contradictory_chronology_review_queue_count"] == 1
    assert review_summary["summary"]["contested_item_count"] == 1
    assert review_summary["summary"]["no_event_fact_count"] == 0
    assert review_summary["summary"]["contested_chronology_item_count"] == 1
    assert review_summary["review_queue"][0]["primary_contested_reason_text"] == "Later note gives a different date."
    assert review_summary["review_queue"][0]["latest_review_status"] == "needs_followup"
    assert review_summary["review_queue"][0]["latest_review_note"] == "Check primary clinical source."
    assert review_summary["review_queue"][0]["chronology_impacted"] is True
    assert review_summary["review_queue"][0]["has_legal_procedural_observations"] is False
    assert review_summary["review_queue"][0]["reason_codes"] == ["contested", "review_followup", "contradictory_chronology"]
    assert review_summary["review_queue"][0]["chronology_bucket"] == "dated"
    assert review_summary["review_queue"][0]["event_ids"] == [report["events"][0]["event_id"]]
    assert review_summary["review_queue"][0]["observation_families"] == [
        "actions_events",
        "actor_identification",
        "object_target",
        "temporal",
    ]
    assert review_summary["review_queue"][0]["legal_procedural_predicates"] == []
    assert review_summary["review_queue"][1]["primary_contested_reason_text"] is None
    assert review_summary["review_queue"][1]["latest_review_status"] is None
    assert review_summary["review_queue"][1]["latest_review_note"] is None
    assert review_summary["review_queue"][1]["chronology_impacted"] is True
    assert review_summary["review_queue"][1]["reason_codes"] == ["unreviewed", "missing_actor", "procedural_significance"]
    assert review_summary["review_queue"][1]["chronology_bucket"] == "dated"
    assert review_summary["contested_summary"]["needs_followup_count"] == 1
    assert review_summary["contested_summary"]["reviewed_count"] == 1
    assert review_summary["contested_summary"]["chronology_impacted_count"] == 1
    assert review_summary["chronology_groups"]["dated_events"]
    assert review_summary["chronology_groups"]["undated_events"] == []
    assert review_summary["chronology_groups"]["facts_with_no_event"] == []
    assert review_summary["chronology_groups"]["contested_chronology_items"]
    assert operator_views["intake_triage"]["items"][0]["fact_id"] == payload["fact_candidates"][0]["fact_id"]
    assert operator_views["procedural_posture"]["items"][0]["fact_id"] == payload["fact_candidates"][1]["fact_id"]
    assert workbench["inspector_defaults"]["selected_fact_id"] == payload["fact_candidates"][0]["fact_id"]
    assert workbench["operator_views"]["contested_items"]["summary"]["count"] == 1
    assert workbench["zelph_ruleset_version"] == FACT_REVIEW_ZELPH_RULESET_VERSION
    assert workbench["zelph"]["version"] == "fact_intake.zelph_bridge.v1"
    assert workbench["zelph"]["rule_status"] in {"engine_ok", "engine_unavailable", "engine_error"}
    assert workbench["facts"][0]["inferred_signal_classes"] == []
    assert workbench["review_queue"][0]["inferred_signal_classes"] == []
    assert acceptance["fixture_kind"] == "synthetic"
    assert acceptance["summary"]["story_count"] >= 1
    assert list_fact_review_sources(conn, workflow_kind="transcript_semantic")[0]["latest_workflow_link"]["fact_run_id"] == payload["run"]["run_id"]
    assert resolve_fact_run_link(conn, workflow_kind="transcript_semantic", workflow_run_id="semantic:test:1")["fact_run_id"] == payload["run"]["run_id"]
    assert resolve_fact_run_id(conn, workflow_kind="transcript_semantic", workflow_run_id="semantic:test:1") == payload["run"]["run_id"]
    assert find_latest_fact_workflow_link(conn, workflow_kind="transcript_semantic")["fact_run_id"] == payload["run"]["run_id"]


def test_persist_fact_intake_payload_replaces_existing_run_rows() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:1",
            source_id="source-a",
            source_type="context_file",
            text="Initial source text.",
        )
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="replace_demo")
    persist_fact_intake_payload(conn, payload)

    payload["fact_candidates"][0]["canonical_label"] = "Updated label"
    payload["observations"].append(
        {
            "observation_id": "obs:replace",
            "statement_id": payload["statements"][0]["statement_id"],
            "excerpt_id": payload["excerpts"][0]["excerpt_id"],
            "source_id": payload["sources"][0]["source_id"],
            "observation_order": 1,
            "predicate_key": "claimed",
            "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["claimed"],
            "object_text": "Initial source text.",
            "object_type": "fact_statement",
            "object_ref": None,
            "subject_text": None,
            "observation_status": "captured",
            "provenance": {"source": "manual_review"},
        }
    )
    payload["observations"].extend(
        [
            {
                "observation_id": "obs:replace:actor",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 2,
                "predicate_key": "actor",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["actor"],
                "object_text": "Reporter",
                "object_type": "person",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_review"},
            },
            {
                "observation_id": "obs:replace:action",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 3,
                "predicate_key": "communicated",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["communicated"],
                "object_text": "reported",
                "object_type": "action",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_review"},
            },
        ]
    )
    payload["reviews"].append(
        {
            "review_id": "review:replace",
            "fact_id": payload["fact_candidates"][0]["fact_id"],
            "review_status": "accepted",
            "reviewer": "reviewer@example",
            "note": None,
            "provenance": {"source": "manual_review"},
        }
    )
    persist_fact_intake_payload(conn, payload)

    report = build_fact_intake_report(conn, run_id=payload["run"]["run_id"])
    fact_row_count = conn.execute("SELECT COUNT(*) FROM fact_candidates").fetchone()[0]
    observation_row_count = conn.execute("SELECT COUNT(*) FROM fact_observations").fetchone()[0]
    event_row_count = conn.execute("SELECT COUNT(*) FROM event_candidates").fetchone()[0]
    review_row_count = conn.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0]

    assert fact_row_count == 1
    assert observation_row_count == 3
    assert event_row_count == 1
    assert review_row_count == 1
    assert report["facts"][0]["canonical_label"] == "Updated label"
    assert {row["predicate_key"] for row in report["facts"][0]["observations"]} == {
        "claimed",
        "actor",
        "communicated",
    }
    assert report["facts"][0]["reviews"][0]["review_status"] == "accepted"
    assert report["events"][0]["event_type"] == "reported"


def test_workbench_payload_applies_canonical_zelph_enrichment() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:wiki",
            source_id="wiki-source",
            source_type="wiki_article",
            text="Revision by BD2412: Reverted unsourced change.",
        ),
        TextUnit(
            unit_id="unit:legal",
            source_id="legal-source",
            source_type="legal_record",
            text="Formal order confirms the governing legal position.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_demo")
    payload["sources"][0]["provenance"] = {"source_signal_classes": ["wiki_article", "revision_history"]}
    payload["sources"][1]["provenance"] = {"source_signal_classes": ["legal_record", "strong_legal_source"]}
    payload["fact_candidates"][0]["canonical_label"] = "Wiki revision"
    payload["fact_candidates"][1]["canonical_label"] = "Legal position"
    persist_fact_intake_payload(conn, payload)

    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    wiki_fact = next(row for row in workbench["facts"] if row["fact_id"] == payload["fact_candidates"][0]["fact_id"])
    legal_fact = next(row for row in workbench["facts"] if row["fact_id"] == payload["fact_candidates"][1]["fact_id"])

    assert "public_summary" in wiki_fact["source_signal_classes"]
    assert "volatility_signal" in wiki_fact["signal_classes"]
    assert "volatility_signal" in wiki_fact["inferred_signal_classes"]
    assert "public_summary" in wiki_fact["inferred_source_signal_classes"]
    assert "public_knowledge_not_authority" not in wiki_fact["signal_classes"]
    assert legal_fact["inferred_signal_classes"] == []
    assert workbench["zelph"]["inferred_fact_count"] == 1


def test_persist_fact_intake_payload_rejects_unsupported_status_values() -> None:
    conn = sqlite3.connect(":memory:")
    payload = build_fact_intake_payload_from_text_units(
        [
            TextUnit(
                unit_id="unit:1",
                source_id="source-a",
                source_type="context_file",
                text="Invalid status example.",
            )
        ],
        source_label="status_demo",
    )
    payload["observations"].append(
        {
            "observation_id": "obs:bad",
            "statement_id": payload["statements"][0]["statement_id"],
            "excerpt_id": payload["excerpts"][0]["excerpt_id"],
            "source_id": payload["sources"][0]["source_id"],
            "observation_order": 1,
            "predicate_key": "claimed",
            "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["claimed"],
            "object_text": "Invalid status example.",
            "object_type": "fact_statement",
            "object_ref": None,
            "subject_text": None,
            "observation_status": "mystery_status",
            "provenance": {"source": "manual_review"},
        }
    )

    with pytest.raises(ValueError, match="unsupported observation_status"):
        persist_fact_intake_payload(conn, payload)


def test_abstained_observation_is_preserved_but_not_used_for_event_assembly() -> None:
    conn = sqlite3.connect(":memory:")
    payload = build_fact_intake_payload_from_text_units(
        [
            TextUnit(
                unit_id="unit:1",
                source_id="source-a",
                source_type="context_file",
                text="The record may describe surgery but the extractor abstained.",
            )
        ],
        source_label="abstain_demo",
    )
    payload["observations"].extend(
        [
            {
                "observation_id": "obs:actor",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 1,
                "predicate_key": "actor",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["actor"],
                "object_text": "Dr Smith",
                "object_type": "person",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "captured",
                "provenance": {"source": "manual_annotation"},
            },
            {
                "observation_id": "obs:abstained_action",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 2,
                "predicate_key": "performed_action",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["performed_action"],
                "object_text": "surgery",
                "object_type": "action",
                "object_ref": None,
                "subject_text": None,
                "observation_status": "abstained",
                "provenance": {"source": "extractor"},
            },
        ]
    )

    summary = persist_fact_intake_payload(conn, payload)
    report = build_fact_intake_report(conn, run_id=payload["run"]["run_id"])

    assert summary["observation_count"] == 2
    assert summary["event_count"] == 0
    assert report["summary"]["event_count"] == 0
    assert {row["observation_status"] for row in report["observations"]} == {"captured", "abstained"}
