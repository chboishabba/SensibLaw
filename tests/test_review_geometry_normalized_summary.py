from __future__ import annotations

import json
from pathlib import Path

from scripts.build_review_geometry_normalized_summary import build_normalized_summary


def test_build_review_geometry_normalized_summary(tmp_path: Path) -> None:
    result = build_normalized_summary(tmp_path / "out")

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["version"] == "review_geometry_normalized_summary_v1"
    assert len(payload["artifacts"]) == 6

    metrics_by_id = {row["artifact_id"]: row for row in payload["artifacts"]}
    assert metrics_by_id["au_narrow_affidavit_coverage_review_v1"]["dominant_primary_workload"] == "queue_pressure"
    assert metrics_by_id["au_dense_affidavit_coverage_review_v1"]["review_required_source_ratio"] == 0.875
    assert metrics_by_id["wikidata_checked_structural_review_v1"]["primary_workload_counts"]["governance_pressure"] == 3
    assert metrics_by_id["wikidata_dense_structural_review_v1"]["candidate_signal_density"] == 1.4
    assert metrics_by_id["gwb_checked_public_review_v1"]["source_status_counts"]["review_required"] == 45
    assert metrics_by_id["gwb_broader_review_v1"]["provisional_bundle_density"] == 1.0

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Review Geometry Normalized Summary" in summary_text
    assert "au_dense_affidavit_coverage_review_v1" in summary_text
    assert "wikidata_dense_structural_review_v1" in summary_text
    assert "gwb_broader_review_v1" in summary_text
