from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.compiler_contract import normalize_compiler_contract
from src.policy.operator_workflow_surface import build_operator_workflow_surface
from src.policy.product_gate import normalize_product_gate
from src.policy.world_model import build_world_model as _build_world_model
from src.policy.world_model_adapters import (
    ACTION_POLICY_SCHEMA_VERSION,
    CONFLICT_SCHEMA_VERSION,
    CONVERGENCE_SCHEMA_VERSION,
    NAT_CLAIM_SCHEMA_VERSION,
    TEMPORAL_SCHEMA_VERSION,
    ReviewClaimRecordMapping,
    build_authority_surface_rows,
    build_review_claim_records,
    build_review_inputs,
)
from src.policy.world_model_projections import (
    project_claim_table,
    project_linkage_case,
    project_report as _project_report,
    project_review_surface,
)


GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION = "sl.gwb_broader_review_world_model.v0_1"
GWB_BROADER_REVIEW_FAMILY_ID = "gwb_broader_review"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _claim_status(review_status: str) -> str:
    normalized = review_status.strip().lower()
    if normalized in {"review_required", "missing_review", "open"}:
        return "REVIEW"
    if normalized in {"covered", "accepted", "resolved", "reviewed"}:
        return "PROMOTED"
    return "REVIEW_ONLY"


def _qualifiers_for_queue_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "route_target": _as_text(row.get("route_target")),
        "resolution_status": _as_text(row.get("resolution_status")),
        "authority_yield": _as_text(row.get("authority_yield")),
        "priority_score": int(row.get("priority_score") or 0),
        "priority_rank": int(row.get("priority_rank") or 0),
        "chips": list(row.get("chips", [])) if isinstance(row.get("chips"), Sequence) else [],
        "source_url": _as_text(row.get("source_url")),
        "cite_class": _as_text(row.get("cite_class")),
        "brexit_related": bool(row.get("brexit_related")),
        "resolution_mode": _as_text(row.get("resolution_mode")),
        "source_refs": list(row.get("source_refs", [])) if isinstance(row.get("source_refs"), Sequence) else [],
    }


def build_world_model(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("GWB broader-review world-model adapter requires mapping payload")
    if _as_text(payload.get("fixture_kind")) != "gwb_broader_review":
        raise ValueError("GWB broader-review world-model adapter requires gwb_broader_review fixture kind")

    normalized_metrics = payload.get("normalized_metrics_v1")
    if not isinstance(normalized_metrics, Mapping):
        raise ValueError("GWB broader-review world-model adapter requires normalized_metrics_v1")
    artifact_id = _as_text(normalized_metrics.get("artifact_id"))
    if not artifact_id:
        raise ValueError("GWB broader-review world-model adapter requires artifact_id")

    compiler_contract = normalize_compiler_contract(
        payload.get("compiler_contract") if isinstance(payload.get("compiler_contract"), Mapping) else None
    )
    promotion_gate = normalize_product_gate(
        payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), Mapping) else None
    )
    workflow_summary = payload.get("workflow_summary") if isinstance(payload.get("workflow_summary"), Mapping) else {}
    operator_workflow_surface = build_operator_workflow_surface(
        compiler_contract=compiler_contract,
        promotion_gate=promotion_gate,
        workflow_summary=workflow_summary,
    )
    operator_views = payload.get("operator_views") if isinstance(payload.get("operator_views"), Mapping) else {}
    legal_follow_view = (
        operator_views.get("legal_follow_graph")
        if isinstance(operator_views.get("legal_follow_graph"), Mapping)
        else {}
    )
    queue = _mapping_rows(legal_follow_view.get("queue"))
    claims = build_review_claim_records(
        queue,
        family_id=GWB_BROADER_REVIEW_FAMILY_ID,
        context={
            "artifact_id": artifact_id,
            "lane_id": _as_text(operator_workflow_surface.get("lane")) or "gwb",
            "operator_workflow_surface": dict(operator_workflow_surface),
        },
        mapping=ReviewClaimRecordMapping(
            claim_id="item_id",
            candidate_id="item_id",
            cohort_id=lambda _row, context: context.get("artifact_id"),
            root_artifact_id=lambda _row, context: context.get("artifact_id"),
            source_family=lambda _row, _context: "gwb_legal_follow",
            authority_level=lambda _row, _context: "legal_follow_queue_item",
            claim_status=lambda row, _context: _claim_status(_as_text(row.get("resolution_status")) or "open"),
            evidence_status=lambda row, _context: _as_text(row.get("resolution_status")) or "open",
            source_property=lambda _row, _context: "gwb_broader_review",
            target_property=lambda _row, _context: "legal_follow_target",
            state_basis=lambda _row, _context: "gwb_broader_review_artifact",
            provenance_chain=lambda row, context: {
                "artifact_id": context.get("artifact_id"),
                "lane": context.get("lane_id"),
                "promotion_decision": _as_text(
                    context.get("operator_workflow_surface", {}).get("summary", {}).get("gate_decision")
                ),
                "workflow_stage": _as_text(context.get("operator_workflow_surface", {}).get("stage")),
                "recommended_view": _as_text(context.get("operator_workflow_surface", {}).get("recommended_view")),
                "route_target": _as_text(row.get("route_target")),
            },
            canonical_form=lambda row, context: {
                "subject": _as_text(row.get("item_id")),
                "property": "legal_follow_target",
                "value": _as_text(row.get("title")),
                "qualifiers": _qualifiers_for_queue_row(row),
                "references": [],
                "window_id": _as_text(context.get("artifact_id")),
            },
        ),
    )

    return _build_world_model(
        model_id=artifact_id,
        lane_family=GWB_BROADER_REVIEW_FAMILY_ID,
        model_status="candidate",
        source_mode="gwb_broader_review_payload",
        claims=claims,
        authority_surfaces=build_authority_surface_rows([f"operator_workflow_surface:{artifact_id}"]),
        provenance_graph=[
            {
                "source_payload_kind": _as_text(payload.get("fixture_kind")),
                "artifact_id": artifact_id,
            }
        ],
        summary={
            "claim_count": len(claims),
            "must_review_count": sum(
                1 for claim in claims if _as_text(claim.get("action_policy", {}).get("actionability")) == "must_review"
            ),
            "must_abstain_count": sum(
                1 for claim in claims if _as_text(claim.get("action_policy", {}).get("actionability")) == "must_abstain"
            ),
            "can_act_count": sum(
                1 for claim in claims if _as_text(claim.get("action_policy", {}).get("actionability")) == "can_act"
            ),
            "queue_count": len(queue),
        },
        metadata={
            "artifact_id": artifact_id,
            "lane_id": _as_text(operator_workflow_surface.get("lane")) or "gwb",
            "decision": _as_text(operator_workflow_surface.get("summary", {}).get("gate_decision")),
            "compiler_contract": compiler_contract,
            "promotion_gate": promotion_gate,
            "workflow_summary": dict(workflow_summary),
            "operator_workflow_surface": operator_workflow_surface,
            "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
            "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
            "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
            "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
            "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
            "adapter_stack": ["review_claim_records", "authority_surface_rows", "review_inputs"],
            "linkage_inputs": build_review_inputs(
                payload,
                field_names=(
                    "operator_views",
                    "workflow_summary",
                    "promotion_gate",
                    "compiler_contract",
                    "source_review_rows",
                    "archive_follow_rows",
                    "review_claim_records",
                    "provisional_review_rows",
                    "provisional_review_bundles",
                    "related_review_clusters",
                ),
                extra_fields={
                    "fixture_kind": _as_text(payload.get("fixture_kind")),
                    "normalized_metrics_v1": dict(normalized_metrics),
                    "operator_workflow_surface": dict(operator_workflow_surface),
                },
            ),
        },
    )


def project_report(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(world_model)
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    report = _project_report(
        world_model=model,
        schema_version=GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
        artifact_id=_as_text(metadata.get("artifact_id")) or _as_text(model.get("model_id")),
        lane_id=_as_text(metadata.get("lane_id")) or "gwb",
        family_id=_as_text(model.get("lane_family")) or GWB_BROADER_REVIEW_FAMILY_ID,
        compiler_contract=metadata.get("compiler_contract") if isinstance(metadata.get("compiler_contract"), Mapping) else None,
        promotion_gate=metadata.get("promotion_gate") if isinstance(metadata.get("promotion_gate"), Mapping) else None,
        workflow_summary=metadata.get("workflow_summary") if isinstance(metadata.get("workflow_summary"), Mapping) else None,
        operator_workflow_surface=metadata.get("operator_workflow_surface")
        if isinstance(metadata.get("operator_workflow_surface"), Mapping)
        else None,
        claims=model.get("claims") if isinstance(model.get("claims"), Sequence) else None,
        summary=model.get("summary") if isinstance(model.get("summary"), Mapping) else None,
        extra_fields={
            "claim_schema_version": _as_text(metadata.get("claim_schema_version")),
            "convergence_schema_version": _as_text(metadata.get("convergence_schema_version")),
            "temporal_schema_version": _as_text(metadata.get("temporal_schema_version")),
            "conflict_schema_version": _as_text(metadata.get("conflict_schema_version")),
            "action_policy_schema_version": _as_text(metadata.get("action_policy_schema_version")),
            "decision": _as_text(metadata.get("decision")),
        },
    )
    report["claim_table"] = project_claim_table(model)
    report["review_surface"] = project_review_surface(
        model,
        workflow_summary=metadata.get("workflow_summary") if isinstance(metadata.get("workflow_summary"), Mapping) else None,
        operator_workflow_surface=metadata.get("operator_workflow_surface")
        if isinstance(metadata.get("operator_workflow_surface"), Mapping)
        else None,
    )
    from src.policy.gwb_linkage_depth import build_case as build_linkage_case

    linkage_case_payload = build_linkage_case(report)
    report["linkage_case"] = project_linkage_case(
        model,
        case_id=_as_text(linkage_case_payload.get("case_id")) or "gwb_broader_review",
        contract_id=_as_text(linkage_case_payload.get("contract_id")),
        nodes=linkage_case_payload.get("nodes", []),
        edges=linkage_case_payload.get("edges", []),
        expected_anchor_ids=linkage_case_payload.get("expected_anchor_ids", []),
        expected_terminal_ids=linkage_case_payload.get("expected_terminal_ids", []),
        notes=linkage_case_payload.get("notes", []),
    )
    return report


def build_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    return project_report(build_world_model(payload))


build_gwb_broader_review_world_model_report = build_report


__all__ = [
    "GWB_BROADER_REVIEW_FAMILY_ID",
    "GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION",
    "build_report",
    "build_world_model",
    "build_gwb_broader_review_world_model_report",
    "project_report",
]
