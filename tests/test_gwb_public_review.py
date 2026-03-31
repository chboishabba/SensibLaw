from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_gwb_public_review as module
from scripts.build_gwb_public_review import ARTIFACT_VERSION, build_gwb_public_review


def test_build_gwb_public_review(tmp_path: Path) -> None:
    result = build_gwb_public_review(tmp_path / "out")

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert payload["version"] == ARTIFACT_VERSION
    assert payload["fixture_kind"] == "gwb_public_review"
    assert summary["review_item_count"] == 11
    assert summary["selected_seed_lane_count"] == 11
    assert summary["source_row_count"] == 77
    assert summary["covered_count"] == 32
    assert summary["missing_review_count"] == 45
    assert summary["candidate_anchor_count"] == 209
    assert summary["provisional_structured_anchor_count"] == 97
    assert summary["provisional_anchor_bundle_count"] == 41
    assert summary["related_review_cluster_count"] == 9
    assert summary["unresolved_surface_count"] == 7
    assert summary["ambiguous_event_count"] == 9
    normalized = payload["normalized_metrics_v1"]
    assert normalized["artifact_id"] == "gwb_checked_public_review_v1"
    assert normalized["review_item_status_counts"] == {
        "accepted": 2,
        "review_required": 9,
        "held": 0,
    }
    assert normalized["source_status_counts"] == {
        "accepted": 32,
        "review_required": 45,
        "held": 0,
    }
    assert normalized["dominant_primary_workload"] == "linkage_pressure"
    assert normalized["primary_workload_counts"]["linkage_pressure"] == 45
    assert normalized["candidate_signal_count"] == 97
    assert normalized["provisional_queue_row_count"] == 97
    assert normalized["provisional_bundle_count"] == 41
    assert normalized["review_required_source_ratio"] == 0.584416
    assert normalized["candidate_signal_density"] == 2.155556
    assert normalized["provisional_row_density"] == 2.155556
    assert normalized["provisional_bundle_density"] == 0.911111

    assert any(row["review_status"] == "covered" for row in payload["source_review_rows"])
    assert any(row["review_status"] == "missing_review" for row in payload["source_review_rows"])
    assert payload["related_review_clusters"]
    assert payload["provisional_structured_anchors"]
    assert payload["provisional_anchor_bundles"]
    assert payload["provisional_anchor_bundles"][0]["bundle_rank"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Public Review" in summary_text
    assert "Normalized Metrics" in summary_text
    assert "Provisional Anchor Bundles" in summary_text


def test_gwb_public_review_consumes_shared_anchor_queueing_component() -> None:
    rank_src = inspect.getsource(module._rank_provisional_rows)
    bundle_src = inspect.getsource(module._bundle_provisional_rows)

    assert "_build_provisional_structured_anchors_impl" in rank_src
    assert "_build_provisional_anchor_bundles_impl" in bundle_src
