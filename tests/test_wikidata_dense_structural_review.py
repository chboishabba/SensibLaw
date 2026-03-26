from __future__ import annotations

import json
from pathlib import Path

from scripts.build_wikidata_dense_structural_review import build_dense_review_artifact


def test_build_wikidata_dense_structural_review_artifact(tmp_path: Path) -> None:
    payload = build_dense_review_artifact(tmp_path)

    artifact_path = Path(payload["artifact_path"])
    summary_path = Path(payload["summary_path"])

    assert artifact_path.exists()
    assert summary_path.exists()

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = artifact["summary"]

    assert artifact["version"] == "wikidata_dense_structural_review_v1"
    assert artifact["source_handoff_version"] == "wikidata_structural_handoff_v1"
    assert summary["review_item_count"] == 9
    assert summary["review_required_item_count"] == 4
    assert summary["source_review_row_count"] > 30
    assert summary["candidate_structural_cue_count"] > summary["source_review_row_count"]
    assert summary["provisional_review_row_count"] == summary["candidate_structural_cue_count"]
    assert summary["provisional_review_bundle_count"] == 9
    assert summary["baseline_confirmation_count"] >= 10
    assert summary["cluster_promotion_gap_count"] >= 10
    assert summary["governance_gap_count"] >= 5
    assert summary["qualifier_drift_gap_count"] == 1
    assert summary["structural_contradiction_count"] >= 10

    assert any(
        row["source_kind"] == "qualifier_statement_bundle"
        for row in artifact["source_review_rows"]
    )
    assert any(
        row["source_kind"] == "disjointness_statement_bundle"
        for row in artifact["source_review_rows"]
    )
    assert any(
        row["cue_kind"] == "focus_qid" for row in artifact["candidate_structural_cues"]
    )
    assert artifact["related_review_clusters"]
    assert artifact["provisional_review_rows"][0]["priority_rank"] == 1
    assert artifact["provisional_review_bundles"][0]["bundle_rank"] == 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Wikidata Dense Structural Review Summary" in summary_text
    assert "Top Provisional Review Bundles" in summary_text
