from __future__ import annotations

from pathlib import Path
import copy
import json

from src.ontology.wikidata_grounding_depth import (
    GROUNDING_ATTACHMENT_SCHEMA_VERSION,
    GROUNDING_BATCH_SCHEMA_VERSION,
    GROUNDING_DEPTH_SCHEMA_VERSION,
    GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION,
    GROUNDING_SCORECARD_SCHEMA_VERSION,
    build_grounding_depth_attachment,
    build_grounding_depth_batch,
    build_grounding_depth_comparison,
    build_grounding_depth_evidence_report,
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


def test_cli_writes_report(tmp_path: Path) -> None:
    from SensibLaw.cli import grounding_depth

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
    from SensibLaw.cli import grounding_depth

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
