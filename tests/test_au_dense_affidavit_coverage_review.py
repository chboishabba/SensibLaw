from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_dense_affidavit_coverage_review import build_au_dense_affidavit_coverage_review


def test_build_au_dense_affidavit_coverage_review(tmp_path: Path) -> None:
    result = build_au_dense_affidavit_coverage_review(tmp_path / "out")

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["version"] == "affidavit_coverage_review_v1"
    assert payload["source_input"]["source_kind"] == "au_dense_overlay_slice"
    assert payload["source_input"]["source_row_count"] == 24
    assert payload["summary"]["affidavit_proposition_count"] == 3
    assert payload["summary"]["covered_count"] >= 2
    assert payload["summary"]["partial_count"] == 0
    assert payload["summary"]["unsupported_affidavit_count"] >= 1
    assert payload["summary"]["missing_review_count"] <= 21
    assert payload["summary"]["related_source_count"] >= 1
    assert payload["summary"]["related_review_cluster_count"] >= 1
    assert payload["summary"]["chronology_gap_count"] >= 1
    assert payload["summary"]["event_extraction_gap_count"] >= 1
    assert payload["summary"]["evidence_gap_count"] >= 1
    assert payload["summary"]["transcript_timestamp_hint_count"] >= 1
    assert payload["summary"]["calendar_reference_hint_count"] >= 1
    assert payload["summary"]["procedural_event_cue_count"] >= 1
    assert payload["summary"]["candidate_anchor_count"] >= 1
    assert payload["summary"]["provisional_structured_anchor_count"] >= 1
    assert payload["summary"]["provisional_anchor_bundle_count"] >= 1
    assert payload["summary"]["affidavit_supported_ratio"] < 1.0
    assert any(row["coverage_status"] == "covered" for row in payload["affidavit_rows"])
    assert any(row["coverage_status"] == "unsupported_affidavit" for row in payload["affidavit_rows"])
    assert any(row["review_status"] == "covered" for row in payload["source_review_rows"])
    assert any(row["review_status"] == "missing_review" for row in payload["source_review_rows"])
    assert any(row["best_match_basis"] == "segment" for row in payload["source_review_rows"] if row["review_status"] == "covered")
    assert payload["related_review_clusters"]
    assert any(cluster["candidate_source_count"] >= 1 for cluster in payload["related_review_clusters"])
    assert any(cluster["reason_code_rollup"] for cluster in payload["related_review_clusters"])
    assert any(cluster["workload_class_rollup"] for cluster in payload["related_review_clusters"])
    assert any(cluster["recommended_next_action"] for cluster in payload["related_review_clusters"])
    assert any(cluster["extraction_hint_rollup"] for cluster in payload["related_review_clusters"])
    assert any(cluster["candidate_anchor_rollup"] for cluster in payload["related_review_clusters"])
    assert any(row["primary_workload_class"] for row in payload["source_review_rows"] if row["review_status"] == "missing_review")
    assert any(row["has_transcript_timestamp_hint"] for row in payload["source_review_rows"] if row["review_status"] == "missing_review")
    assert any(row["candidate_anchors"] for row in payload["source_review_rows"] if row["review_status"] == "missing_review")
    assert payload["provisional_structured_anchors"]
    assert payload["provisional_anchor_bundles"]
    assert payload["provisional_anchor_bundles"][0]["bundle_rank"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_score"] >= payload["provisional_structured_anchors"][-1]["priority_score"]
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Related Review Clusters" in summary_text
    assert "Top reasons:" in summary_text
    assert "Top workload classes:" in summary_text
    assert "Recommended next action:" in summary_text
    assert "Extraction hints:" in summary_text
    assert "Candidate anchors:" in summary_text
    assert "Provisional Structured Anchors" in summary_text
    assert "Provisional Anchor Bundles" in summary_text
    assert "#1" in summary_text
    assert "Source rows: `24`" in summary_text
