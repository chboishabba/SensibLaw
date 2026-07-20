from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .wikidata import build_wikidata_climate_review_demonstrator
from .wikidata_change_review import build_change_review_report_from_path
from .wikidata_disjointness import project_wikidata_disjointness_payload
from .wikidata_hotspot import generate_hotspot_cluster_pack, load_hotspot_manifest
from .wikidata_hotspot_eval import evaluate_hotspot_cluster_pack, load_hotspot_response_bundle
from .wikidata_latent_slice_graph import build_wikidata_latent_slice_graph
from .wikidata_nat_live_follow_executor import build_policy_risk_population_preview_preflight
from .wikidata_signal_review_bundle import (
    build_change_review_bundle,
    build_climate_review_bundle,
    build_disjointness_bundle,
    build_hotspot_eval_bundle,
    build_live_follow_preflight_bundle,
)
from .wikidata_zelph_lane_plan import build_adjacent_zelph_lane_plan
from .wikidata_zelph_lane_proof import build_disjointness_zelph_lane_proof


WIKIDATA_LANE_STATUS_SCHEMA_VERSION = "sl.wikidata_lane_status.v0_4"


def _sensiblaw_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return _sensiblaw_root().parent


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _lane_registry() -> list[dict[str, Any]]:
    return [
        {
            "lane_id": "climate_review_demonstrator",
            "lane_family": "climate_migration_review",
            "execution_surface": "sensiblaw wikidata climate-review-demonstrator",
            "evidence_mode": "repo-data-plus-fixture",
            "authority_posture": "review_only",
            "live_capable": False,
            "zelph_096_alignment": "adjacent",
            "dependency_class": "adjacent_live",
            "bundle_builder": build_climate_review_bundle,
            "notes": [
                "Bounded climate migration lane is runnable and stable on pinned artifacts.",
                "Zelph SPARQL can later widen candidate discovery, but this surface itself stays review-first.",
            ],
        },
        {
            "lane_id": "change_review_packet",
            "lane_family": "ontology_repair_review",
            "execution_surface": "sensiblaw wikidata compare-candidates",
            "evidence_mode": "fixture-backed",
            "authority_posture": "review_only",
            "live_capable": False,
            "zelph_096_alignment": "none",
            "dependency_class": "review_geometry",
            "bundle_builder": build_change_review_bundle,
            "notes": [
                "Current change-review lane is deterministic and in-memory only.",
                "It remains useful for bounded ontology repair comparisons without claiming edit authority.",
            ],
        },
        {
            "lane_id": "disjointness_report",
            "lane_family": "p2738_qualifier_disjointness",
            "execution_surface": "sensiblaw wikidata disjointness-report",
            "evidence_mode": "fixture-backed-real-slice",
            "authority_posture": "diagnostic_only",
            "live_capable": False,
            "zelph_096_alignment": "direct",
            "dependency_class": "direct_zelph",
            "bundle_builder": build_disjointness_bundle,
            "notes": [
                "This is the clearest direct beneficiary of Zelph 0.9.6 qualifier import plus SPARQL property paths.",
                "Repo proof is local and bounded today; full WD shard-native proof still depends on the published HF manifest/index entrypoints.",
            ],
        },
        {
            "lane_id": "hotspot_eval",
            "lane_family": "structural_hotspot_review",
            "execution_surface": "sensiblaw wikidata hotspot-eval",
            "evidence_mode": "fixture-backed",
            "authority_posture": "review_only",
            "live_capable": False,
            "zelph_096_alignment": "none",
            "dependency_class": "review_geometry",
            "bundle_builder": build_hotspot_eval_bundle,
            "notes": [
                "Hotspot evaluation is stable, but it is not the main Zelph integration pressure point.",
                "Best treated as a reviewer-geometry lane rather than a graph-query lane.",
            ],
        },
        {
            "lane_id": "nat_live_follow_preflight",
            "lane_family": "bounded_live_follow",
            "execution_surface": "sensiblaw wikidata nat-live-follow-preflight",
            "evidence_mode": "fixture-backed-live-shaped",
            "authority_posture": "review_only",
            "live_capable": True,
            "zelph_096_alignment": "adjacent",
            "dependency_class": "adjacent_live",
            "bundle_builder": build_live_follow_preflight_bundle,
            "notes": [
                "This is the only currently executable lane here that is explicitly live-oriented.",
                "It complements Zelph-backed discovery, but it does not itself require Zelph to run.",
            ],
        },
    ]


def _load_lane_reports() -> dict[str, dict[str, Any]]:
    sensiblaw_root = _sensiblaw_root()
    repo_root = _repo_root()
    fixture_root = sensiblaw_root / "tests" / "fixtures" / "wikidata"
    climate_root = (
        sensiblaw_root
        / "data"
        / "ontology"
        / "wikidata_migration_packs"
        / "p5991_p14143_climate_pilot_20260328"
    )

    migration_pack = _read_json(climate_root / "migration_pack.json")
    climate_text = _read_json(
        climate_root / "climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json"
    )
    review_packet = _read_json(fixture_root / "wikidata_nat_review_packet_20260401.json")
    climate_report = build_wikidata_climate_review_demonstrator(
        migration_pack,
        climate_text_payload=climate_text,
        review_packet=review_packet,
    )
    change_review_report = build_change_review_report_from_path(
        fixture_root / "q27968055_change_review_packet.json"
    )
    disjointness_report = project_wikidata_disjointness_payload(
        _read_json(
            fixture_root / "disjointness_p2738_fixed_construction_real_pack_v1" / "slice.json"
        )
    )
    hotspot_manifest = load_hotspot_manifest(
        repo_root / "docs" / "planning" / "wikidata_hotspot_pilot_pack_v1.manifest.json"
    )
    hotspot_pack = generate_hotspot_cluster_pack(
        hotspot_manifest,
        repo_root=repo_root,
        pack_ids=["software_entity_kind_collapse_pack_v0"],
    )
    hotspot_eval = evaluate_hotspot_cluster_pack(
        hotspot_pack,
        load_hotspot_response_bundle(
            fixture_root
            / "hotspot_eval_v1"
            / "software_entity_kind_collapse_pack_v0_responses_inconsistent.json"
        ),
    )
    live_follow_preflight = build_policy_risk_population_preview_preflight(
        _read_json(fixture_root / "wikidata_nat_live_follow_campaign_20260403.json")
    )
    return {
        "climate_review_demonstrator": climate_report,
        "change_review_packet": change_review_report,
        "disjointness_report": disjointness_report,
        "hotspot_eval": hotspot_eval,
        "nat_live_follow_preflight": live_follow_preflight,
    }


def _observed_summary(lane_id: str, report: Mapping[str, Any]) -> dict[str, Any]:
    if lane_id == "climate_review_demonstrator":
        return {
            "entity_qid": report["inputs"]["entity_qid"],
            "candidate_count": report["candidate_change_surface"]["candidate_count"],
            "final_state": report["review_disposition"]["final_state"],
            "bridge_case_count": report["residual_completeness_surface"]["bridge_case_count"],
        }
    if lane_id == "change_review_packet":
        candidate_reports = report.get("candidate_reports", [])
        return {
            "focus_item": report["focus_item"],
            "candidate_count": len(candidate_reports),
            "checked_safe_reviewable_count": sum(
                1
                for row in candidate_reports
                if isinstance(row, Mapping) and row.get("disposition") == "checked_safe_reviewable"
            ),
            "held_count": sum(
                1
                for row in candidate_reports
                if isinstance(row, Mapping) and row.get("disposition") == "held"
            ),
        }
    if lane_id == "disjointness_report":
        return {
            "source_window_id": report["source_window_id"],
            "disjoint_pair_count": report["review_summary"]["disjoint_pair_count"],
            "subclass_violation_count": report["subclass_violation_count"],
            "instance_violation_count": report["instance_violation_count"],
            "culprit_class_count": report["review_summary"]["culprit_class_count"],
        }
    if lane_id == "hotspot_eval":
        return {
            "pack_count": len(report.get("selected_pack_ids", [])),
            "cluster_total": report["summary"]["cluster_counts"]["total"],
            "inconsistent_cluster_count": report["summary"]["cluster_counts"]["inconsistent"],
        }
    return {
        "campaign_id": report["campaign_id"],
        "candidate_count": report["candidate_count"],
        "top_n": report["top_n"],
        "coverage_counts": report["coverage_counts"],
    }


def build_wikidata_lane_artifacts() -> dict[str, dict[str, Any]]:
    reports = _load_lane_reports()
    artifacts: dict[str, dict[str, Any]] = {}
    for lane in _lane_registry():
        lane_id = lane["lane_id"]
        report = reports[lane_id]
        bundle = lane["bundle_builder"](
            report=report,
            lane_id=lane_id,
            lane_family=lane["lane_family"],
            authority_posture=lane["authority_posture"],
            evidence_mode=lane["evidence_mode"],
            execution_surface=lane["execution_surface"],
        )
        latent_slice_graph = build_wikidata_latent_slice_graph(bundle)
        zelph_lane_plan = None
        zelph_lane_proof = None
        if lane["dependency_class"] == "adjacent_live":
            zelph_lane_plan = build_adjacent_zelph_lane_plan(
                report=report,
                bundle=bundle,
                latent_slice_graph=latent_slice_graph,
                lane_id=lane_id,
                lane_family=lane["lane_family"],
                execution_surface=lane["execution_surface"],
            )
        if lane_id == "disjointness_report":
            zelph_lane_proof = build_disjointness_zelph_lane_proof(
                report=report,
                bundle=bundle,
                latent_slice_graph=latent_slice_graph,
                lane_id=lane_id,
                lane_family=lane["lane_family"],
                execution_surface=lane["execution_surface"],
            )
        artifacts[lane_id] = {
            "lane_id": lane_id,
            "lane_family": lane["lane_family"],
            "execution_surface": lane["execution_surface"],
            "evidence_mode": lane["evidence_mode"],
            "authority_posture": lane["authority_posture"],
            "live_capable": lane["live_capable"],
            "zelph_096_alignment": lane["zelph_096_alignment"],
            "dependency_class": lane["dependency_class"],
            "observed": _observed_summary(lane_id, report),
            "notes": list(lane["notes"]),
            "report": report,
            "normalized_bundle": bundle,
            "latent_slice_graph": latent_slice_graph,
            "zelph_lane_plan": zelph_lane_plan,
            "zelph_lane_proof": zelph_lane_proof,
        }
    return artifacts


def build_wikidata_lane_bundle(lane_id: str) -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    if lane_id not in artifacts:
        raise ValueError(f"unknown Wikidata lane: {lane_id}")
    return artifacts[lane_id]["normalized_bundle"]


def build_wikidata_lane_graph(lane_id: str) -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    if lane_id not in artifacts:
        raise ValueError(f"unknown Wikidata lane: {lane_id}")
    return artifacts[lane_id]["latent_slice_graph"]


def build_wikidata_lane_proof(lane_id: str) -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    if lane_id not in artifacts:
        raise ValueError(f"unknown Wikidata lane: {lane_id}")
    proof = artifacts[lane_id].get("zelph_lane_proof")
    if not isinstance(proof, Mapping):
        raise ValueError(f"lane does not expose a direct Zelph proof surface: {lane_id}")
    return dict(proof)


def build_wikidata_lane_plan(lane_id: str) -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    if lane_id not in artifacts:
        raise ValueError(f"unknown Wikidata lane: {lane_id}")
    plan = artifacts[lane_id].get("zelph_lane_plan")
    if not isinstance(plan, Mapping):
        raise ValueError(f"lane does not expose an adjacent Zelph plan surface: {lane_id}")
    return dict(plan)


def build_wikidata_lane_status() -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    lanes = []
    for lane_id in sorted(artifacts):
        artifact = artifacts[lane_id]
        bundle = artifact["normalized_bundle"]
        latent_slice_graph = artifact["latent_slice_graph"]
        zelph_lane_plan = artifact.get("zelph_lane_plan")
        zelph_lane_proof = artifact.get("zelph_lane_proof")
        lanes.append(
            {
                "lane_id": artifact["lane_id"],
                "lane_family": artifact["lane_family"],
                "status": "ok",
                "execution_surface": artifact["execution_surface"],
                "evidence_mode": artifact["evidence_mode"],
                "authority_posture": artifact["authority_posture"],
                "live_capable": artifact["live_capable"],
                "zelph_096_alignment": artifact["zelph_096_alignment"],
                "dependency_class": artifact["dependency_class"],
                "observed": dict(artifact["observed"]),
                "normalized_bundle_summary": {
                    "schema_version": bundle["schema_version"],
                    "promotion_status": bundle["promotion_status"],
                    "signal_kind": bundle["signal_kind"],
                    "authority_surface": bundle["authority_surface"],
                    "summary": dict(bundle["summary"]),
                },
                "latent_slice_graph_summary": {
                    "schema_version": latent_slice_graph["schema_version"],
                    "flatness_posture": latent_slice_graph["flatness_indicators"]["flatness_posture"],
                    "node_count": latent_slice_graph["diagnostics"]["metrics"]["node_count"],
                    "edge_count": latent_slice_graph["diagnostics"]["metrics"]["edge_count"],
                    "node_kind_counts": dict(
                        latent_slice_graph["diagnostics"]["distributions"]["node_kind_counts"]
                    ),
                },
                **(
                    {
                        "zelph_lane_plan_summary": {
                            "schema_version": zelph_lane_plan["schema_version"],
                            "plan_scope": zelph_lane_plan["plan_scope"],
                            "zelph_role": zelph_lane_plan["zelph_role"],
                            "overall_status": zelph_lane_plan["readiness"]["overall_status"],
                            "hosted_wd_dependency_status": zelph_lane_plan["readiness"][
                                "hosted_wd_dependency_status"
                            ],
                            "query_pressure_count": len(zelph_lane_plan["query_pressures"]),
                        }
                    }
                    if isinstance(zelph_lane_plan, Mapping)
                    else {}
                ),
                **(
                    {
                        "zelph_lane_proof_summary": {
                            "schema_version": zelph_lane_proof["schema_version"],
                            "proof_scope": zelph_lane_proof["proof_scope"],
                            "overall_status": zelph_lane_proof["acceptance"]["overall_status"],
                            "hosted_wd_acceptance_status": zelph_lane_proof["acceptance"][
                                "hosted_wd_acceptance_status"
                            ],
                            "transport_manifest_version": zelph_lane_proof["transport_artifact"]["summary"][
                                "manifest_version"
                            ],
                            "selected_shard_count": zelph_lane_proof["transport_artifact"]["summary"][
                                "selected_shard_count"
                            ],
                        }
                    }
                    if isinstance(zelph_lane_proof, Mapping)
                    else {}
                ),
                "notes": list(artifact["notes"]),
            }
        )

    direct_alignments = {
        row["lane_id"]
        for row in lanes
        if row["zelph_096_alignment"] == "direct"
    }
    dependency_class_counts: dict[str, int] = {}
    for row in lanes:
        dependency_class = row["dependency_class"]
        dependency_class_counts[dependency_class] = dependency_class_counts.get(dependency_class, 0) + 1
    bounded_local_direct_zelph = [
        row["lane_id"]
        for row in lanes
        if row.get("zelph_lane_proof_summary", {}).get("overall_status") == "bounded_local_ready"
    ]
    adjacent_parallel_ready = [
        row["lane_id"]
        for row in lanes
        if row.get("zelph_lane_plan_summary", {}).get("overall_status") == "ready_for_parallel_discovery"
    ]
    hosted_wd_pending = [
        row["lane_id"]
        for row in lanes
        if row.get("zelph_lane_proof_summary", {}).get("hosted_wd_acceptance_status")
        == "pending_manifest_alignment"
    ]
    return {
        "schema_version": WIKIDATA_LANE_STATUS_SCHEMA_VERSION,
        "summary": {
            "lane_count": len(lanes),
            "ok_lane_count": len(lanes),
            "live_capable_lane_count": sum(1 for row in lanes if row["live_capable"]),
            "fixture_backed_lane_count": sum(1 for row in lanes if "fixture" in str(row["evidence_mode"])),
            "direct_zelph_096_lane_count": len(direct_alignments),
            "direct_zelph_096_lane_ids": sorted(direct_alignments),
            "bounded_local_direct_zelph_lane_count": len(bounded_local_direct_zelph),
            "bounded_local_direct_zelph_lane_ids": sorted(bounded_local_direct_zelph),
            "adjacent_zelph_plan_lane_count": len(adjacent_parallel_ready),
            "adjacent_zelph_plan_lane_ids": sorted(adjacent_parallel_ready),
            "hosted_wd_pending_lane_count": len(hosted_wd_pending),
            "hosted_wd_pending_lane_ids": sorted(hosted_wd_pending),
            "dependency_class_counts": dependency_class_counts,
        },
        "lanes": lanes,
    }


__all__ = [
    "WIKIDATA_LANE_STATUS_SCHEMA_VERSION",
    "build_wikidata_lane_artifacts",
    "build_wikidata_lane_bundle",
    "build_wikidata_lane_graph",
    "build_wikidata_lane_plan",
    "build_wikidata_lane_proof",
    "build_wikidata_lane_status",
]
