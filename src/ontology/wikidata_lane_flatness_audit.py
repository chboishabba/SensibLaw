from __future__ import annotations

from typing import Any, Mapping

from .wikidata_lane_status import build_wikidata_lane_artifacts


WIKIDATA_LANE_FLATNESS_AUDIT_SCHEMA_VERSION = "sl.wikidata_lane_flatness_audit.v0_1"


def _lane_non_visual_diagnosis(
    *,
    flatness_posture: str,
    branching_factor: float,
    duplicate_node_emission_count: int,
) -> str:
    if duplicate_node_emission_count > 0:
        return "projection_identity_collapse"
    if flatness_posture == "missing_authority_structure":
        return "missing_authority_structure"
    if flatness_posture == "residual_heavy":
        return "residual_heavy_projection"
    if flatness_posture == "structured":
        return "renderer_candidate"
    if branching_factor <= 1.0:
        return "star_projection_shallow"
    return "projection_shallow"


def _lane_next_action(diagnosis: str) -> str:
    if diagnosis == "projection_identity_collapse":
        return "dedupe latent slice node ids before evaluating visual layout"
    if diagnosis == "renderer_candidate":
        return "only then evaluate itir-svelte rendering/layout behavior"
    if diagnosis == "missing_authority_structure":
        return "inspect bundle candidate extraction before graph rendering"
    if diagnosis == "residual_heavy_projection":
        return "reduce residual dominance or widen authority projection"
    return "widen relation projection depth/kinds before touching rendering"


def build_wikidata_lane_flatness_audit() -> dict[str, Any]:
    artifacts = build_wikidata_lane_artifacts()
    lanes: list[dict[str, Any]] = []
    projection_flat_lane_ids: list[str] = []
    structured_lane_ids: list[str] = []
    duplicate_identity_lane_ids: list[str] = []
    renderer_ready_lane_ids: list[str] = []

    for lane_id in sorted(artifacts):
        artifact = artifacts[lane_id]
        graph = artifact["latent_slice_graph"]
        diagnostics = graph["diagnostics"]
        metrics = diagnostics["metrics"]
        cone = diagnostics.get("cone", {})
        emission = graph["emission_diagnostics"]
        flatness_posture = graph["flatness_indicators"]["flatness_posture"]
        diagnosis = _lane_non_visual_diagnosis(
            flatness_posture=flatness_posture,
            branching_factor=float(metrics["branching_factor"]),
            duplicate_node_emission_count=int(emission["duplicate_node_emission_count"]),
        )
        if flatness_posture == "projection_flat":
            projection_flat_lane_ids.append(lane_id)
        if flatness_posture == "structured":
            structured_lane_ids.append(lane_id)
        if int(emission["duplicate_node_emission_count"]) > 0:
            duplicate_identity_lane_ids.append(lane_id)
        if diagnosis == "renderer_candidate":
            renderer_ready_lane_ids.append(lane_id)
        lanes.append(
            {
                "lane_id": lane_id,
                "lane_family": artifact["lane_family"],
                "dependency_class": artifact["dependency_class"],
                "execution_surface": artifact["execution_surface"],
                "flatness_posture": flatness_posture,
                "graph_metrics": dict(metrics),
                "cone_summary": {
                    "width_by_depth": dict(cone.get("width_by_depth", {})),
                    "selectivity": cone.get("selectivity", 0.0),
                    "leakage": cone.get("leakage", 0.0),
                },
                "emission_diagnostics": dict(emission),
                "non_visual_diagnosis": diagnosis,
                "renderer_followup_status": (
                    "defer_to_itir_svelte_priority_list"
                    if diagnosis != "renderer_candidate"
                    else "eligible_for_itir_svelte_review"
                ),
                "next_action": _lane_next_action(diagnosis),
            }
        )

    return {
        "schema_version": WIKIDATA_LANE_FLATNESS_AUDIT_SCHEMA_VERSION,
        "audit_scope": "bounded_wikidata_lane_graph_flatness",
        "summary": {
            "lane_count": len(lanes),
            "projection_flat_lane_count": len(projection_flat_lane_ids),
            "projection_flat_lane_ids": projection_flat_lane_ids,
            "structured_lane_count": len(structured_lane_ids),
            "structured_lane_ids": structured_lane_ids,
            "duplicate_identity_lane_count": len(duplicate_identity_lane_ids),
            "duplicate_identity_lane_ids": duplicate_identity_lane_ids,
            "renderer_ready_lane_count": len(renderer_ready_lane_ids),
            "renderer_ready_lane_ids": renderer_ready_lane_ids,
            "renderer_followup_status": "defer_to_itir_svelte_priority_list",
            "primary_owner": "data_projection_diagnostics",
        },
        "priority_findings": [
            {
                "finding_id": "duplicate_node_identity_collapse",
                "severity": "high",
                "lane_ids": duplicate_identity_lane_ids,
                "why_it_matters": (
                    "Duplicate latent-slice node ids collapse emitted structure before any renderer sees it."
                ),
            },
            {
                "finding_id": "all_current_lanes_remain_projection_flat",
                "severity": "medium",
                "lane_ids": projection_flat_lane_ids,
                "why_it_matters": (
                    "Current flatness is still a projection-shape result, so visual rendering should stay deferred."
                ),
            },
        ],
        "lanes": lanes,
        "next_actions": [
            "Fix hotspot_eval duplicate node ids before any visual rendering investigation.",
            "Keep renderer work deferred to the itir-svelte priority list until a lane reaches structured posture.",
            "Use lane-flatness as the non-visual gate before revisiting graph presentation.",
        ],
    }


__all__ = [
    "WIKIDATA_LANE_FLATNESS_AUDIT_SCHEMA_VERSION",
    "build_wikidata_lane_flatness_audit",
]
