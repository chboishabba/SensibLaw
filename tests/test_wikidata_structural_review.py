from __future__ import annotations

import json
from pathlib import Path

from scripts.build_wikidata_structural_review import build_review_artifact


def test_build_wikidata_structural_review_artifact(tmp_path: Path) -> None:
    payload = build_review_artifact(tmp_path)

    artifact_path = Path(payload["artifact_path"])
    summary_path = Path(payload["summary_path"])

    assert artifact_path.exists()
    assert summary_path.exists()

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = artifact["summary"]

    assert artifact["version"] == "wikidata_structural_review_v1"
    assert artifact["source_handoff_version"] == "wikidata_structural_handoff_v1"
    assert summary["review_item_count"] == 9
    assert summary["related_review_cluster_count"] == 4
    assert summary["review_required_item_count"] == 4
    assert summary["candidate_structural_cue_count"] >= 18
    assert summary["provisional_review_bundle_count"] == 9
    assert summary["governance_gap_count"] == 3
    assert summary["qualifier_drift_gap_count"] == 1
    assert summary["structural_contradiction_count"] == 2
    normalized = artifact["normalized_metrics_v1"]
    assert normalized["artifact_id"] == "wikidata_checked_structural_review_v1"
    assert normalized["review_item_status_counts"] == {
        "accepted": 5,
        "review_required": 4,
        "held": 0,
    }
    assert normalized["source_status_counts"] == {
        "accepted": 10,
        "review_required": 6,
        "held": 0,
    }
    assert normalized["dominant_primary_workload"] == "structural_pressure"
    assert normalized["primary_workload_counts"]["structural_pressure"] == 3
    assert normalized["primary_workload_counts"]["governance_pressure"] == 3
    assert normalized["candidate_signal_count"] == 11
    assert normalized["review_required_source_ratio"] == 0.375
    assert normalized["candidate_signal_density"] == 1.833333
    assert normalized["provisional_row_density"] == 4.166667
    assert normalized["provisional_bundle_density"] == 1.5

    review_item_ids = {row["review_item_id"] for row in artifact["review_item_rows"]}
    assert "review:qualifier_baseline" in review_item_ids
    assert "review:qualifier_drift:Q100104196|P166" in review_item_ids
    assert "review:hotspot_pack:software_entity_kind_collapse_pack_v0" in review_item_ids
    assert "review:disjointness_case:working_fluid_contradiction" in review_item_ids

    clusters = {row["review_item_id"]: row for row in artifact["related_review_clusters"]}
    held_pack_cluster = clusters["review:hotspot_pack:software_entity_kind_collapse_pack_v0"]
    assert held_pack_cluster["dominant_workload_class"] == "governance_gap"
    assert held_pack_cluster["candidate_cue_rollup"]["hold_reason"] == 1
    assert held_pack_cluster["candidate_cue_rollup"]["sample_question"] == 2

    contradiction_cluster = clusters["review:disjointness_case:working_fluid_contradiction"]
    assert contradiction_cluster["dominant_workload_class"] == "structural_contradiction"
    assert contradiction_cluster["candidate_cue_rollup"]["pair_label"] == 1
    assert contradiction_cluster["candidate_cue_rollup"]["violation_counts"] == 1

    provisional_rows = artifact["provisional_review_rows"]
    assert provisional_rows[0]["workload_class"] == "structural_contradiction"
    assert provisional_rows[0]["priority_rank"] == 1

    bundles = artifact["provisional_review_bundles"]
    assert bundles[0]["bundle_rank"] == 1
    assert bundles[0]["review_item_id"].startswith("review:disjointness_case:")
    assert bundles[0]["top_priority_score"] >= bundles[-1]["top_priority_score"]

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Wikidata Structural Review Summary" in summary_text
    assert "Normalized Metrics" in summary_text
    assert "Related review clusters: 4" in summary_text
    assert "Qualifier drift case Q100104196|P166" in summary_text
    assert "Top Provisional Review Bundles" in summary_text
