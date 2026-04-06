from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.query_fact_review import main
from scripts.build_affidavit_coverage_review import write_affidavit_coverage_review
from src.fact_intake import (
    OBSERVATION_PREDICATE_TO_FAMILY,
    AUTHORITY_INGEST_VERSION,
    FEEDBACK_RECEIPT_VERSION,
    build_fact_intake_payload_from_text_units,
    persist_fact_intake_payload,
    persist_authority_ingest_receipt,
    persist_feedback_receipt,
    record_fact_workflow_link,
)
from src.fact_intake.acceptance import STORY_WAVES
from src.reporting.structure_report import TextUnit


def _seed_fact_review_run(db_path) -> str:
    conn = sqlite3.connect(str(db_path))
    units = [
        TextUnit("unit:1", "source-a", "context_file", "The injury occurred on 2024-01-01."),
        TextUnit("unit:2", "source-a", "context_file", "A later note disputes that timeline."),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="query_fact_review_demo")
    first_fact_id = payload["fact_candidates"][0]["fact_id"]
    first_statement_id = payload["statements"][0]["statement_id"]
    payload["fact_candidates"][0]["canonical_label"] = "Initial injury date"
    payload["fact_candidates"][0]["chronology_sort_key"] = "2024-01-01"
    payload["fact_candidates"][0]["chronology_label"] = "2024-01-01"
    payload["fact_candidates"][0]["candidate_status"] = "candidate"
    payload["fact_candidates"][1]["canonical_label"] = "Later note dispute"
    payload["fact_candidates"][1]["candidate_status"] = "candidate"
    payload["observations"].extend(
        [
            {
                "observation_id": "obs:q1",
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
                "provenance": {"source": "pytest"},
            },
            {
                "observation_id": "obs:q2",
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
                "provenance": {"source": "pytest"},
            },
            {
                "observation_id": "obs:q3",
                "statement_id": payload["statements"][0]["statement_id"],
                "excerpt_id": payload["excerpts"][0]["excerpt_id"],
                "source_id": payload["sources"][0]["source_id"],
                "observation_order": 3,
                "predicate_key": "event_date",
                "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY["event_date"],
                "object_text": "2024-01-01",
                "object_type": "date",
                "object_ref": None,
                "subject_text": "injury",
                "observation_status": "captured",
                "provenance": {"source": "pytest"},
            },
        ]
    )
    payload["contestations"].append(
        {
            "contestation_id": "contest:q1",
            "fact_id": first_fact_id,
            "statement_id": first_statement_id,
            "contestation_status": "disputed",
            "reason_text": "Later note gives a different date.",
            "author": "reviewer@example",
            "provenance": {"source": "pytest"},
        }
    )
    payload["reviews"].append(
        {
            "review_id": "review:q1",
            "fact_id": first_fact_id,
            "review_status": "needs_followup",
            "reviewer": "reviewer@example",
            "note": "Check primary clinical source.",
            "provenance": {"source": "pytest"},
        }
    )
    persist_fact_intake_payload(conn, payload)
    record_fact_workflow_link(
        conn,
        workflow_kind="transcript_semantic",
        workflow_run_id="semantic:query-demo",
        fact_run_id=payload["run"]["run_id"],
        source_label=payload["run"]["source_label"],
    )
    conn.close()
    return payload["run"]["run_id"]


def _seed_authority_ingest_run(db_path) -> str:
    conn = sqlite3.connect(str(db_path))
    receipt = persist_authority_ingest_receipt(
        conn,
        {
            "version": AUTHORITY_INGEST_VERSION,
            "authority_kind": "jade",
            "ingest_mode": "fetch",
            "citation": "[2021] FamCA 83",
            "selection_reason": "explicit_citation",
            "resolved_url": "https://jade.example/content/ext/mnc/2021/famca/83",
            "content_type": "text/plain",
            "content_length": 1234,
            "content_sha256": "abc123",
            "paragraph_request": [120],
            "paragraph_window": 1,
            "body_preview_text": "Paragraph 119 ... Paragraph 120 ... Paragraph 121 ...",
            "fetch_metadata": {"source": "pytest"},
            "segments": [
                {"segment_kind": "paragraph", "paragraph_number": 119, "segment_text": "Paragraph 119"},
                {"segment_kind": "paragraph", "paragraph_number": 120, "segment_text": "Paragraph 120"},
                {"segment_kind": "paragraph", "paragraph_number": 121, "segment_text": "Paragraph 121"},
            ],
        },
    )
    conn.close()
    return receipt["ingest_run_id"]


def _seed_feedback_receipt(db_path) -> str:
    conn = sqlite3.connect(str(db_path))
    receipt = persist_feedback_receipt(
        conn,
        {
            "schema_version": FEEDBACK_RECEIPT_VERSION,
            "feedback_class": "suite_frustration",
            "role_label": "lawyer",
            "task_label": "browse_corpus",
            "target_product": "itir-svelte",
            "target_surface": "/corpora/processed/personal",
            "workflow_label": "personal_results_review",
            "source_kind": "interview",
            "summary": "The user could see results but not the next action.",
            "quote_text": "I can see the results, but I still don't know what I'm supposed to do next.",
            "severity": "high",
            "desired_outcome": "One obvious next step from the results page.",
            "sentiment": "negative",
            "captured_at": "2026-03-27T14:00:00Z",
            "tags": ["navigation", "workflow", "ui"],
            "provenance": {"collector": "pytest", "source_ref": "feedback:1"},
        },
    )
    conn.close()
    return receipt["receipt_id"]


def test_query_fact_review_script_lists_runs_and_summaries(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(["--db-path", str(db_path), "runs", "--limit", "5"])
    runs_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert runs_payload["runs"][0]["run_id"] == run_id
    assert runs_payload["runs"][0]["contestation_count"] == 1
    assert runs_payload["runs"][0]["workflow_link"]["workflow_kind"] == "transcript_semantic"

    exit_code = main(["--db-path", str(db_path), "summary", "--run-id", run_id])
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["summary"]["summary"]["review_queue_count"] >= 1
    assert summary_payload["summary"]["summary"]["needs_followup_count"] == 1
    assert summary_payload["summary"]["contested_summary"]["count"] == 1
    assert summary_payload["summary"]["chronology_summary"]["fact_count"] == 2
    assert summary_payload["summary"]["summary"]["missing_actor_review_queue_count"] >= 1


def test_query_fact_review_script_reports_review_queue_and_chronology(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(["--db-path", str(db_path), "review-queue", "--run-id", run_id])
    review_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert review_payload["contested_summary"]["count"] == 1
    assert review_payload["review_queue"][0]["reason_codes"]
    assert review_payload["review_queue"][0]["status_explanation"]["status_scope"] == "review"
    assert review_payload["review_queue"][0]["status_explanation"]["why"]

    exit_code = main(["--db-path", str(db_path), "chronology", "--run-id", run_id])
    chronology_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert chronology_payload["chronology_summary"]["event_count"] >= 1
    assert chronology_payload["chronology"]["facts"]
    assert chronology_payload["chronology_groups"]["dated_events"]
    assert "contested_chronology_items" in chronology_payload["chronology_groups"]

    exit_code = main(["--db-path", str(db_path), "view", "--run-id", run_id, "--view-kind", "intake_triage"])
    view_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert view_payload["view_kind"] == "intake_triage"
    assert view_payload["view"]["summary"]["review_queue_count"] >= 1
    assert view_payload["view"]["queue"][0]["description"]
    assert view_payload["view"]["queue"][0]["operator_readout"]["reason_line"] == view_payload["view"]["queue"][0]["description"]

    exit_code = main(["--db-path", str(db_path), "workbench", "--run-id", run_id])
    workbench_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert workbench_payload["workbench"]["operator_views"]["chronology_prep"]["groups"]["dated_events"]
    assert "contradictory_chronology" in workbench_payload["workbench"]["operator_views"]["intake_triage"]["groups"]
    assert workbench_payload["workbench"]["operator_views"]["intake_triage"]["control_plane"]["version"] == "follow.control.v1"
    assert isinstance(workbench_payload["workbench"]["operator_views"]["intake_triage"]["queue"], list)
    assert workbench_payload["workbench"]["operator_views"]["intake_triage"]["queue"][0]["operator_readout"]["headline"] == workbench_payload["workbench"]["operator_views"]["intake_triage"]["queue"][0]["title"]
    assert workbench_payload["workbench"]["operator_views"]["contested_items"]["queue"][0]["operator_readout"]["headline"] == workbench_payload["workbench"]["operator_views"]["contested_items"]["queue"][0]["title"]
    assert workbench_payload["workbench"]["operator_views"]["contested_items"]["control_plane"]["source_family"] == "fact_review"
    assert workbench_payload["workbench"]["reopen_navigation"]["query"]["workflow_kind"] == "transcript_semantic"
    assert "missing_actor" in workbench_payload["workbench"]["issue_filters"]["available_filters"]
    first_fact_id = workbench_payload["workbench"]["facts"][0]["fact_id"]
    assert workbench_payload["workbench"]["inspector_classification"]["facts"][first_fact_id]["status_keys"]
    assert "approximate_events" in workbench_payload["workbench"]["chronology_groups"]
    assert isinstance(workbench_payload["workbench"]["semantic_context"], dict)
    assert workbench_payload["workbench"]["workflow_summary"]["recommended_view"] in {
        "intake_triage",
        "chronology_prep",
        "contested_items",
        "authority_follow",
        "professional_handoff",
    }
    assert "signal_classes" in workbench_payload["workbench"]["facts"][0]
    assert "inspector_classification" in workbench_payload["workbench"]["facts"][0]

    exit_code = main(["--db-path", str(db_path), "acceptance", "--run-id", run_id, "--fixture-kind", "synthetic"])
    acceptance_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert acceptance_payload["acceptance"]["summary"]["story_count"] >= 1
    assert acceptance_payload["acceptance"]["fixture_kind"] == "synthetic"
    assert "failed_check_ids" in acceptance_payload["acceptance"]["stories"][0]

    exit_code = main(["--db-path", str(db_path), "semantic-status", "--run-id", run_id])
    semantic_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert semantic_payload["semantic_status"]["materialized"] is True
    assert semantic_payload["semantic_status"]["latest_refresh"]["refresh_status"] == "ok"

    exit_code = main(["--db-path", str(db_path), "semantic-refreshes", "--run-id", run_id, "--limit", "5"])
    refresh_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert refresh_payload["refreshes"][0]["run_id"] == run_id
    assert refresh_payload["refreshes"][0]["current_stage"] == "finalize"

    exit_code = main(["--db-path", str(db_path), "feedback", "--run-id", run_id])
    feedback_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert feedback_payload["feedback"]["summary"]["constrained_fact_count"] >= 1
    assert any("review" in msg.casefold() for msg in feedback_payload["feedback"]["global_messages"])


def test_query_fact_review_script_reports_authority_ingest_runs(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    ingest_run_id = _seed_authority_ingest_run(db_path)

    exit_code = main(["--db-path", str(db_path), "authority-runs", "--limit", "5"])
    runs_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert runs_payload["runs"][0]["ingest_run_id"] == ingest_run_id
    assert runs_payload["runs"][0]["authority_kind"] == "jade"
    assert runs_payload["runs"][0]["segment_count"] == 3

    exit_code = main(["--db-path", str(db_path), "authority-summary", "--ingest-run-id", ingest_run_id])
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["summary"]["run"]["resolved_url"].endswith("/83")
    assert [row["paragraph_number"] for row in summary_payload["summary"]["segments"]] == [119, 120, 121]


def test_query_fact_review_script_reports_feedback_receipts(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    receipt_id = _seed_feedback_receipt(db_path)

    exit_code = main(["--db-path", str(db_path), "feedback-receipts", "--limit", "5"])
    receipts_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipts_payload["receipts"][0]["receipt_id"] == receipt_id
    assert receipts_payload["receipts"][0]["feedback_class"] == "suite_frustration"
    assert receipts_payload["receipts"][0]["role_label"] == "lawyer"
    assert receipts_payload["receipts"][0]["provenance"]["source_ref"] == "feedback:1"

    exit_code = main(["--db-path", str(db_path), "feedback-summary", "--receipt-id", receipt_id])
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["summary"]["receipt"]["target_product"] == "itir-svelte"
    assert summary_payload["summary"]["receipt"]["source_kind"] == "interview"
    assert "don't know what I'm supposed to do next" in summary_payload["summary"]["receipt"]["quote_text"]


def test_query_fact_review_script_adds_feedback_receipt(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "feedback-add",
            "--feedback-class",
            "competitor_frustration",
            "--role-label",
            "lawyer",
            "--task-label",
            "prepare_case",
            "--source-kind",
            "interview",
            "--summary",
            "The user cannot trace where the answer came from.",
            "--quote-text",
            "It gives me an answer, but I cannot see where it came from.",
            "--severity",
            "high",
            "--target-product",
            "competitor-x",
            "--target-surface",
            "answer_panel",
            "--workflow-label",
            "case_prep",
            "--desired-outcome",
            "Visible provenance and source trail.",
            "--sentiment",
            "negative",
            "--tag",
            "provenance",
            "--tag",
            "trust",
            "--provenance-collector",
            "manual_note",
            "--provenance-source-ref",
            "interview:1",
        ]
    )
    add_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert add_payload["receipt"]["feedback_class"] == "competitor_frustration"

    receipt_id = add_payload["receipt"]["receipt_id"]
    exit_code = main(["--db-path", str(db_path), "feedback-summary", "--receipt-id", receipt_id])
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["summary"]["receipt"]["target_product"] == "competitor-x"
    assert summary_payload["summary"]["receipt"]["tags"] == ["provenance", "trust"]
    assert summary_payload["summary"]["receipt"]["provenance"]["collector"] == "manual_note"
    assert summary_payload["summary"]["receipt"]["provenance"]["source_ref"] == "interview:1"


def test_query_fact_review_script_imports_feedback_receipts(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    input_path = tmp_path / "feedback.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "feedback_class": "suite_frustration",
                        "role_label": "builder",
                        "task_label": "browse_corpus",
                        "source_kind": "operator_note",
                        "summary": "The route exists but the next action is unclear.",
                        "quote_text": "I can see the page, but I still do not know the next step.",
                        "severity": "medium",
                        "target_product": "itir-svelte",
                        "tags": ["workflow"],
                        "provenance": {"collector": "pytest"},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": FEEDBACK_RECEIPT_VERSION,
                        "feedback_class": "delight_signal",
                        "role_label": "lawyer",
                        "task_label": "review_sources",
                        "source_kind": "chat_thread",
                        "summary": "The user values visible disagreement and abstention.",
                        "quote_text": "I like that it shows disagreement instead of flattening it away.",
                        "severity": "low",
                        "captured_at": "2026-03-27T18:00:00Z",
                        "target_product": "SensibLaw",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["--db-path", str(db_path), "feedback-import", "--input", str(input_path)])
    import_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert import_payload["imported_count"] == 2

    exit_code = main(["--db-path", str(db_path), "feedback-receipts", "--limit", "10"])
    receipts_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(receipts_payload["receipts"]) == 2
    assert {row["feedback_class"] for row in receipts_payload["receipts"]} == {"suite_frustration", "delight_signal"}
    imported_suite = next(row for row in receipts_payload["receipts"] if row["feedback_class"] == "suite_frustration")
    assert imported_suite["target_product"] == "itir-svelte"
    assert imported_suite["tags"] == ["workflow"]
    assert imported_suite["provenance"]["collector"] == "pytest"


def test_query_fact_review_script_resolves_and_reopens_by_workflow_link(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "resolve-workflow",
            "--workflow-kind",
            "transcript_semantic",
            "--workflow-run-id",
            "semantic:query-demo",
        ]
    )
    resolve_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert resolve_payload["workflow_link"]["fact_run_id"] == run_id

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--workflow-kind",
            "transcript_semantic",
            "--workflow-run-id",
            "semantic:query-demo",
            "summary",
        ]
    )
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["summary"]["run"]["run_id"] == run_id

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "latest-workflow",
            "--workflow-kind",
            "transcript_semantic",
        ]
    )
    latest_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert latest_payload["workflow_link"]["fact_run_id"] == run_id
    assert latest_payload["summary"]["run"]["run_id"] == run_id

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--workflow-kind",
            "transcript_semantic",
            "summary",
        ]
    )
    implicit_latest_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert implicit_latest_payload["summary"]["run"]["run_id"] == run_id

    exit_code = main(["--db-path", str(db_path), "sources", "--workflow-kind", "transcript_semantic"])
    sources_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert sources_payload["sources"][0]["latest_workflow_link"]["fact_run_id"] == run_id


def test_query_fact_review_script_exports_demo_bundle_for_mary_operator_path(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "demo-bundle",
            "--workflow-kind",
            "transcript_semantic",
            "--workflow-run-id",
            "semantic:query-demo",
            "--wave",
            "wave1_legal",
            "--fixture-kind",
            "real",
        ]
    )
    bundle_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert bundle_payload["selector"]["run_id"] == run_id
    assert bundle_payload["selector"]["workflow_kind"] == "transcript_semantic"
    assert bundle_payload["selector"]["workflow_run_id"] == "semantic:query-demo"
    assert bundle_payload["selector"]["wave"] == "wave1_legal"
    assert bundle_payload["selector"]["fixture_kind"] == "real"
    assert bundle_payload["workbench"]["reopen_navigation"]["query"]["workflow_kind"] == "transcript_semantic"
    assert "missing_actor" in bundle_payload["workbench"]["issue_filters"]["available_filters"]
    assert isinstance(bundle_payload["workbench"]["semantic_context"], dict)
    assert bundle_payload["workbench"]["workflow_summary"]["stage"] in {
        "inspect",
        "decide",
        "record",
        "follow_up",
    }
    assert "chronology_groups" in bundle_payload["workbench"]
    assert bundle_payload["acceptance"]["wave"] == "wave1_legal"
    assert bundle_payload["sources"][0]["latest_workflow_link"]["workflow_run_id"] == "semantic:query-demo"


def test_query_fact_review_script_accepts_later_acceptance_waves_for_demo_bundle(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "demo-bundle",
            "--workflow-kind",
            "transcript_semantic",
            "--workflow-run-id",
            "semantic:query-demo",
            "--wave",
            "wave5_handoff_false_coherence",
            "--fixture-kind",
            "real",
        ]
    )
    bundle_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert bundle_payload["selector"]["run_id"] == run_id
    assert bundle_payload["selector"]["wave"] == "wave5_handoff_false_coherence"
    assert bundle_payload["acceptance"]["wave"] == "wave5_handoff_false_coherence"


def test_query_fact_review_script_acceptance_supports_wave4_fixture_kind(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "acceptance",
            "--run-id",
            run_id,
            "--wave",
            "wave4_medical_regulatory",
            "--fixture-kind",
            "real",
        ]
    )
    acceptance_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert acceptance_payload["acceptance"]["wave"] == "wave4_medical_regulatory"
    assert acceptance_payload["acceptance"]["fixture_kind"] == "real"
    assert acceptance_payload["acceptance"]["summary"]["story_count"] == len(STORY_WAVES["wave4_medical_regulatory"])


def test_query_fact_review_script_demo_bundle_resolves_selector_variants_for_later_wave(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "demo-bundle",
            "--workflow-kind",
            "transcript_semantic",
            "--source-label",
            "query_fact_review_demo",
            "--wave",
            "wave4_medical_regulatory",
            "--fixture-kind",
            "synthetic",
        ]
    )
    bundle_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert bundle_payload["selector"]["run_id"] == run_id
    assert bundle_payload["selector"]["workflow_kind"] == "transcript_semantic"
    assert bundle_payload["selector"]["workflow_run_id"] == "semantic:query-demo"
    assert bundle_payload["selector"]["source_label"] == "query_fact_review_demo"
    assert bundle_payload["selector"]["wave"] == "wave4_medical_regulatory"
    assert bundle_payload["acceptance"]["wave"] == "wave4_medical_regulatory"
    assert bundle_payload["acceptance"]["summary"]["story_count"] == len(STORY_WAVES["wave4_medical_regulatory"])


def test_query_fact_review_script_shows_full_report(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    run_id = _seed_fact_review_run(db_path)

    exit_code = main(["--db-path", str(db_path), "report", "--run-id", run_id])
    report_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "report" in report_payload
    assert report_payload["report"]["run"]["run_id"] == run_id
    assert "statements" in report_payload["report"]


def test_query_fact_review_script_lists_persisted_contested_review_runs(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "query_contested_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    result = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=Path(db_path),
    )
    review_run_id = result["persist_summary"]["review_run_id"]

    exit_code = main(["--db-path", str(db_path), "contested-runs", "--limit", "5"])
    runs_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert runs_payload["runs"][0]["review_run_id"] == review_run_id
    assert runs_payload["runs"][0]["source_label"] == "query_contested_demo"
    assert runs_payload["runs"][0]["covered_count"] == 1

    exit_code = main(["--db-path", str(db_path), "contested-summary", "--review-run-id", review_run_id])
    summary_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary_payload["review"]["run"]["review_run_id"] == review_run_id
    assert summary_payload["review"]["summary"]["covered_count"] == 1
    assert summary_payload["review"]["affidavit_rows"][0]["proposition_id"] == "aff-prop:p1-s1"
    assert summary_payload["review"]["affidavit_rows"][0]["status_explanation"]["status_scope"] == "coverage"
    assert summary_payload["review"]["affidavit_rows"][0]["status_explanation"]["status_value"] == "covered"
    assert summary_payload["review"]["source_review_rows"][0]["status_explanation"]["status_scope"] == "review"
    assert summary_payload["review"]["source_review_rows"][0]["status_explanation"]["status_bucket"] in {
        "resolved",
        "review_source",
        "adjudicate",
        "inspect",
    }
    assert summary_payload["review"]["source_review_rows"][0]["status_explanation"]["why"]
    assert "review coverage" not in summary_payload["review"]["source_review_rows"][0]["status_explanation"]["why"].casefold()


def test_query_fact_review_script_shows_contested_proving_slice(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "query_contested_slice_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The witness later denied attending the second meeting.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "reviewed",
            },
            {
                "fact_id": "fact:f2",
                "contestation_count": 1,
                "reason_codes": ["source_conflict"],
                "latest_review_status": "contested",
            },
        ],
    }
    result = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text=(
            "The witness attended the meeting on Tuesday.\n\n"
            "The witness denied attending the second meeting.\n\n"
            "The witness also saw the respondent leave at noon."
        ),
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=Path(db_path),
    )
    review_run_id = result["persist_summary"]["review_run_id"]

    exit_code = main(["--db-path", str(db_path), "contested-proving-slice", "--review-run-id", review_run_id])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    proving_slice = payload["proving_slice"]
    assert proving_slice["run"]["review_run_id"] == review_run_id
    assert proving_slice["summary"]["supported_affidavit_count"] == 1
    assert proving_slice["summary"]["disputed_affidavit_count"] == 1
    assert proving_slice["summary"]["weakly_addressed_affidavit_count"] == 0
    assert proving_slice["summary"]["missing_affidavit_count"] == 1
    assert proving_slice["sections"]["supported"][0]["proposition_id"] == "aff-prop:p1-s1"
    assert proving_slice["sections"]["supported"][0]["relation_type"] in {"exact_support", "equivalent_support"}
    assert proving_slice["sections"]["supported"][0]["relation_root"] == "supports"
    assert proving_slice["sections"]["supported"][0]["explanation"]["classification"] == "supported"
    assert proving_slice["sections"]["supported"][0]["status_explanation"]["status_value"] == "covered"
    assert "support" in proving_slice["sections"]["supported"][0]["status_explanation"]["why"].casefold()
    assert proving_slice["sections"]["disputed"][0]["relation_type"] in {"explicit_dispute", "implicit_dispute"}
    assert proving_slice["sections"]["disputed"][0]["explanation"]["classification"] == "disputed"
    assert proving_slice["sections"]["missing"][0]["proposition_id"] == "aff-prop:p3-s1"
    assert proving_slice["sections"]["missing"][0]["relation_type"] == "unrelated"
    assert proving_slice["sections"]["missing"][0]["relation_leaf"] == "missing"
    assert proving_slice["sections"]["missing"][0]["explanation"]["classification"] == "missing"
    assert proving_slice["sections"]["missing"][0]["status_explanation"]["status_bucket"] == "review_source"
    assert "missing" in proving_slice["sections"]["missing"][0]["status_explanation"]["why"].casefold()
    assert proving_slice["next_steps"]

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "contested-proving-slice",
            "--review-run-id",
            review_run_id,
            "--with-interrogatives",
        ]
    )
    interrogative_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    interrogatives = interrogative_payload["proving_slice"]["sections"]["missing"][0]["interrogatives"]
    assert interrogatives["why"]
    assert any(value.startswith("paragraph:") for value in interrogatives["when"])


def test_query_fact_review_script_shows_narrow_contested_rows(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "query_contested_rows_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The witness denied attending the second meeting.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "reviewed"},
            {"fact_id": "fact:f2", "contestation_count": 1, "reason_codes": ["source_conflict"], "latest_review_status": "contested"},
        ],
    }
    result = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text=(
            "The witness attended the meeting on Tuesday.\n\n"
            "The witness denied attending the second meeting."
        ),
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=Path(db_path),
    )
    review_run_id = result["persist_summary"]["review_run_id"]

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "contested-rows",
            "--review-run-id",
            review_run_id,
            "--proposition-id",
            "aff-prop:p2-s1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["review_run_id"] == review_run_id
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["proposition_id"] == "aff-prop:p2-s1"
    assert row["relation_root"] in {"invalidates", "supports", "non_resolving", "unanswered"}
    assert isinstance(row["matched_source_rows"], list)
    assert row["status_explanation"]["status_value"] == row["coverage_status"]
    assert row["status_explanation"]["related_record_id"] == row["best_source_row_id"]
    assert isinstance(row["status_explanation"]["details"]["missing_dimensions"], list)
    assert row["status_explanation"]["why"]

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "contested-rows",
            "--review-run-id",
            review_run_id,
            "--proposition-id",
            "aff-prop:p2-s1",
            "--with-interrogatives",
        ]
    )
    interrogative_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    interrogative_row = interrogative_payload["rows"][0]
    assert interrogative_row["interrogatives"]["why"] == interrogative_row["status_explanation"]["why"]
    assert any(value.startswith("paragraph:") for value in interrogative_row["interrogatives"]["when"])
    assert interrogative_row["interrogatives"]["what"]
