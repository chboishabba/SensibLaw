from __future__ import annotations

import json
from pathlib import Path

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

    assert any(row["review_status"] == "covered" for row in payload["source_review_rows"])
    assert any(row["review_status"] == "missing_review" for row in payload["source_review_rows"])
    assert payload["related_review_clusters"]
    assert payload["provisional_structured_anchors"]
    assert payload["provisional_anchor_bundles"]
    assert payload["provisional_anchor_bundles"][0]["bundle_rank"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Public Review" in summary_text
    assert "Provisional Anchor Bundles" in summary_text
