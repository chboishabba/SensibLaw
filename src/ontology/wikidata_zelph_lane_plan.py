from __future__ import annotations

from typing import Any, Mapping


WIKIDATA_ZELPH_LANE_PLAN_SCHEMA_VERSION = "sl.wikidata_zelph_lane_plan.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.append(text)
    return seen


def _climate_query_pressures(
    *,
    report: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    review_disposition = (
        report.get("review_disposition") if isinstance(report.get("review_disposition"), Mapping) else {}
    )
    candidate_surface = (
        report.get("candidate_change_surface")
        if isinstance(report.get("candidate_change_surface"), Mapping)
        else {}
    )
    focus_qids = _as_list(bundle.get("dependency_cone", {}).get("focus_qids"))
    focus_pids = _as_list(bundle.get("dependency_cone", {}).get("focus_pids"))
    return [
        {
            "pressure_id": "source_property_broadening",
            "goal": "broaden candidate discovery around the source climate property while keeping review-first migration semantics.",
            "seed_qids": focus_qids,
            "seed_pids": [_text(inputs.get("source_property"))],
            "suggested_operations": [
                "sparql-subset",
                "partial-loading",
                "node-route-selection",
            ],
            "bounded_receipt": {
                "candidate_count": int(candidate_surface.get("candidate_count", 0) or 0),
                "held_candidate_count": int(review_disposition.get("held_candidate_count", 0) or 0),
            },
        },
        {
            "pressure_id": "migration_target_confirmation",
            "goal": "confirm that the target migration property and related subclasses stay reviewable before any broader pack expansion.",
            "seed_qids": focus_qids,
            "seed_pids": [_text(inputs.get("target_property"))],
            "suggested_operations": [
                "sparql-subset",
                "transitive-property-paths",
                "node-route-selection",
            ],
            "bounded_receipt": {
                "review_final_state": _text(review_disposition.get("final_state")),
                "promotable_candidate_count": int(
                    review_disposition.get("promotable_candidate_count", 0) or 0
                ),
            },
        },
        {
            "pressure_id": "split_pressure_context",
            "goal": "use Zelph-backed discovery only to sharpen split pressure and migration-family confirmation, not to bypass review holds.",
            "seed_qids": focus_qids,
            "seed_pids": focus_pids,
            "suggested_operations": [
                "sparql-subset",
                "transitive-property-paths",
            ],
            "bounded_receipt": {
                "residual_codes": [
                    _text(row.get("code"))
                    for row in bundle.get("residuals", [])
                    if isinstance(row, Mapping) and _text(row.get("code"))
                ],
            },
        },
    ]


def _live_follow_query_pressures(
    *,
    report: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates = report.get("candidates") if isinstance(report.get("candidates"), list) else []
    focus_qids = _as_list(bundle.get("dependency_cone", {}).get("focus_qids"))
    routing_needs: list[str] = []
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        for need in row.get("routing_needs", []):
            text = _text(need)
            if text and text not in routing_needs:
                routing_needs.append(text)
    return [
        {
            "pressure_id": "held_follow_target_confirmation",
            "goal": "confirm the held follow targets directly from bounded node routes before widening the live-follow queue.",
            "seed_qids": focus_qids,
            "seed_pids": [],
            "suggested_operations": [
                "node-route-selection",
                "partial-loading",
            ],
            "bounded_receipt": {
                "candidate_count": int(report.get("candidate_count", 0) or 0),
                "coverage_counts": dict(report.get("coverage_counts", {})),
            },
        },
        {
            "pressure_id": "authority_follow_reference_pressure",
            "goal": "use Zelph-backed reads to confirm authority, follow, and reference pressure on the top held candidates.",
            "seed_qids": focus_qids,
            "seed_pids": [],
            "suggested_operations": [
                "sparql-subset",
                "node-route-selection",
            ],
            "bounded_receipt": {
                "routing_needs": routing_needs,
                "top_n": int(report.get("top_n", 0) or 0),
            },
        },
    ]


def build_adjacent_zelph_lane_plan(
    *,
    report: Mapping[str, Any],
    bundle: Mapping[str, Any],
    latent_slice_graph: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    execution_surface: str,
) -> dict[str, Any]:
    if lane_id == "climate_review_demonstrator":
        query_pressures = _climate_query_pressures(report=report, bundle=bundle)
        zelph_role = "candidate_discovery_and_migration_confirmation"
    elif lane_id == "nat_live_follow_preflight":
        query_pressures = _live_follow_query_pressures(report=report, bundle=bundle)
        zelph_role = "follow_target_confirmation_and_queue_pressure"
    else:
        raise ValueError(f"lane does not expose an adjacent Zelph plan surface: {lane_id}")

    return {
        "schema_version": WIKIDATA_ZELPH_LANE_PLAN_SCHEMA_VERSION,
        "lane_id": _text(lane_id),
        "lane_family": _text(lane_family),
        "execution_surface": _text(execution_surface),
        "plan_scope": "bounded_adjacent_zelph_discovery",
        "zelph_role": zelph_role,
        "focus_entities": _as_list(bundle.get("dependency_cone", {}).get("focus_qids")),
        "focus_properties": _as_list(bundle.get("dependency_cone", {}).get("focus_pids")),
        "query_pressures": query_pressures,
        "graph_receipt": {
            "flatness_posture": _text(
                latent_slice_graph.get("flatness_indicators", {}).get("flatness_posture")
            ),
            "node_count": int(latent_slice_graph.get("diagnostics", {}).get("metrics", {}).get("node_count", 0) or 0),
            "edge_count": int(latent_slice_graph.get("diagnostics", {}).get("metrics", {}).get("edge_count", 0) or 0),
        },
        "readiness": {
            "normalized_bundle_status": "available",
            "latent_slice_graph_status": "available",
            "zelph_dependency_status": "adjacent_optional",
            "hosted_wd_dependency_status": "not_blocking",
            "overall_status": "ready_for_parallel_discovery",
        },
        "blocking_items": [
            "Any Zelph-backed widening remains review-first and candidate-only.",
            "This surface does not grant edit authority or bypass the lane's existing hold geometry.",
        ],
        "next_actions": [
            "Run bounded Zelph-backed discovery or confirmation against the seeded entities/properties for this lane.",
            "Feed any widened result set back into the existing bounded review packet or live-follow preflight rather than inventing a second authority surface.",
        ],
    }


__all__ = [
    "WIKIDATA_ZELPH_LANE_PLAN_SCHEMA_VERSION",
    "build_adjacent_zelph_lane_plan",
]
