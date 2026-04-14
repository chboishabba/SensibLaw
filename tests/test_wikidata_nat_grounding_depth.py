from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import copy
import json

from src.ontology.wikidata_grounding_depth import (
    GROUNDING_ATTACHMENT_SCHEMA_VERSION,
    GROUNDING_BATCH_SCHEMA_VERSION,
    GROUNDING_DEPTH_SCHEMA_VERSION,
    GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION,
    GROUNDING_PRIORITY_SURFACE_SCHEMA_VERSION,
    GROUNDING_ROUTING_SCHEMA_VERSION,
    GROUNDING_SCORECARD_SCHEMA_VERSION,
    build_grounding_depth_attachment,
    build_grounding_depth_batch,
    build_grounding_depth_comparison,
    build_grounding_depth_evidence_report,
    build_grounding_depth_priority_surface,
    build_grounding_depth_routing_report,
    build_grounding_depth_scorecard,
    build_grounding_depth_summary,
)


def _load_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_packets_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_grounding_depth_fixture_contains_packets() -> None:
    payload = _load_fixture()
    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["evidence_focus"] == "hard packets grounding depth"
    assert len(payload["sample_packets"]) == 3


def test_each_packet_has_revision_evidence() -> None:
    payload = _load_fixture()
    for packet in payload["sample_packets"]:
        assert packet["qid"].startswith("Q")
        assert packet["revision_url"].startswith("https://")
        assert isinstance(packet["revision_locked_notes"], str)
        assert packet["revision_evidence"], "packet should include evidence excerpts"
        excerpt_texts = [e["excerpt"] for e in packet["revision_evidence"]]
    assert all(excerpt_texts), "excerpt cannot be empty"


def _load_attachment_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_operator_surface_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_grounding_attachment_matches_fixture() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    review_packet = {"packet_id": "review-packet:5bae90b4fcb444f6", "review_entity_qid": "Q10403939"}
    attachment = build_grounding_depth_attachment(
        review_packet=review_packet,
        grounding_summary=summary,
    )
    expected = _load_attachment_fixture()
    assert attachment["schema_version"] == GROUNDING_ATTACHMENT_SCHEMA_VERSION
    assert attachment == expected


def test_build_grounding_attachment_fail_closed() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    review_packet = {"packet_id": "unknown", "review_entity_qid": "Q000000"}
    attachment = build_grounding_depth_attachment(
        review_packet=review_packet,
        grounding_summary=summary,
    )
    assert attachment["grounding_status"] == "no_grounding_data"
    assert attachment["notes"] == ["no grounding data matched the provided packet"]


def test_build_grounding_summary_uses_fixture() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    assert summary["schema_version"] == GROUNDING_DEPTH_SCHEMA_VERSION
    assert summary["lane_id"] == payload["lane_id"]
    assert summary["packet_count"] == 3
    assert summary["grounded_packet_count"] == 3
    assert all(pkt["grounding_status"] == "grounded" for pkt in summary["packets"])


def test_missing_evidence_marks_packet_incomplete() -> None:
    payload = _load_fixture()
    altered = copy.deepcopy(payload)
    altered["sample_packets"][0]["revision_evidence"][0]["excerpt"] = ""
    summary = build_grounding_depth_summary(fixture=altered)
    assert summary["grounded_packet_count"] == 2
    assert summary["packets"][0]["grounding_status"] == "missing_evidence"
    evidence_entry = summary["packets"][0]["revision_evidence"][0]
    assert evidence_entry["status"] == "incomplete"
    assert "excerpt" in evidence_entry["missing_fields"]


def _load_batch_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_batch_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_grounding_batch_matches_fixture() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    review_packets = [
        {"packet_id": "review-packet:5bae90b4fcb444f6", "review_entity_qid": "Q10403939"},
        {"packet_id": "review-packet:c52b8308fdbdd5e3", "review_entity_qid": "Q731938"},
    ]
    batch = build_grounding_depth_batch(
        review_packets=review_packets,
        grounding_summary=summary,
    )
    expected = _load_batch_fixture()
    assert batch["schema_version"] == GROUNDING_BATCH_SCHEMA_VERSION
    assert batch == expected


def test_build_grounding_batch_handles_empty_review_packets() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    batch = build_grounding_depth_batch(
        review_packets=[],
        grounding_summary=summary,
    )
    assert batch["attachment_count"] == 0
    assert batch["attachments"] == []


def test_cli_generates_expected_batch(tmp_path: Path) -> None:
    from cli import grounding_depth

    summary_fixture = _load_fixture()
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary_fixture, indent=2), encoding="utf-8")
    packets_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_review_packets_20260402.json"
    )
    output_path = tmp_path / "batch.json"
    grounding_depth.main(
        [
            "--summary",
            str(summary_path),
            "--packets",
            str(packets_path),
            "--outfile",
            str(output_path),
        ]
    )
    produced = json.loads(output_path.read_text(encoding="utf-8"))
    expected = _load_batch_fixture()
    assert produced == expected


def _load_report_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_evidence_report_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_scorecard_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_scorecard_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_evidence_report_matches_fixture() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    report = build_grounding_depth_evidence_report(grounding_summary=summary)
    expected = _load_report_fixture()
    assert report["schema_version"] == GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report == expected


def test_build_priority_surface_is_empty_when_all_packets_grounded() -> None:
    payload = _load_fixture()
    summary = build_grounding_depth_summary(fixture=payload)
    priority = build_grounding_depth_priority_surface(grounding_summary=summary)

    assert priority["schema_version"] == GROUNDING_PRIORITY_SURFACE_SCHEMA_VERSION
    assert priority["packet_count"] == 3
    assert priority["grounded_packet_count"] == 3
    assert priority["bounded_follow_candidate_count"] == 0
    assert priority["highest_priority_score"] == 0
    assert priority["gap_class_counts"]["grounded"] == 3
    assert priority["dominant_gap_class"] == "grounded"
    assert priority["missing_field_counts"] == {}
    assert priority["recommended_follow_scope_counts"]["none"] == 3
    assert all(row["priority_score"] == 0 for row in priority["queue"])
    assert all(row["recommended_follow_target"] == "none" for row in priority["queue"])
    assert all(row["grounding_gap_class"] == "grounded" for row in priority["queue"])
    assert all(row["recommended_follow_scope"] == "none" for row in priority["queue"])


def test_build_priority_surface_ranks_missing_grounding_first() -> None:
    payload = _load_fixture()
    altered = copy.deepcopy(payload)
    altered["sample_packets"][0]["revision_evidence"][0]["excerpt"] = ""
    altered["sample_packets"][0]["revision_evidence"][0]["excerpt_summary"] = ""
    summary = build_grounding_depth_summary(fixture=altered)
    priority = build_grounding_depth_priority_surface(grounding_summary=summary)

    assert priority["bounded_follow_candidate_count"] == 1
    first = priority["queue"][0]
    assert first["packet_id"] == "review-packet:5bae90b4fcb444f6"
    assert first["grounding_status"] == "missing_evidence"
    assert first["missing_fields"] == ["excerpt", "excerpt_summary"]
    assert first["grounding_gap_class"] == "revision_evidence_missing"
    assert first["recommended_follow_target"] == "revision_locked_evidence"
    assert first["recommended_follow_scope"] == "revision_evidence"
    assert first["bounded_follow_recommended"] is True
    assert first["priority_rank"] == 1
    assert priority["highest_priority_score"] == first["priority_score"]
    assert priority["gap_class_counts"]["revision_evidence_missing"] == 1
    assert priority["dominant_gap_class"] == "grounded"
    assert priority["missing_field_counts"]["excerpt"] == 1
    assert priority["missing_field_counts"]["excerpt_summary"] == 1
    assert priority["recommended_follow_scope_counts"]["revision_evidence"] == 1


def test_live_follow_receipts_shift_priority_from_more_search_to_review() -> None:
    payload = _load_fixture()
    altered = copy.deepcopy(payload)
    altered["sample_packets"][0]["revision_evidence"][0]["excerpt"] = ""
    altered["sample_packets"][0]["revision_evidence"][0]["excerpt_summary"] = ""
    live_result = {
        "result_rows": [
            {
                "qid": "Q10403939",
                "plan_id": "hard_grounding_packet:1",
                "target_ref": "review-packet:5bae90b4fcb444f6",
                "status": "fetched",
                "chosen_source_class": "named_revision_locked_source",
                "evidence": {
                    "source_class": "named_revision_locked_source",
                    "revision_source": {
                        "label": "Akademiska Hus",
                        "revision_url": "https://www.wikidata.org/w/index.php?title=Q10403939&oldid=2419926147",
                    },
                },
            }
        ]
    }
    summary = build_grounding_depth_summary(
        fixture=altered,
        live_follow_results=[live_result],
    )
    report = build_grounding_depth_evidence_report(grounding_summary=summary)
    priority = build_grounding_depth_priority_surface(grounding_summary=summary)

    first_summary = summary["packets"][0]
    assert first_summary["live_follow_status"] == "live_receipts_fetched"
    assert len(first_summary["live_follow_receipts"]) == 1

    first_report = report["packets"][0]
    assert first_report["live_follow_status"] == "live_receipts_fetched"
    assert first_report["live_follow_count"] == 1
    assert first_report["live_source_class_counts"]["named_revision_locked_source"] == 1

    first = priority["queue"][0]
    assert first["packet_id"] == "review-packet:5bae90b4fcb444f6"
    assert first["grounding_gap_class"] == "live_receipts_ready_for_review"
    assert first["recommended_follow_target"] == "review_live_follow_receipts"
    assert first["recommended_follow_scope"] == "packet_review"
    assert first["bounded_follow_recommended"] is False
    assert first["live_follow_status"] == "live_receipts_fetched"
    assert first["live_follow_count"] == 1
    assert first["live_source_class_counts"]["named_revision_locked_source"] == 1
    assert priority["live_follow_ready_count"] == 1
    assert priority["gap_class_counts"]["live_receipts_ready_for_review"] == 1
    assert priority["recommended_follow_scope_counts"]["packet_review"] >= 1
    assert priority["live_source_class_counts"]["named_revision_locked_source"] == 1


def _build_live_follow_result(
    *,
    source_class: str,
    revision_timestamp: str,
    plan_id: str = "hard_grounding_packet:1",
    qid: str = "Q10403939",
) -> dict[str, Any]:
    return {
        "result_rows": [
            {
                "qid": qid,
                "plan_id": plan_id,
                "target_ref": "review-packet:5bae90b4fcb444f6",
                "status": "fetched",
                "chosen_source_class": source_class,
                "evidence": {
                    "source_class": source_class,
                    "revision": {
                        "revision_timestamp": revision_timestamp,
                    },
                },
            }
        ]
    }


def test_hard_grounding_policy_checks_allowlist_and_freshness() -> None:
    from src.ontology.wikidata_grounding_depth import HARD_GROUNDING_ALLOWED_SOURCE_CLASSES

    payload = _load_fixture()
    live_result = _build_live_follow_result(
        source_class="named_revision_locked_source",
        revision_timestamp="2025-10-21T13:17:20Z",
    )
    summary = build_grounding_depth_summary(
        fixture=payload,
        live_follow_results=[live_result],
        policy_reference_time=datetime(2025, 10, 22, tzinfo=timezone.utc),
    )
    policy_checks = summary["hard_grounding_policy_checks"]
    assert policy_checks["allowed_source_classes"] == list(sorted(HARD_GROUNDING_ALLOWED_SOURCE_CLASSES))
    assert policy_checks["max_revision_age_days"] == 365
    assert policy_checks["violations"] == []


def test_hard_grounding_policy_checks_flags_unsupported_and_stale() -> None:
    payload = _load_fixture()
    live_result = _build_live_follow_result(
        source_class="unsupported_source",
        revision_timestamp="2023-01-01T00:00:00Z",
    )
    summary = build_grounding_depth_summary(
        fixture=payload,
        live_follow_results=[live_result],
        policy_reference_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    policy_checks = summary["hard_grounding_policy_checks"]
    assert len(policy_checks["violations"]) == 2
    codes = {entry["code"] for entry in policy_checks["violations"]}
    assert codes == {"unsupported_source_class", "stale_revision"}


def test_cli_writes_report(tmp_path: Path) -> None:
    from cli import grounding_depth

    summary_fixture = _load_fixture()
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary_fixture, indent=2), encoding="utf-8")
    packets_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_review_packets_20260402.json"
    )
    batch_path = tmp_path / "batch.json"
    report_path = tmp_path / "report.json"
    grounding_depth.main(
        [
            "--summary",
            str(summary_path),
            "--packets",
            str(packets_path),
            "--outfile",
            str(batch_path),
            "--report-out",
            str(report_path),
        ]
    )
    produced_report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_report = _load_report_fixture()
    assert produced_report == expected_report


def _load_single_batch_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_batch_single_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_comparison_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_comparison_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_comparison_matches_fixture() -> None:
    base_batch = _load_batch_fixture()
    single_batch = _load_single_batch_fixture()
    comparison = build_grounding_depth_comparison(batches=[base_batch, single_batch])
    expected = _load_comparison_fixture()
    assert comparison["schema_version"] == GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION
    assert comparison == expected


def test_cli_writes_comparison(tmp_path: Path) -> None:
    from cli import grounding_depth

    summary_fixture = _load_fixture()
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary_fixture, indent=2), encoding="utf-8")
    packets_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_grounding_depth_review_packets_20260402.json"
    )
    batch_path = tmp_path / "batch.json"
    comparison_path = tmp_path / "comparison.json"
    scorecard_path = tmp_path / "scorecard.json"
    grounding_depth.main(
        [
            "--summary",
            str(summary_path),
            "--packets",
            str(packets_path),
            "--outfile",
            str(batch_path),
            "--compare",
            str(
                Path(__file__).resolve().parent
                / "fixtures"
                / "wikidata"
                / "wikidata_nat_grounding_depth_batch_20260402.json"
            ),
            "--compare",
            str(
                Path(__file__).resolve().parent
                / "fixtures"
                / "wikidata"
                / "wikidata_nat_grounding_depth_batch_single_20260402.json"
            ),
            "--comparison-out",
            str(comparison_path),
            "--scorecard-run",
            "baseline="
            + str(
                Path(__file__).resolve().parent
                / "fixtures"
                / "wikidata"
                / "wikidata_nat_grounding_depth_comparison_20260402.json"
            ),
            "--scorecard-run",
            "single="
            + str(
                Path(__file__).resolve().parent
                / "fixtures"
                / "wikidata"
                / "wikidata_nat_grounding_depth_comparison_single_20260402.json"
            ),
            "--scorecard-out",
            str(scorecard_path),
        ]
    )
    produced_comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    expected_comparison = _load_comparison_fixture()
    assert produced_comparison == expected_comparison
    produced_scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    expected_scorecard = _load_scorecard_fixture()
    assert produced_scorecard == expected_scorecard


def test_build_grounding_depth_routing_report_tracks_needs() -> None:
    summary = build_grounding_depth_summary(fixture=_load_fixture())
    report = build_grounding_depth_routing_report(grounding_summary=summary)
    assert report["schema_version"] == GROUNDING_ROUTING_SCHEMA_VERSION
    routing_map = {row["packet_id"]: row for row in report["routing_report"]}
    first_packet = routing_map["review-packet:5bae90b4fcb444f6"]
    assert first_packet["coverage_status"] == "unknown"
    assert first_packet["routing_needs"] == ["follow", "reference"]
    second_packet = routing_map["review-packet:atrium-ljungberg-20260401"]
    assert "authority" in second_packet["routing_needs"]
    assert "follow" in second_packet["routing_needs"]
    assert "reference" in second_packet["routing_needs"]


def test_build_grounding_depth_routing_report_counts_hold_vs_abstain() -> None:
    summary = build_grounding_depth_summary(fixture=_load_fixture())
    coverage_index = {
        "packet_slots": [
            {"packet_id": "review-packet:5bae90b4fcb444f6", "coverage_decision": "grounded"},
            {"packet_id": "review-packet:atrium-ljungberg-20260401", "coverage_decision": "hold"},
            {"packet_id": "review-packet:c52b8308fdbdd5e3", "coverage_decision": "abstain"},
        ]
    }
    report = build_grounding_depth_routing_report(
        grounding_summary=summary,
        coverage_index=coverage_index,
    )
    routing_map = {row["packet_id"]: row for row in report["routing_report"]}
    assert report["grounded_packet_count"] == 1
    assert report["hold_count"] == 1
    assert report["abstain_count"] == 1
    assert routing_map["review-packet:5bae90b4fcb444f6"]["coverage_status"] == "grounded"
    assert routing_map["review-packet:atrium-ljungberg-20260401"]["coverage_status"] == "hold"
    assert routing_map["review-packet:c52b8308fdbdd5e3"]["coverage_status"] == "abstain"
