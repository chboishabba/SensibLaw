from __future__ import annotations

import json
import sqlite3

from scripts.query_fact_review import main
from src.fact_intake import (
    OBSERVATION_PREDICATE_TO_FAMILY,
    build_fact_intake_payload_from_text_units,
    persist_fact_intake_payload,
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

    exit_code = main(["--db-path", str(db_path), "workbench", "--run-id", run_id])
    workbench_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert workbench_payload["workbench"]["operator_views"]["chronology_prep"]["groups"]["dated_events"]
    assert "contradictory_chronology" in workbench_payload["workbench"]["operator_views"]["intake_triage"]["groups"]
    assert workbench_payload["workbench"]["reopen_navigation"]["query"]["workflow_kind"] == "transcript_semantic"
    assert "missing_actor" in workbench_payload["workbench"]["issue_filters"]["available_filters"]
    first_fact_id = workbench_payload["workbench"]["facts"][0]["fact_id"]
    assert workbench_payload["workbench"]["inspector_classification"]["facts"][first_fact_id]["status_keys"]
    assert "approximate_events" in workbench_payload["workbench"]["chronology_groups"]
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
