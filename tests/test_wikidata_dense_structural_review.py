from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_wikidata_dense_structural_review as dense_module
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
    normalized = artifact["normalized_metrics_v1"]
    assert normalized["artifact_id"] == "wikidata_dense_structural_review_v1"
    assert normalized["review_item_status_counts"] == {
        "accepted": 5,
        "review_required": 4,
        "held": 0,
    }
    assert normalized["source_status_counts"] == {
        "accepted": 33,
        "review_required": 20,
        "held": 0,
    }
    assert normalized["dominant_primary_workload"] == "structural_pressure"
    assert normalized["primary_workload_counts"]["structural_pressure"] == 13
    assert normalized["primary_workload_counts"]["governance_pressure"] == 7
    assert normalized["candidate_signal_count"] == 28
    assert normalized["review_required_source_ratio"] == 0.377358
    assert normalized["candidate_signal_density"] == 1.4
    assert normalized["provisional_row_density"] == 4.4
    assert normalized["provisional_bundle_density"] == 0.45

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
    assert "Normalized Metrics" in summary_text
    assert "Top Provisional Review Bundles" in summary_text


def test_wikidata_dense_structural_review_uses_shared_io_policy() -> None:
    source = inspect.getsource(dense_module)

    assert "load_json_object(" in source
    assert "relative_repo_path(" in source
    assert "write_json_markdown_artifact(" in source


def test_wikidata_dense_structural_review_uses_shared_geometry_policy() -> None:
    source = inspect.getsource(dense_module)

    assert "build_dense_qualifier_drift_row(" in source
    assert "build_dense_qualifier_drift_cues(" in source
    assert "build_dense_hotspot_rows(" in source
    assert "build_dense_hotspot_cues(" in source
    assert "build_dense_disjointness_row(" in source
    assert "build_dense_disjointness_cues(" in source
