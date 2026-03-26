from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_broader_review import ARTIFACT_VERSION, build_gwb_broader_review


def test_build_gwb_broader_review(tmp_path: Path) -> None:
    result = build_gwb_broader_review(tmp_path / "out")

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert payload["version"] == ARTIFACT_VERSION
    assert payload["fixture_kind"] == "gwb_broader_review"
    assert summary["review_item_count"] == 13
    assert summary["distinct_seed_lane_count"] == 13
    assert summary["source_row_count"] > 30
    assert summary["covered_count"] > 10
    assert summary["missing_review_count"] > 5
    assert summary["related_review_cluster_count"] >= 5
    assert summary["candidate_anchor_count"] > summary["source_row_count"]
    assert summary["provisional_review_row_count"] > 10
    assert summary["provisional_review_bundle_count"] >= summary["related_review_cluster_count"]
    normalized = payload["normalized_metrics_v1"]
    assert normalized["artifact_id"] == "gwb_broader_review_v1"
    assert normalized["review_item_status_counts"] == {
        "accepted": 7,
        "review_required": 6,
        "held": 0,
    }
    assert normalized["source_status_counts"] == {
        "accepted": 37,
        "review_required": 11,
        "held": 0,
    }
    assert normalized["dominant_primary_workload"] == "linkage_pressure"
    assert normalized["primary_workload_counts"]["linkage_pressure"] == 8
    assert normalized["primary_workload_counts"]["event_or_time_pressure"] == 3
    assert normalized["candidate_signal_count"] == 38
    assert normalized["provisional_queue_row_count"] == 38
    assert normalized["provisional_bundle_count"] == 11
    assert normalized["review_required_source_ratio"] == 0.229167
    assert normalized["candidate_signal_density"] == 3.454545
    assert normalized["provisional_row_density"] == 3.454545
    assert normalized["provisional_bundle_density"] == 1.0

    assert any(row["source_kind"] == "seed_family_support" for row in payload["source_review_rows"])
    assert any(row["source_kind"] == "merged_promoted_relation" for row in payload["source_review_rows"])
    assert any(row["source_kind"] == "source_family_summary" for row in payload["source_review_rows"])
    assert payload["related_review_clusters"]
    assert payload["provisional_review_rows"][0]["priority_rank"] == 1
    assert payload["provisional_review_bundles"][0]["bundle_rank"] == 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Broader Review" in summary_text
    assert "Normalized Metrics" in summary_text
    assert "Top Provisional Review Bundles" in summary_text
