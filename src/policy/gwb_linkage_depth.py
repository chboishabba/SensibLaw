from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.policy.gwb_broader_review_world_model import (
    GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
)
from src.policy.linkage_depth import (
    build_expected_layer_contract,
    build_linkage_depth_case,
    build_linkage_depth_receipt,
)
from src.policy.linkage_case_inputs import (
    case_from_linkage_projection,
    case_from_receipt,
    require_case_from_projection_artifact,
)

GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID = "gwb_broader_review_linkage"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_ref_event_lineage_depth(source_refs: Any) -> str:
    refs = [row for row in source_refs if isinstance(row, Mapping)] if isinstance(source_refs, list) else []
    if not refs:
        return "missing"
    complete = False
    partial = False
    for ref in refs:
        event_ids = [str(value).strip() for value in ref.get("event_ids", []) if str(value).strip()]
        source_paths = [str(value).strip() for value in ref.get("source_paths", []) if str(value).strip()]
        source_urls = [str(value).strip() for value in ref.get("source_urls", []) if str(value).strip()]
        citation_refs = [row for row in ref.get("citation_refs", []) if isinstance(row, Mapping)]
        if event_ids and (source_paths or source_urls or citation_refs):
            complete = True
        elif event_ids or source_paths or source_urls or citation_refs:
            partial = True
    if complete:
        return "complete"
    if partial:
        return "partial"
    return "missing"


def _source_ref_cross_source_braid_depth(source_refs: Any) -> str:
    refs = [row for row in source_refs if isinstance(row, Mapping)] if isinstance(source_refs, list) else []
    if not refs:
        return "missing"
    values = {
        _text(ref.get("cross_source_braid_depth"))
        for ref in refs
        if _text(ref.get("cross_source_braid_depth"))
    }
    if "complete" in values:
        return "complete"
    if "partial" in values:
        return "partial"
    if "candidate_only" in values:
        return "candidate_only"
    for ref in refs:
        merged_event_ids = [str(value).strip() for value in ref.get("merged_event_ids", []) if str(value).strip()]
        ordering_edge_ids = [str(value).strip() for value in ref.get("ordering_edge_ids", []) if str(value).strip()]
        if merged_event_ids and ordering_edge_ids:
            return "complete"
        if merged_event_ids or ordering_edge_ids:
            return "partial"
    return "missing"


def build_contract() -> dict[str, Any]:
    return build_expected_layer_contract(
        contract_id=GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
        domain="gwb_broader_review_linkage",
        anchor_kind="source_follow_anchor",
        expected_layers=[
            "source_anchor",
            "source_container",
            "domain_candidate",
            "authority_surface",
            "review_surface",
            "tranche_anchor",
        ],
        required_bridges=[
            ["source_anchor", "source_container"],
            ["source_container", "domain_candidate"],
            ["domain_candidate", "authority_surface"],
            ["authority_surface", "review_surface"],
            ["review_surface", "tranche_anchor"],
        ],
        terminal_anchor="tranche_anchor",
        required_authority_boundaries=[
            "gwb_legal_follow_queue",
            "gwb_operator_workflow_surface",
            "workflow_tranche_anchor",
        ],
        required_visibility_fields=[
            "queue_review_depth",
            "event_lineage_depth",
            "cross_source_braid_depth",
            "candidate_vs_promoted_visibility",
        ],
        notes=[
            "GWB uses the legal-follow queue as the native spine; WD enrichment stays optional.",
            "This first non-WD adopter proves the shared control-plane does not depend on Wikidata geometry.",
        ],
        linkage_policy={
            "native_spine": "legal_follow_queue",
            "wd_bridge_requirement": "optional",
        },
    )


def _build_case_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    if _text(report.get("schema_version")) != GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION:
        raise ValueError("GWB broader review linkage case requires world-model report payload")

    claims = [row for row in report.get("claims", []) if isinstance(row, Mapping)]
    if not claims:
        raise ValueError("GWB broader review linkage case requires at least one claim")

    artifact_id = _text(report.get("artifact_id"))
    lane_id = _text(report.get("lane_id")) or "gwb"
    authority_node_id = f"operator_authority_surface:{artifact_id}"
    review_node_id = f"broader_review_surface:{artifact_id}"
    tranche_node_id = f"workflow_tranche_anchor:{artifact_id}"

    nodes = [
        {
            "id": authority_node_id,
            "layer": "authority_surface",
            "label": f"GWB operator authority surface {artifact_id}",
            "metadata": {
                "artifact_id": artifact_id,
                "lane_id": lane_id,
                "decision": _text(report.get("decision")),
                "authority_surface": "gwb_operator_workflow_surface",
            },
        },
        {
            "id": review_node_id,
            "layer": "review_surface",
            "label": f"GWB broader-review world-model surface {artifact_id}",
            "metadata": {
                "artifact_id": artifact_id,
                "family_id": _text(report.get("family_id")),
                "claim_count": int(report.get("summary", {}).get("claim_count", 0) or 0),
            },
        },
        {
            "id": tranche_node_id,
            "layer": "tranche_anchor",
            "label": f"GWB workflow/tranche anchor {artifact_id}",
            "metadata": {
                "artifact_id": artifact_id,
                "workflow_stage": _text(report.get("workflow_summary", {}).get("stage")),
                "gate_decision": _text(report.get("promotion_gate", {}).get("decision")),
                "authority_surface": "workflow_tranche_anchor",
            },
        },
    ]
    edges = [
        {
            "source": authority_node_id,
            "target": review_node_id,
            "kind": "world_model_projection",
            "metadata": {
                "from_layer": "authority_surface",
                "to_layer": "review_surface",
                "authority_surface": "gwb_operator_workflow_surface",
            },
        },
        {
            "source": review_node_id,
            "target": tranche_node_id,
            "kind": "workflow_tranche_projection",
            "metadata": {
                "from_layer": "review_surface",
                "to_layer": "tranche_anchor",
                "authority_surface": "workflow_tranche_anchor",
                "promotion_status": _text(report.get("promotion_gate", {}).get("decision")) or "audit",
            },
        },
    ]
    anchor_ids: list[str] = []

    for claim in claims:
        claim_id = _text(claim.get("claim_id"))
        if not claim_id:
            continue
        source_anchor_id = f"source_follow_anchor:{claim_id}"
        queue_item_id = f"legal_follow_queue_item:{claim_id}"
        candidate_id = f"legal_follow_claim_candidate:{claim_id}"
        anchor_ids.append(source_anchor_id)

        nat_claim = claim.get("nat_claim") if isinstance(claim.get("nat_claim"), Mapping) else {}
        qualifiers = nat_claim.get("qualifiers") if isinstance(nat_claim.get("qualifiers"), Mapping) else {}
        source_refs = qualifiers.get("source_refs")
        event_lineage_depth = _source_ref_event_lineage_depth(source_refs)
        cross_source_braid_depth = _source_ref_cross_source_braid_depth(source_refs)
        event_quality_status = _text(qualifiers.get("event_quality_status")) or _text(claim.get("event_quality_status")) or None
        event_quality_score = qualifiers.get("event_quality_score") if qualifiers.get("event_quality_score") is not None else (claim.get("event_quality_score") if claim.get("event_quality_score") is not None else None)
        event_time_anchor_status = _text(qualifiers.get("event_time_anchor_status")) or _text(claim.get("event_time_anchor_status")) or None
        resolved_historical_date = _text(qualifiers.get("resolved_historical_date")) or _text(claim.get("resolved_historical_date")) or None
        
        nodes.extend(
            [
                {
                    "id": source_anchor_id,
                    "layer": "source_anchor",
                    "label": f"source follow anchor {claim_id}",
                    "metadata": {
                        "claim_id": claim_id,
                        "source_refs": list(source_refs) if isinstance(source_refs, list) else [],
                        "route_target": _text(qualifiers.get("route_target")),
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
                {
                    "id": queue_item_id,
                    "layer": "source_container",
                    "label": f"legal-follow queue item {claim_id}",
                    "metadata": {
                        "claim_id": claim_id,
                        "resolution_status": _text(qualifiers.get("resolution_status")),
                        "authority_yield": _text(qualifiers.get("authority_yield")),
                        "priority_rank": int(qualifiers.get("priority_rank", 0) or 0),
                        "queue_review_depth": "complete",
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
                {
                    "id": candidate_id,
                    "layer": "domain_candidate",
                    "label": f"legal-follow claim/review candidate {claim_id}",
                    "metadata": {
                        "claim_id": claim_id,
                        "claim_status": _text(claim.get("status")),
                        "evidence_count": int(claim.get("evidence_count", 0) or 0),
                        "family_id": _text(claim.get("family_id")),
                        "candidate_vs_promoted_visibility": True,
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
            ]
        )
        edges.extend(
            [
                {
                    "source": source_anchor_id,
                    "target": queue_item_id,
                    "kind": "follow_anchor_projection",
                    "metadata": {
                        "from_layer": "source_anchor",
                        "to_layer": "source_container",
                        "authority_surface": "gwb_legal_follow_queue",
                        "queue_review_depth": "complete",
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
                {
                    "source": queue_item_id,
                    "target": candidate_id,
                    "kind": "queue_claim_projection",
                    "metadata": {
                        "from_layer": "source_container",
                        "to_layer": "domain_candidate",
                        "authority_surface": "gwb_legal_follow_queue",
                        "queue_review_depth": "complete",
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
                {
                    "source": candidate_id,
                    "target": authority_node_id,
                    "kind": "operator_review_projection",
                    "metadata": {
                        "from_layer": "domain_candidate",
                        "to_layer": "authority_surface",
                        "authority_surface": "gwb_operator_workflow_surface",
                        "promotion_status": _text(claim.get("status")) or "review",
                        "candidate_vs_promoted_visibility": True,
                        "event_lineage_depth": event_lineage_depth,
                        "cross_source_braid_depth": cross_source_braid_depth,
                        "event_quality_status": event_quality_status,
                        "event_quality_score": event_quality_score,
                        "event_time_anchor_status": event_time_anchor_status,
                        "resolved_historical_date": resolved_historical_date,
                    },
                },
            ]
        )

    return build_linkage_depth_case(
        case_id="gwb_broader_review",
        case_kind="legal_follow_fixture",
        lane_id=lane_id,
        contract_id=GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
        case_source="emitted_bridge_artifact",
        notes=[
            "Bounded GWB broader-review linkage case projected from the queue-backed world-model surface.",
            "This first non-WD adopter preserves native legal-follow depth without requiring a WD bridge.",
        ],
        expected_anchor_ids=anchor_ids,
        expected_terminal_ids=[tranche_node_id],
        nodes=nodes,
        edges=edges,
        contract=build_contract(),
    )


def build_case(report: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(report, Mapping):
        case = case_from_receipt(
            report.get("linkage_depth_receipt"),
            case_kind="legal_follow_fixture",
            default_case_id="gwb_broader_review",
            default_lane_id="gwb",
            default_contract=build_contract(),
            default_contract_id=GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
            default_notes=["Bounded GWB broader review case loaded from the emitted lane receipt."],
        )
        if case is not None:
            return case
        case = case_from_linkage_projection(
            report.get("linkage_case"),
            case_kind="legal_follow_fixture",
            default_case_id="gwb_broader_review",
            default_lane_id="gwb",
            default_contract=build_contract(),
            default_contract_id=GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
            default_notes=["Bounded GWB broader review case loaded from the projected linkage surface."],
        )
        if case is not None:
            return case
    return _build_case_payload(report)


def build_receipt(
    report: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract_payload = (
        dict(contract)
        if isinstance(contract, Mapping)
        else build_contract()
    )
    case_payload = require_case_from_projection_artifact(
        report,
        case_kind="legal_follow_fixture",
        default_case_id="gwb_broader_review",
        default_lane_id="gwb",
        default_contract=contract_payload,
        default_contract_id=GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID,
        default_notes=["Bounded GWB broader review case loaded from the projected linkage surface."],
    )
    receipt = build_linkage_depth_receipt(
        case=case_payload,
        contract=contract_payload,
        source_mode="emitted_bridge_artifact",
        notes=[
            "Lane-level linkage receipt for the GWB broader-review world-model surface.",
            "The shared core audits this without learning GWB-specific queue geometry.",
        ],
    )
    receipt["contract"] = deepcopy(contract_payload)
    return receipt


__all__ = [
    "GWB_BROADER_REVIEW_LINKAGE_CONTRACT_ID",
    "build_case",
    "build_contract",
    "build_receipt",
]
