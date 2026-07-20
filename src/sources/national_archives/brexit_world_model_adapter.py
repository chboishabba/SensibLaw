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
    build_review_claim_records,
    build_review_inputs,
)
from src.policy.world_model_projections import project_report as _project_report


BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION = "sl.brexit_review_world_model.v0_1"
BREXIT_REVIEW_FAMILY_ID = "brexit_broader_review"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _review_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    tokens = (
        "brexit",
        "withdrawal act",
        "article 50",
        "european union (withdrawal) act",
        "exit terms",
    )
    return [
        row
        for row in _mapping_rows(payload.get("source_review_rows"))
        if any(token in _as_text(row.get("text")).lower() for token in tokens)
        or any(token in _as_text(row.get("source_family")).lower() for token in tokens)
        or any(token in _as_text(row.get("source_kind")).lower() for token in tokens)
    ]


def _archive_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _mapping_rows(payload.get("archive_follow_rows"))


def _claim_status(review_status: str) -> str:
    normalized = review_status.strip().lower()
    if normalized in {"review_required", "missing_review"}:
        return "REVIEW"
    if normalized == "covered":
        return "PROMOTED"
    return "REVIEW_ONLY"


def _qualifiers_for_review_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": _as_text(row.get("source_kind")),
        "source_family": _as_text(row.get("source_family")),
        "primary_workload_class": _as_text(row.get("primary_workload_class")),
        "workload_classes": list(row.get("workload_classes", []))
        if isinstance(row.get("workload_classes"), Sequence)
        else [],
        "candidate_anchors": list(row.get("candidate_anchors", []))
        if isinstance(row.get("candidate_anchors"), Sequence)
        else [],
        "text": _as_text(row.get("text")),
    }


def _qualifiers_for_archive_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "authority_role": _as_text(row.get("authority_role")),
        "collection": _as_text(row.get("collection")),
        "anchor_date": _as_text(row.get("anchor_date")),
        "intent_tags": list(row.get("intent_tags", []))
        if isinstance(row.get("intent_tags"), Sequence)
        else [],
        "search_focus": _as_text(row.get("search_focus")),
        "url": _as_text(row.get("url")),
    }


def _provenance_chain(
    artifact_id: str,
    operator_workflow_surface: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "lane": _as_text(operator_workflow_surface.get("lane")),
        "promotion_decision": _as_text(operator_workflow_surface.get("summary", {}).get("gate_decision")),
        "workflow_stage": _as_text(operator_workflow_surface.get("stage")),
        "recommended_view": _as_text(operator_workflow_surface.get("recommended_view")),
        "source_ref": source_ref,
    }


def build_world_model(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Brexit world-model adapter requires broader review payload")
    if _as_text(payload.get("fixture_kind")) != "gwb_broader_review":
        raise ValueError("Brexit world-model adapter requires gwb_broader_review fixture kind")

    normalized_metrics = payload.get("normalized_metrics_v1")
    if not isinstance(normalized_metrics, Mapping):
        raise ValueError("Brexit world-model adapter requires normalized_metrics_v1")
    artifact_id = _as_text(normalized_metrics.get("artifact_id"))
    if not artifact_id:
        raise ValueError("Brexit world-model adapter requires artifact_id")

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

    context = {
        "artifact_id": artifact_id,
        "operator_workflow_surface": dict(operator_workflow_surface),
    }
    claims = build_review_claim_records(
        _review_rows(payload),
        family_id=BREXIT_REVIEW_FAMILY_ID,
        context=context,
        mapping=ReviewClaimRecordMapping(
            claim_id=lambda row, _context: f"brexit-review:{_as_text(row.get('source_row_id'))}",
            candidate_id=lambda row, _context: f"brexit-review:{_as_text(row.get('source_row_id'))}",
            cohort_id=lambda _row, context: context.get("artifact_id"),
            root_artifact_id=lambda _row, context: context.get("artifact_id"),
            source_family=lambda row, _context: _as_text(row.get("source_family")) or "brexit_review_row",
            authority_level=lambda row, _context: _as_text(row.get("source_kind")) or "brexit_review_row",
            claim_status=lambda row, _context: _claim_status(_as_text(row.get("review_status"))),
            evidence_status=lambda row, _context: _as_text(row.get("review_status")) or "review_required",
            source_property=lambda _row, _context: "brexit_review",
            target_property=lambda _row, _context: "review_status",
            state_basis=lambda _row, _context: "brexit_artifact",
            provenance_chain=lambda row, context: _provenance_chain(
                _as_text(context.get("artifact_id")),
                context.get("operator_workflow_surface", {}),
                _as_text(row.get("source_row_id")),
            ),
            canonical_form=lambda row, _context: {
                "subject": _as_text(row.get("source_row_id")),
                "property": "review_status",
                "value": _as_text(row.get("review_status")),
                "qualifiers": _qualifiers_for_review_row(row),
                "references": [],
            },
        ),
    )
    claims.extend(
        build_review_claim_records(
            _archive_rows(payload),
            family_id=BREXIT_REVIEW_FAMILY_ID,
            context=context,
            mapping=ReviewClaimRecordMapping(
                claim_id=lambda row, _context: f"brexit-archive:{_as_text(row.get('doc_id'))}",
                candidate_id=lambda row, _context: f"brexit-archive:{_as_text(row.get('doc_id'))}",
                cohort_id=lambda _row, context: context.get("artifact_id"),
                root_artifact_id=lambda _row, context: context.get("artifact_id"),
                source_family=lambda _row, _context: "brexit_national_archives",
                authority_level=lambda _row, _context: "national_archive_record",
                claim_status=lambda _row, _context: "REVIEW",
                evidence_status=lambda row, _context: "archive_follow_live" if row.get("live_fetch") else "archive_follow_fixture",
                source_property=lambda _row, _context: "brexit_review",
                target_property=lambda _row, _context: "archive_follow_title",
                state_basis=lambda _row, _context: "brexit_artifact",
                provenance_chain=lambda row, context: _provenance_chain(
                    _as_text(context.get("artifact_id")),
                    context.get("operator_workflow_surface", {}),
                    _as_text(row.get("doc_id")),
                ),
                canonical_form=lambda row, _context: {
                    "subject": _as_text(row.get("doc_id")),
                    "property": "archive_follow_title",
                    "value": _as_text(row.get("title")),
                    "qualifiers": _qualifiers_for_archive_row(row),
                    "references": [],
                },
            ),
        )
    )

    summary = {
        "claim_count": len(claims),
        "review_row_claim_count": len(_review_rows(payload)),
        "archive_claim_count": len(_archive_rows(payload)),
        "must_review_count": sum(
            1 for claim in claims if _as_text(claim.get("action_policy", {}).get("actionability")) == "must_review"
        ),
        "can_act_count": sum(
            1 for claim in claims if _as_text(claim.get("action_policy", {}).get("actionability")) == "can_act"
        ),
    }

    return _build_world_model(
        model_id=artifact_id,
        lane_family=BREXIT_REVIEW_FAMILY_ID,
        model_status="candidate",
        source_mode="gwb_broader_review_payload",
        claims=claims,
        authority_surfaces=[
            {
                "authority_surface_id": f"operator_workflow_surface:{artifact_id}",
                "authority_kind": "operator_workflow_surface",
                "status": "reviewed",
                "lane_id": _as_text(operator_workflow_surface.get("lane") or "gwb"),
                "decision": _as_text(operator_workflow_surface.get("summary", {}).get("gate_decision")),
                "workflow_stage": _as_text(operator_workflow_surface.get("stage")),
            }
        ],
        provenance_graph=[
            {
                "source_payload_kind": _as_text(payload.get("fixture_kind")),
                "artifact_id": artifact_id,
                "archive_row_count": len(_archive_rows(payload)),
            }
        ],
        summary=summary,
        metadata={
            "artifact_id": artifact_id,
            "lane_id": _as_text(operator_workflow_surface.get("lane") or "gwb"),
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
            "adapter_stack": ["review_claim_records", "review_inputs"],
            "linkage_inputs": build_review_inputs(
                payload,
                field_names=("source_review_rows", "archive_follow_rows", "review_claim_records", "operator_views"),
                extra_fields={
                    "fixture_kind": _as_text(payload.get("fixture_kind")),
                    "normalized_metrics_v1": dict(normalized_metrics),
                    "workflow_summary": dict(workflow_summary),
                    "promotion_gate": dict(promotion_gate),
                    "compiler_contract": dict(compiler_contract),
                    "operator_workflow_surface": dict(operator_workflow_surface),
                },
            ),
        },
    )


def project_report(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(world_model)
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    return _project_report(
        world_model=model,
        schema_version=BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
        artifact_id=_as_text(metadata.get("artifact_id")) or _as_text(model.get("model_id")),
        lane_id=_as_text(metadata.get("lane_id")) or "gwb",
        family_id=_as_text(model.get("lane_family")) or BREXIT_REVIEW_FAMILY_ID,
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


def build_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    return project_report(build_world_model(payload))


__all__ = [
    "BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION",
    "build_report",
    "build_world_model",
    "project_report",
]
