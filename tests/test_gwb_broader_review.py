from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_gwb_broader_review as module
from scripts.build_gwb_broader_review import ARTIFACT_VERSION, build_gwb_broader_review
from src.policy.gwb_broader_review_world_model import (
    GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
    build_gwb_broader_review_world_model_report,
)


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
    assert payload["compiler_contract"]["lane"] == "gwb"
    assert payload["compiler_contract"]["evidence_bundle"]["source_family"] == "gwb_broader_review"
    assert any(row["role"] == "legal_linkage_graph" for row in payload["compiler_contract"]["derived_products"])
    assert payload["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert payload["promotion_gate"]["product_ref"] == "gwb_broader_review_v1"
    assert payload["review_claim_records"]
    assert all(row["lane"] == "gwb" for row in payload["review_claim_records"])
    assert all(row["family_id"] == "gwb_broader_review" for row in payload["review_claim_records"])
    assert all(row["state"] == "review_claim" for row in payload["review_claim_records"])
    assert all(row["state_basis"] == "source_review_row" for row in payload["review_claim_records"])
    assert all(row["evidence_status"] == "review_only" for row in payload["review_claim_records"])
    assert all(row["review_route"]["actionability"] == "must_review" for row in payload["review_claim_records"])
    relation_rows = [row for row in payload["review_claim_records"] if "proposition_relation" in row]
    assert relation_rows
    assert relation_rows[0]["target_proposition_identity"]["identity_basis"]["basis_kind"] == "seed_id"
    assert relation_rows[0]["target_proposition_identity"]["provenance"]["source_kind"] == "review_item_target"
    assert relation_rows[0]["proposition_relation"]["relation_kind"] == "addresses"
    assert relation_rows[0]["proposition_relation"]["target_proposition_id"] == relation_rows[0]["target_proposition_identity"]["proposition_id"]
    assert any("proposition_relation" not in row for row in payload["review_claim_records"])
    normalized_artifact = payload["suite_normalized_artifact"]
    assert normalized_artifact["schema_version"] == "itir.normalized.artifact.v1"
    assert normalized_artifact["artifact_role"] == "derived_product"
    assert normalized_artifact["authority"]["derived"] is True
    assert normalized_artifact["summary"]["lane"] == "gwb"
    assert normalized_artifact["summary"]["gate_decision"] == payload["promotion_gate"]["decision"]
    assert normalized_artifact["summary"]["workflow_stage"] == payload["workflow_summary"]["stage"]
    assert normalized_artifact["summary"]["recommended_view"] == payload["workflow_summary"]["recommended_view"]
    assert normalized_artifact["unresolved_pressure_status"] in {"none", "hold", "abstain"}
    reasoner_input_artifact = payload["reasoner_input_artifact"]
    assert reasoner_input_artifact["schema_version"] == "sl.reasoner_input.v0_1"
    assert reasoner_input_artifact["source_system"] == "SensibLaw"
    assert reasoner_input_artifact["source_lane"] == "gwb"
    assert reasoner_input_artifact["normalized_artifact"]["artifact_id"] == normalized_artifact["artifact_id"]
    assert reasoner_input_artifact["summary"]["gate_decision"] == payload["promotion_gate"]["decision"]
    assert payload["workflow_summary"]["stage"] in {"decide", "follow_up", "record", "archive"}
    assert payload["workflow_summary"]["recommended_view"] in {
        "legal_follow_graph",
        "source_review_rows",
        "summary",
        "archive_follow_rows",
    }
    assert payload["workflow_summary"]["counts"]["missing_review_count"] == summary["missing_review_count"]
    assert "debate_edge_count" in summary
    assert payload["workflow_summary"]["counts"]["debate_edge_count"] == summary["debate_edge_count"]
    assert summary["debate_edge_count"] > 0
    assert payload["workflow_summary"]["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert summary["review_item_count"] > 10
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
        "accepted": 39,
        "review_required": 14,
        "held": 0,
    }
    assert normalized["dominant_primary_workload"] == "linkage_pressure"
    assert normalized["primary_workload_counts"]["linkage_pressure"] == 8
    assert normalized["primary_workload_counts"]["event_or_time_pressure"] == 3
    assert normalized["candidate_signal_count"] == 46
    assert normalized["provisional_queue_row_count"] == 46
    assert normalized["provisional_bundle_count"] == 13
    assert normalized["review_required_source_ratio"] == 0.264151
    assert normalized["candidate_signal_density"] == 3.285714
    assert normalized["provisional_row_density"] == 3.285714
    assert normalized["provisional_bundle_density"] == 0.928571

    assert any(row["source_kind"] == "seed_family_support" for row in payload["source_review_rows"])
    assert any(row["source_kind"] == "merged_promoted_relation" for row in payload["source_review_rows"])
    assert any(row["source_kind"] == "source_family_summary" for row in payload["source_review_rows"])
    assert payload["legal_follow_graph"]["derived_only"] is True
    assert payload["legal_follow_graph"]["challengeable"] is True
    assert payload["legal_follow_graph"]["summary"]["seed_lane_count"] == summary["review_item_count"]
    assert payload["legal_follow_graph"]["summary"]["source_row_count"] == summary["source_row_count"]
    assert payload["legal_follow_graph"]["summary"]["source_row_node_count"] <= summary["source_row_count"]
    assert payload["legal_follow_graph"]["summary"]["source_family_count"] >= 1
    assert payload["legal_follow_graph"]["summary"]["source_kind_counts"].get("source_family_summary", 0) >= 1
    assert isinstance(payload["legal_follow_graph"]["summary"]["source_family_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["linkage_kind_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["review_status_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["support_kind_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["followed_source_cite_class_counts"], dict)
    assert payload["operator_views"]["legal_follow_graph"]["available"] is True
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["summary"], dict)
    assert payload["operator_views"]["legal_follow_graph"]["control_plane"]["version"] == "follow.control.v1"
    assert payload["operator_views"]["legal_follow_graph"]["control_plane"]["source_family"] == "gwb_legal_follow"
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["summary"]["route_target_counts"], dict)
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["summary"]["resolution_status_counts"], dict)
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["summary"]["priority_band_counts"], dict)
    assert payload["operator_views"]["legal_follow_graph"]["summary"]["highest_priority_score"] >= 0
    assert payload["operator_views"]["legal_follow_graph"]["summary"]["highest_authority_yield"] in {
        "high",
        "medium",
        "low",
    }
    if payload["operator_views"]["legal_follow_graph"]["summary"]["queue_count"] > 0:
        assert payload["workflow_summary"]["recommended_view"] in {
            "legal_follow_graph",
            "archive_follow_rows",
        }
    else:
        assert payload["workflow_summary"]["recommended_view"] == "source_review_rows"
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["queue"], list)
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["highlight_nodes"], list)
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["sample_edges"], list)
    if payload["operator_views"]["legal_follow_graph"]["queue"]:
        assert payload["operator_views"]["legal_follow_graph"]["queue"][0]["priority_rank"] == 1
    assert payload["related_review_clusters"]
    assert payload["provisional_review_rows"][0]["priority_rank"] == 1
    assert payload["provisional_review_bundles"][0]["bundle_rank"] == 1
    parliamentary_rows = [
        row for row in payload["source_review_rows"] if row.get("source_kind") == "parliamentary_statement"
    ]
    assert len(parliamentary_rows) == 2
    assert all(row["metadata"]["source_unit_id"].startswith("sourceunit:parliamentary") for row in parliamentary_rows)
    assert all(row.get("priority_score") == 5 for row in parliamentary_rows)
    assert all("operator_label" in row for row in parliamentary_rows)
    assert all(row["metadata"].get("ready_for_follow") is True for row in parliamentary_rows)
    assert any(
        anchor.get("anchor_kind") == "clause_label" for row in parliamentary_rows for anchor in row.get("candidate_anchors", [])
    )
    receipt_rows = [
        row for row in payload["source_review_rows"] if row.get("source_kind") == "uk_legislation_receipt"
    ]
    assert receipt_rows
    anchor_kinds = {anchor["anchor_kind"] for anchor in receipt_rows[0]["candidate_anchors"]}
    assert "section_label" in anchor_kinds
    assert "version" in anchor_kinds

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Broader Review" in summary_text
    assert "Derived Legal-Linkage Graph" in summary_text
    assert "Source kinds:" in summary_text
    assert "Linkage kinds:" in summary_text
    assert "Debate edges captured" in summary_text
    assert "Graph inspection" in summary_text
    assert "Sample typed links" in summary_text
    assert "Normalized Metrics" in summary_text
    assert "Top Provisional Review Bundles" in summary_text


def test_gwb_broader_review_consumes_shared_queueing_component() -> None:
    rows_src = inspect.getsource(module._build_provisional_rows)
    bundles_src = inspect.getsource(module._build_bundles)

    assert "_build_provisional_structured_anchors_impl" in rows_src
    assert "_build_provisional_anchor_bundles_impl" in bundles_src


def test_gwb_broader_review_world_model_report_rebinds_legal_follow_queue(tmp_path: Path) -> None:
    result = build_gwb_broader_review(tmp_path / "out")
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))

    report = build_gwb_broader_review_world_model_report(payload)

    assert report["schema_version"] == GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION
    assert report["family_id"] == "gwb_broader_review"
    assert report["lane_id"] == "gwb"
    assert report["summary"]["claim_count"] >= 1
    assert report["summary"]["must_review_count"] >= 1
    assert report["summary"]["queue_count"] == payload["operator_views"]["legal_follow_graph"]["summary"]["queue_count"]
    first_claim = report["claims"][0]
    assert first_claim["nat_claim"]["property"] == "legal_follow_target"
    assert first_claim["action_policy"]["actionability"] == "must_review"
