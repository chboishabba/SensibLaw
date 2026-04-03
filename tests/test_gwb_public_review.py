from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_gwb_public_review as module
from scripts.build_gwb_public_review import ARTIFACT_VERSION, build_gwb_public_review
from src.policy.gwb_legal_follow_graph import build_gwb_legal_follow_operator_view
from src.policy.gwb_legal_follow_graph import build_gwb_legal_follow_graph
from src.sources.eur_lex_adapter import CELEX_METADATA


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
    assert payload["compiler_contract"]["lane"] == "gwb"
    assert payload["compiler_contract"]["evidence_bundle"]["source_family"] == "gwb_public_review"
    assert any(row["role"] == "legal_linkage_graph" for row in payload["compiler_contract"]["derived_products"])
    assert payload["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert payload["promotion_gate"]["product_ref"] == "gwb_public_review_v1"
    assert payload["workflow_summary"]["stage"] in {"decide", "follow_up", "record"}
    assert payload["workflow_summary"]["recommended_view"] in {"legal_follow_graph", "source_review_rows", "summary"}
    assert payload["workflow_summary"]["counts"]["missing_review_count"] == summary["missing_review_count"]
    assert payload["workflow_summary"]["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
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
    assert payload["legal_follow_graph"]["derived_only"] is True
    assert payload["legal_follow_graph"]["challengeable"] is True
    assert payload["legal_follow_graph"]["summary"]["seed_lane_count"] == summary["review_item_count"]
    assert payload["legal_follow_graph"]["summary"]["source_row_count"] == summary["source_row_count"]
    assert payload["legal_follow_graph"]["summary"]["source_row_node_count"] <= summary["source_row_count"]
    assert payload["legal_follow_graph"]["summary"]["node_count"] > summary["review_item_count"]
    assert payload["legal_follow_graph"]["summary"]["edge_count"] >= summary["source_row_count"]
    assert payload["legal_follow_graph"]["summary"]["source_kind_counts"].get("gwb_seed_event", 0) >= 1
    assert isinstance(payload["legal_follow_graph"]["summary"]["source_family_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["linkage_kind_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["review_status_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["support_kind_label_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["followed_source_kind_counts"], dict)
    assert isinstance(payload["legal_follow_graph"]["summary"]["followed_source_receipt_kind_counts"], dict)
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
        assert payload["workflow_summary"]["recommended_view"] == "legal_follow_graph"
    else:
        assert payload["workflow_summary"]["recommended_view"] == "source_review_rows"
    assert isinstance(payload["operator_views"]["legal_follow_graph"]["queue"], list)
    highlight_nodes = payload["operator_views"]["legal_follow_graph"]["highlight_nodes"]
    sample_edges = payload["operator_views"]["legal_follow_graph"]["sample_edges"]
    assert isinstance(highlight_nodes, list)
    assert isinstance(sample_edges, list)
    assert highlight_nodes
    allowed_kinds = {"source_family", "linkage_kind", "support_kind", "review_status", "predicate"}
    assert all(node["kind"] in allowed_kinds for node in highlight_nodes)
    assert all(node["label"] for node in highlight_nodes)
    assert all(edge["source"] for edge in sample_edges)
    assert all(edge["target"] for edge in sample_edges)
    assert payload["provisional_anchor_bundles"][0]["bundle_rank"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "GWB Public Review" in summary_text
    assert "Derived Legal-Linkage Graph" in summary_text
    assert "Source kinds:" in summary_text
    assert "Linkage kinds:" in summary_text
    assert "Graph inspection" in summary_text
    assert "Sample typed links" in summary_text
    assert "Normalized Metrics" in summary_text
    assert "Provisional Anchor Bundles" in summary_text


def test_gwb_public_review_consumes_shared_anchor_queueing_component() -> None:
    rank_src = inspect.getsource(module._rank_provisional_rows)
    bundle_src = inspect.getsource(module._bundle_provisional_rows)

    assert "_build_provisional_structured_anchors_impl" in rank_src
    assert "_build_provisional_anchor_bundles_impl" in bundle_src


def test_build_gwb_legal_follow_operator_view_handles_missing_graph() -> None:
    view = build_gwb_legal_follow_operator_view({"nodes": [], "edges": [], "summary": {}})

    assert view["available"] is False
    assert view["highlight_nodes"] == []
    assert view["sample_edges"] == []
    assert view["summary"]["queue_count"] == 0
    assert view["queue"] == []
    assert view["control_plane"]["source_family"] == "gwb_legal_follow"


def test_gwb_legal_follow_graph_collects_followed_source_receipts() -> None:
    review_items = [
        {
            "seed_id": "seed-a",
            "action_summary": "Sample action",
            "linkage_kind": "linkage",
            "support_kinds": [],
            "review_statuses": [],
        }
    ]
    source_rows = [
        {
            "seed_id": "seed-a",
            "source_kind": "gwb_seed_event",
            "source_row_id": "row-a",
            "text": "Context",
            "review_status": "missing_review",
            "candidate_anchors": [],
            "receipts": [
                {"kind": "source_link", "value": "https://example.com/article"},
            ],
        }
    ]
    graph = build_gwb_legal_follow_graph(
        review_item_rows=review_items,
        source_review_rows=source_rows,
    )
    summary = graph["summary"]
    expected_count = 1 + len(CELEX_METADATA)
    assert summary["followed_source_count"] == expected_count
    assert graph["summary"]["followed_source_kind_counts"].get("https://example.com/article", 0) == 1
    assert graph["summary"]["followed_source_receipt_kind_counts"].get("source_link", 0) == 1
    assert graph["summary"]["followed_source_cite_class_counts"].get("general", 0) == 1
    assert graph["summary"]["followed_source_cite_class_counts"].get("eur_lex", 0) == len(CELEX_METADATA)
    assert any(node["kind"] == "followed_source" for node in graph["nodes"])


def test_gwb_legal_follow_graph_classifies_brexit_legal_cites_from_urls() -> None:
    graph = build_gwb_legal_follow_graph(
        review_item_rows=[
            {
                "seed_id": "seed-b",
                "action_summary": "Brexit action",
                "linkage_kind": "legal_interaction",
                "support_kinds": [],
                "review_statuses": [],
            }
        ],
        source_review_rows=[
            {
                "seed_id": "seed-b",
                "source_kind": "gwb_seed_event",
                "source_row_id": "row-b",
                "text": "Brexit litigation around the European Union (Withdrawal) Act and Article 50",
                "review_status": "missing_review",
                "candidate_anchors": [],
                "receipts": [
                    {"kind": "source_link", "value": "https://www.legislation.gov.uk/ukpga/2018/16/contents/enacted"},
                    {"kind": "source_link", "value": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:12012M050"},
                ],
            }
        ],
    )
    summary = graph["summary"]
    assert summary["followed_source_cite_class_counts"].get("uk_legislation", 0) == 1
    assert summary["followed_source_cite_class_counts"].get("eur_lex", 0) == 1
    assert summary["brexit_related_follow_count"] == 2
    operator_view = build_gwb_legal_follow_operator_view(graph)
    assert operator_view["summary"]["queue_count"] == 2
    assert operator_view["summary"]["route_target_counts"]["uk_legislation_follow"] == 1
    assert operator_view["summary"]["route_target_counts"]["eur_lex_follow"] == 1
    assert operator_view["summary"]["priority_band_counts"]["high"] == 2
    assert operator_view["summary"]["highest_priority_score"] >= 8
    assert operator_view["summary"]["highest_authority_yield"] == "high"


def test_gwb_legal_follow_graph_adds_deterministic_eur_lex_nodes_when_missing() -> None:
    graph = build_gwb_legal_follow_graph(
        review_item_rows=[
            {
                "seed_id": "seed-eur",
                "action_summary": "EUR-Lex seed",
                "linkage_kind": "default",
                "support_kinds": [],
                "review_statuses": [],
            }
        ],
        source_review_rows=[],
    )
    summary = graph["summary"]
    eur_counts = summary["followed_source_cite_class_counts"].get("eur_lex", 0)
    assert eur_counts == len(CELEX_METADATA)
    operator_view = build_gwb_legal_follow_operator_view(graph)
    assert operator_view["summary"]["route_target_counts"].get("eur_lex_follow", 0) == len(CELEX_METADATA)


def test_live_eur_lex_nodes_expose_resolution_metadata(monkeypatch) -> None:
    class DummyResponse:
        status_code = 200

        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> DummyResponse:
        return DummyResponse("<html><title>Live EUR-Lex Title</title></html>")

    monkeypatch.setenv("SENSIBLAW_EUR_LEX_LIVE", "1")
    monkeypatch.setattr("requests.get", fake_get)
    graph = build_gwb_legal_follow_graph(
        review_item_rows=[
            {
                "seed_id": "seed-live",
                "action_summary": "live check",
                "linkage_kind": "default",
                "support_kinds": [],
                "review_statuses": [],
            }
        ],
        source_review_rows=[],
    )
    live_nodes = [
        node
        for node in graph.get("nodes", [])
        if node.get("kind") == "followed_source" and node.get("metadata", {}).get("resolution_mode") == "live"
    ]
    assert live_nodes, "Live nodes should be present when live mode is enabled"
    assert any(node.get("metadata", {}).get("live_title") == "Live EUR-Lex Title" for node in live_nodes)
    operator_view = build_gwb_legal_follow_operator_view(graph)
    queue = operator_view["queue"]
    assert queue, "Queue should include live-driven entries"
    assert all(row.get("priority_score") is not None for row in queue), "Every queue row must carry a priority"
    assert operator_view["queue"][0]["resolution_status"] == "open"
    assert operator_view["queue"][0]["priority_rank"] == 1
    assert operator_view["queue"][0]["priority_score"] >= operator_view["queue"][1]["priority_score"]
    assert operator_view["queue"][0]["authority_yield"] == "high"
    assert any(row["label"] == "Authority yield" for row in operator_view["queue"][0]["detail_rows"])
    assert any(row["label"] == "Brexit related" for row in operator_view["queue"][0]["detail_rows"])


def test_gwb_legal_follow_graph_seeds_foundation_source_receipts_from_brexit_titles() -> None:
    graph = build_gwb_legal_follow_graph(
        review_item_rows=[
            {
                "seed_id": "seed-c",
                "action_summary": "Brexit proving ground",
                "linkage_kind": "legal_interaction",
                "support_kinds": [],
                "review_statuses": [],
            }
        ],
        source_review_rows=[
            {
                "seed_id": "seed-c",
                "source_kind": "source_family_summary",
                "source_row_id": "row-c",
                "text": "Brexit pressure around the European Union (Withdrawal) Act 2018 (UK) and Treaty on European Union",
                "review_status": "missing_review",
                "candidate_anchors": [],
                "receipts": [],
            }
        ],
    )
    summary = graph["summary"]
    assert summary["followed_source_receipt_kind_counts"].get("foundation_source_reference", 0) == 2
    assert summary["followed_source_cite_class_counts"].get("uk_legislation", 0) == 1
    assert summary["followed_source_cite_class_counts"].get("eur_lex", 0) == 1
