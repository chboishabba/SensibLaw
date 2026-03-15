from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jsonschema
import yaml

from src.fact_intake import (
    FACT_INTAKE_CONTRACT_VERSION,
    MARY_FACT_WORKFLOW_VERSION,
    build_fact_intake_payload_from_text_units,
    build_fact_intake_report,
    build_mary_fact_workflow_projection,
    persist_fact_intake_payload,
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
    payload["contestations"].append(
        {
            "contestation_id": "contest:1",
            "fact_id": first_fact_id,
            "statement_id": first_statement_id,
            "contestation_status": "disputed",
            "reason_text": "Later note gives a different date.",
            "author": "reviewer@example",
            "provenance": {"source": "manual_review"},
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
    report = build_fact_intake_report(conn, run_id=payload["run"]["run_id"])
    projection = build_mary_fact_workflow_projection(conn, run_id=payload["run"]["run_id"])

    assert persist_summary == {
        "run_id": payload["run"]["run_id"],
        "source_count": 1,
        "excerpt_count": 2,
        "statement_count": 2,
        "fact_count": 2,
        "contestation_count": 1,
        "review_count": 1,
    }
    assert report["summary"]["fact_count"] == 2
    assert report["summary"]["contested_fact_count"] == 1
    assert report["summary"]["reviewed_fact_count"] == 1
    assert [fact["fact_id"] for fact in report["facts"]] == [
        payload["fact_candidates"][0]["fact_id"],
        payload["fact_candidates"][1]["fact_id"],
    ]
    assert report["facts"][0]["source_ids"] == [payload["sources"][0]["source_id"]]
    assert report["facts"][0]["excerpt_ids"] == [payload["excerpts"][0]["excerpt_id"]]
    assert report["facts"][0]["statement_ids"] == [payload["statements"][0]["statement_id"]]
    assert report["facts"][0]["contestations"][0]["contestation_status"] == "disputed"
    assert report["facts"][0]["reviews"][0]["review_status"] == "needs_followup"

    assert projection["version"] == MARY_FACT_WORKFLOW_VERSION
    assert [row["fact_id"] for row in projection["chronology"]] == [
        payload["fact_candidates"][0]["fact_id"],
        payload["fact_candidates"][1]["fact_id"],
    ]
    assert projection["facts"][0]["contested"] is True
    assert projection["facts"][0]["review_statuses"] == ["needs_followup"]
    assert projection["facts"][0]["provenance"]["source_ids"] == [payload["sources"][0]["source_id"]]
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
    review_row_count = conn.execute("SELECT COUNT(*) FROM fact_reviews").fetchone()[0]

    assert fact_row_count == 1
    assert review_row_count == 1
    assert report["facts"][0]["canonical_label"] == "Updated label"
    assert report["facts"][0]["reviews"][0]["review_status"] == "accepted"
