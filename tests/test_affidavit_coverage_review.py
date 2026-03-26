from __future__ import annotations

import json
from pathlib import Path

from scripts.build_affidavit_coverage_review import build_affidavit_coverage_review, write_affidavit_coverage_review


def test_build_affidavit_coverage_review_from_fact_review_bundle(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:test-run"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The applicant filed a complaint on 1 March 2024.",
                "candidate_status": "reviewed",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The respondent denied the allegation in correspondence.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f3",
                "fact_text": "A witness recalled seeing a blue car near the clinic.",
                "candidate_status": "abstained",
                "statement_ids": ["statement:s3"],
                "excerpt_ids": ["excerpt:e3"],
                "source_ids": ["src:2"],
            },
            {
                "fact_id": "fact:f4",
                "fact_text": "The hearing was adjourned to 5 March 2024.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s4"],
                "excerpt_ids": ["excerpt:e4"],
                "source_ids": ["src:2"],
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
            {
                "fact_id": "fact:f3",
                "contestation_count": 0,
                "reason_codes": ["statement_only_fact"],
                "latest_review_status": "abstained",
            },
            {
                "fact_id": "fact:f4",
                "contestation_count": 0,
                "reason_codes": ["missing_date"],
                "latest_review_status": "review_queue",
            },
        ],
    }
    affidavit_text = (
        "The applicant filed a complaint on 1 March 2024.\n\n"
        "The respondent denied the complaint in correspondence.\n\n"
        "The court ordered costs against the respondent."
    )

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path="source.json",
        affidavit_path="draft.txt",
    )

    assert payload["summary"]["affidavit_proposition_count"] == 3
    assert payload["summary"]["covered_count"] == 1
    assert payload["summary"]["contested_affidavit_count"] == 1
    assert payload["summary"]["unsupported_affidavit_count"] == 1
    assert payload["summary"]["missing_review_count"] == 1
    assert payload["summary"]["contested_source_count"] == 1
    assert payload["summary"]["abstained_source_count"] == 1

    affidavit_rows = {row["proposition_id"]: row for row in payload["affidavit_rows"]}
    assert affidavit_rows["aff-prop:p1-s1"]["coverage_status"] == "covered"
    assert affidavit_rows["aff-prop:p2-s1"]["coverage_status"] == "contested_source"
    assert affidavit_rows["aff-prop:p3-s1"]["coverage_status"] == "unsupported_affidavit"

    source_rows = {row["source_row_id"]: row for row in payload["source_review_rows"]}
    assert source_rows["fact:f1"]["review_status"] == "covered"
    assert source_rows["fact:f2"]["review_status"] == "contested_source"
    assert source_rows["fact:f3"]["review_status"] == "abstained_source"
    assert source_rows["fact:f4"]["review_status"] == "missing_review"
    assert source_rows["fact:f4"]["workload_classes"] == ["chronology_gap"]
    assert source_rows["fact:f4"]["has_calendar_reference_hint"] is True
    assert source_rows["fact:f4"]["has_procedural_event_cue"] is True
    assert any(anchor["anchor_kind"] == "calendar_reference" for anchor in source_rows["fact:f4"]["candidate_anchors"])
    assert any(anchor["anchor_kind"] == "procedural_event_keywords" for anchor in source_rows["fact:f4"]["candidate_anchors"])
    assert source_rows["fact:f4"]["recommended_next_action"] == "promote existing event/date cues into structured anchors"
    assert any(
        row["source_row_id"] == "fact:f4" and row["anchor_kind"] == "calendar_reference"
        for row in payload["provisional_structured_anchors"]
    )
    assert all("priority_rank" in row and "priority_score" in row for row in payload["provisional_structured_anchors"])
    assert payload["provisional_anchor_bundles"][0]["source_row_id"] == "fact:f4"
    assert payload["provisional_anchor_bundles"][0]["anchor_count"] == 2


def test_write_affidavit_coverage_review_outputs_files(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:demo"},
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
    out_dir = tmp_path / "artifact"
    result = write_affidavit_coverage_review(
        output_dir=out_dir,
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        source_path="bundle.json",
        affidavit_path="draft.txt",
    )

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["version"] == "affidavit_coverage_review_v1"
    assert payload["summary"]["covered_count"] == 1
    assert "provenance-first comparison surface" in summary_path.read_text(encoding="utf-8")


def test_build_affidavit_coverage_review_uses_segment_level_matching_for_long_source_rows() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:segment-match"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": (
                    "Counsel opened the submissions. Starting with the duty of care, may we emphasise at once "
                    "the significant effect of the Civil Liability Act on that question. Counsel then turned "
                    "to section 6I."
                ),
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The court adjourned until Tuesday morning.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
            {"fact_id": "fact:f2", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="Starting with the duty of care, may we emphasize at once the significant effect of the Civil Liability Act on that question.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["coverage_status"] == "covered"
    assert affidavit_row["best_source_row_id"] == "fact:f1"
    assert affidavit_row["best_match_basis"] == "segment"
    assert "Starting with the duty of care" in affidavit_row["best_match_excerpt"]

    source_rows = {row["source_row_id"]: row for row in payload["source_review_rows"]}
    assert source_rows["fact:f1"]["review_status"] == "covered"
    assert source_rows["fact:f1"]["best_match_basis"] == "segment"
    assert source_rows["fact:f1"]["has_procedural_event_cue"] is True
    assert source_rows["fact:f2"]["review_status"] == "missing_review"


def test_build_affidavit_coverage_review_groups_related_uncovered_rows_by_proposition() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:related-cluster"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The court dismissed the appeal and ordered indemnity costs against the applicant.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The appeal was dismissed with costs after the hearing ended.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": ["missing_date"],
                "latest_review_status": "review_queue",
            },
            {
                "fact_id": "fact:f2",
                "contestation_count": 0,
                "reason_codes": ["statement_only_fact"],
                "latest_review_status": "review_queue",
            },
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The court dismissed the appeal with indemnity costs.",
    )

    assert payload["summary"]["covered_count"] == 1
    assert payload["summary"]["related_source_count"] == 1
    assert payload["summary"]["related_review_cluster_count"] == 1
    clusters = payload["related_review_clusters"]
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["proposition_id"] == "aff-prop:p1-s1"
    assert cluster["candidate_source_count"] == 1
    assert cluster["dominant_workload_class"] == "evidence_gap"
    assert cluster["recommended_next_action"] == "operator evidentiary review"
    assert cluster["reason_code_rollup"] == [{"reason_code": "statement_only_fact", "count": 1}]
    assert cluster["workload_class_rollup"] == [{"workload_class": "evidence_gap", "count": 1}]
    assert cluster["candidate_anchor_rollup"] == [{"anchor_kind": "procedural_event_keywords", "count": 1}]
    assert cluster["candidate_source_rows"][0]["source_row_id"] == "fact:f2"
    assert cluster["candidate_source_rows"][0]["primary_workload_class"] == "evidence_gap"
    assert payload["summary"]["provisional_structured_anchor_count"] == 1
    assert payload["summary"]["provisional_anchor_bundle_count"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1
