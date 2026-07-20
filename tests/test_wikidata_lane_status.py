from __future__ import annotations

from src.ontology.wikidata_lane_flatness_audit import build_wikidata_lane_flatness_audit
from src.ontology.wikidata_lane_status import (
    WIKIDATA_LANE_STATUS_SCHEMA_VERSION,
    build_wikidata_lane_bundle,
    build_wikidata_lane_graph,
    build_wikidata_lane_plan,
    build_wikidata_lane_proof,
    build_wikidata_lane_status,
)


def test_wikidata_lane_status_runs_real_lane_builders_and_classifies_dependencies() -> None:
    report = build_wikidata_lane_status()

    assert report["schema_version"] == WIKIDATA_LANE_STATUS_SCHEMA_VERSION
    assert report["summary"] == {
        "lane_count": 5,
        "ok_lane_count": 5,
        "live_capable_lane_count": 1,
        "fixture_backed_lane_count": 5,
        "direct_zelph_096_lane_count": 1,
        "direct_zelph_096_lane_ids": ["disjointness_report"],
        "bounded_local_direct_zelph_lane_count": 1,
        "bounded_local_direct_zelph_lane_ids": ["disjointness_report"],
        "adjacent_zelph_plan_lane_count": 2,
        "adjacent_zelph_plan_lane_ids": [
            "climate_review_demonstrator",
            "nat_live_follow_preflight",
        ],
        "hosted_wd_pending_lane_count": 1,
        "hosted_wd_pending_lane_ids": ["disjointness_report"],
        "dependency_class_counts": {
            "adjacent_live": 2,
            "direct_zelph": 1,
            "review_geometry": 2,
        },
    }

    by_id = {row["lane_id"]: row for row in report["lanes"]}
    assert set(by_id) == {
        "change_review_packet",
        "climate_review_demonstrator",
        "disjointness_report",
        "hotspot_eval",
        "nat_live_follow_preflight",
    }
    assert by_id["disjointness_report"]["dependency_class"] == "direct_zelph"
    assert by_id["nat_live_follow_preflight"]["dependency_class"] == "adjacent_live"
    assert by_id["hotspot_eval"]["dependency_class"] == "review_geometry"
    assert by_id["disjointness_report"]["normalized_bundle_summary"]["promotion_status"] == "candidate_only"
    assert by_id["disjointness_report"]["latent_slice_graph_summary"]["flatness_posture"] == "projection_flat"
    assert by_id["disjointness_report"]["zelph_lane_proof_summary"] == {
        "schema_version": "sl.wikidata_zelph_lane_proof.v0_1",
        "proof_scope": "bounded_local_direct_zelph",
        "overall_status": "bounded_local_ready",
        "hosted_wd_acceptance_status": "pending_manifest_alignment",
        "transport_manifest_version": "zelph-hf-layout/v2",
        "selected_shard_count": 5,
    }
    assert by_id["climate_review_demonstrator"]["zelph_lane_plan_summary"] == {
        "schema_version": "sl.wikidata_zelph_lane_plan.v0_1",
        "plan_scope": "bounded_adjacent_zelph_discovery",
        "zelph_role": "candidate_discovery_and_migration_confirmation",
        "overall_status": "ready_for_parallel_discovery",
        "hosted_wd_dependency_status": "not_blocking",
        "query_pressure_count": 3,
    }
    assert by_id["nat_live_follow_preflight"]["zelph_lane_plan_summary"] == {
        "schema_version": "sl.wikidata_zelph_lane_plan.v0_1",
        "plan_scope": "bounded_adjacent_zelph_discovery",
        "zelph_role": "follow_target_confirmation_and_queue_pressure",
        "overall_status": "ready_for_parallel_discovery",
        "hosted_wd_dependency_status": "not_blocking",
        "query_pressure_count": 2,
    }
    assert by_id["hotspot_eval"]["latent_slice_graph_summary"]["flatness_posture"] == "projection_flat"


def test_wikidata_lane_bundle_emits_shared_review_contract() -> None:
    bundle = build_wikidata_lane_bundle("disjointness_report")

    assert bundle["schema_version"] == "sl.wikidata_signal_review_bundle.v0_1"
    assert bundle["lane_id"] == "disjointness_report"
    assert bundle["signal_kind"] == "structural"
    assert bundle["authority_surface"] == "wikidata"
    assert bundle["soft_type_strength"] == "receipt_backed"
    assert bundle["promotion_status"] == "candidate_only"
    assert bundle["summary"] == {
        "candidate_entity_count": 4,
        "candidate_property_count": 4,
        "residual_count": 2,
        "receipt_count": 2,
    }
    assert bundle["dependency_cone"]["focus_pids"] == ["P2738", "P11260", "P279", "P31"]


def test_wikidata_lane_graph_emits_latent_slice_graph_and_flatness_indicators() -> None:
    graph = build_wikidata_lane_graph("disjointness_report")

    assert graph["schema_version"] == "sl.wikidata_latent_slice_graph.v0_1"
    assert graph["lane_id"] == "disjointness_report"
    assert graph["flatness_indicators"]["flatness_posture"] == "projection_flat"
    assert graph["diagnostics"]["metrics"]["node_count"] == 13
    assert graph["diagnostics"]["metrics"]["edge_count"] == 12
    assert graph["diagnostics"]["distributions"]["node_kind_counts"] == {
        "candidate_entity": 4,
        "candidate_property": 4,
        "lane": 1,
        "residual": 2,
        "receipt": 2,
    }
    assert graph["emission_diagnostics"] == {
        "emitted_node_count": 13,
        "emitted_edge_count": 12,
        "unique_node_count": 13,
        "duplicate_node_id_count": 0,
        "duplicate_node_emission_count": 0,
        "duplicate_node_ids": {},
    }


def test_wikidata_lane_flatness_audit_flags_projection_loss_before_renderer_work() -> None:
    audit = build_wikidata_lane_flatness_audit()

    assert audit["schema_version"] == "sl.wikidata_lane_flatness_audit.v0_1"
    assert audit["summary"] == {
        "lane_count": 5,
        "projection_flat_lane_count": 5,
        "projection_flat_lane_ids": [
            "change_review_packet",
            "climate_review_demonstrator",
            "disjointness_report",
            "hotspot_eval",
            "nat_live_follow_preflight",
        ],
        "structured_lane_count": 0,
        "structured_lane_ids": [],
        "duplicate_identity_lane_count": 1,
        "duplicate_identity_lane_ids": ["hotspot_eval"],
        "renderer_ready_lane_count": 0,
        "renderer_ready_lane_ids": [],
        "renderer_followup_status": "defer_to_itir_svelte_priority_list",
        "primary_owner": "data_projection_diagnostics",
    }
    by_id = {row["lane_id"]: row for row in audit["lanes"]}
    assert by_id["hotspot_eval"]["non_visual_diagnosis"] == "projection_identity_collapse"
    assert by_id["hotspot_eval"]["emission_diagnostics"] == {
        "emitted_node_count": 20,
        "emitted_edge_count": 19,
        "unique_node_count": 13,
        "duplicate_node_id_count": 1,
        "duplicate_node_emission_count": 7,
        "duplicate_node_ids": {
            "property:entity_kind_collapse:hotspot_family": 8,
        },
    }
    assert by_id["hotspot_eval"]["renderer_followup_status"] == "defer_to_itir_svelte_priority_list"
    assert by_id["disjointness_report"]["non_visual_diagnosis"] == "star_projection_shallow"


def test_wikidata_lane_proof_emits_bounded_direct_zelph_surface() -> None:
    proof = build_wikidata_lane_proof("disjointness_report")

    assert proof["schema_version"] == "sl.wikidata_zelph_lane_proof.v0_1"
    assert proof["lane_id"] == "disjointness_report"
    assert proof["proof_scope"] == "bounded_local_direct_zelph"
    assert proof["required_property_scope"] == ["P2738", "P11260", "P279", "P31"]
    assert proof["required_features"] == [
        "qualifier-import",
        "sparql-subset",
        "transitive-property-paths",
        "partial-loading",
        "node-route-selection",
    ]
    assert proof["acceptance"] == {
        "bounded_semantics_status": "proven",
        "partial_load_contract_status": "proven",
        "hosted_wd_acceptance_status": "pending_manifest_alignment",
        "overall_status": "bounded_local_ready",
    }
    assert proof["semantic_receipt"] == {
        "source_window_id": "real_fixed_construction_2026_03_25",
        "disjoint_pair_count": 1,
        "subclass_violation_count": 4,
        "instance_violation_count": 0,
        "culprit_class_count": 1,
        "culprit_item_count": 0,
    }
    assert proof["transport_artifact"]["summary"]["manifest_version"] == "zelph-hf-layout/v2"
    assert proof["transport_artifact"]["summary"]["selected_shard_count"] == 5
    assert proof["transport_artifact"]["review_packet_projection"]["transport_capabilities"] == {
        "manifest_version": "zelph-hf-layout/v2",
        "transport_primary": "hf-object-fetch",
        "node_route_index": True,
        "selected_chunk_read": True,
        "supported_operations": ["header-probe", "selected-chunk-read", "node-route", "sparql-subset"],
        "supported_sections": ["left", "right", "nameOfNode", "nodeOfName"],
        "backend_capabilities": {
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": True,
            "qualifier_import_ready": True,
            "property_path_ready": True,
        },
    }


def test_wikidata_lane_plan_emits_adjacent_zelph_surface_for_climate_lane() -> None:
    plan = build_wikidata_lane_plan("climate_review_demonstrator")

    assert plan["schema_version"] == "sl.wikidata_zelph_lane_plan.v0_1"
    assert plan["lane_id"] == "climate_review_demonstrator"
    assert plan["plan_scope"] == "bounded_adjacent_zelph_discovery"
    assert plan["zelph_role"] == "candidate_discovery_and_migration_confirmation"
    assert plan["focus_entities"] == ["Q10403939"]
    assert plan["focus_properties"] == ["P5991", "P14143"]
    assert plan["readiness"] == {
        "normalized_bundle_status": "available",
        "latent_slice_graph_status": "available",
        "zelph_dependency_status": "adjacent_optional",
        "hosted_wd_dependency_status": "not_blocking",
        "overall_status": "ready_for_parallel_discovery",
    }
    assert [row["pressure_id"] for row in plan["query_pressures"]] == [
        "source_property_broadening",
        "migration_target_confirmation",
        "split_pressure_context",
    ]
    assert plan["query_pressures"][0]["bounded_receipt"] == {
        "candidate_count": 24,
        "held_candidate_count": 24,
    }
    assert plan["query_pressures"][1]["bounded_receipt"] == {
        "review_final_state": "held",
        "promotable_candidate_count": 0,
    }
