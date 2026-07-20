from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.fact_intake.au_review_bundle import AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION
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
from src.policy.world_model import build_world_model as _build_world_model
from src.policy.world_model_profiles import build_profile
from src.policy.world_model_projections import (
    project_claim_table,
    project_linkage_case,
    project_report as _project_report,
    project_review_surface,
)

AU_FACT_REVIEW_BUNDLE_FAMILY_ID = "au_fact_review_bundle"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _build_claims(review_bundle: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run = review_bundle.get("run", {}) if isinstance(review_bundle.get("run"), Mapping) else {}
    run_id = _text(run.get("fact_run_id"))
    semantic_run_id = _text(run.get("semantic_run_id"))
    review_queue = _mapping_rows(review_bundle.get("review_queue"))

    claims = build_review_claim_records(
        review_queue,
        family_id=AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        context={"run_id": run_id, "semantic_run_id": semantic_run_id},
        mapping=ReviewClaimRecordMapping(
            claim_id="fact_id",
            candidate_id="fact_id",
            cohort_id=lambda _row, context: context.get("semantic_run_id"),
            root_artifact_id=lambda _row, context: context.get("run_id"),
            source_family=lambda _row, _context: AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
            authority_level=lambda _row, _context: "review_bundle",
            claim_status=lambda _row, _context: "REVIEW_ONLY",
            evidence_status=lambda _row, _context: "review_only",
            source_property=lambda _row, _context: "review_bundle",
            target_property=lambda _row, _context: "review_bundle",
            state_basis=lambda _row, _context: "review_bundle",
            provenance_chain=lambda row, context: {
                "run_id": context.get("run_id"),
                "semantic_run_id": context.get("semantic_run_id"),
                "event_ids": [_text(value) for value in row.get("event_ids", []) if _text(value)],
            },
            canonical_form=lambda row, context: {
                "subject": _text(row.get("fact_id")),
                "property": "au_review_fact",
                "value": _text(row.get("label")),
                "qualifiers": {
                    "candidate_status": [_text(row.get("candidate_status"))] if _text(row.get("candidate_status")) else [],
                    "reason_codes": [_text(value) for value in row.get("reason_codes", []) if _text(value)],
                    "policy_outcomes": [_text(value) for value in row.get("policy_outcomes", []) if _text(value)],
                },
                "references": [],
                "window_id": _text(context.get("run_id")),
            },
        ),
    )

    summary = {
        "claim_count": len(claims),
        "must_review_count": sum(
            1 for claim in claims if _text((claim.get("action_policy") or {}).get("actionability")) == "must_review"
        ),
    }
    return claims, summary


def build_world_model(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(review_bundle, Mapping):
        raise ValueError("world model requires AU fact review bundle object")
    if _text(review_bundle.get("version")) != "fact.review.bundle.v1":
        raise ValueError("world model requires AU fact review bundle payload")

    run = review_bundle.get("run", {}) if isinstance(review_bundle.get("run"), Mapping) else {}
    run_id = _text(run.get("fact_run_id"))
    semantic_run_id = _text(run.get("semantic_run_id"))
    compiler_contract = review_bundle.get("compiler_contract") if isinstance(review_bundle.get("compiler_contract"), Mapping) else {}
    promotion_gate = review_bundle.get("promotion_gate") if isinstance(review_bundle.get("promotion_gate"), Mapping) else {}
    workflow_summary = review_bundle.get("workflow_summary") if isinstance(review_bundle.get("workflow_summary"), Mapping) else {}
    operator_workflow_surface = (
        review_bundle.get("operator_workflow_surface")
        if isinstance(review_bundle.get("operator_workflow_surface"), Mapping)
        else {}
    )
    claims, summary = _build_claims(review_bundle)
    profile = build_profile(
        profile_id=AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        lane_family=AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        source_kinds=["legal_text", "legal_event", "authority_follow_queue"],
        authority_surfaces=[
            "au_source_document",
            "au_legal_reference_context",
            "au_authority_visibility_surface",
            "au_fact_review_bundle",
            "workflow_tranche_anchor",
        ],
        promotion_policy="candidate_only",
        default_projection_kinds=["report", "claim_table", "review_surface", "linkage_case"],
        metadata={"lane_id": "au"},
    )
    return _build_world_model(
        model_id=run_id or semantic_run_id or AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        lane_family=AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        model_status="candidate",
        source_mode="review_bundle",
        claims=claims,
        authority_surfaces=build_authority_surface_rows(profile["authority_surfaces"]),
        summary=summary,
        metadata={
            "artifact_id": run_id or semantic_run_id or AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
            "lane_id": "au",
            "run_id": run_id,
            "semantic_run_id": semantic_run_id,
            "compiler_contract": compiler_contract,
            "promotion_gate": promotion_gate,
            "workflow_summary": workflow_summary,
            "operator_workflow_surface": operator_workflow_surface,
            "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
            "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
            "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
            "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
            "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
            "profile": profile,
            "adapter_stack": ["review_claim_records", "authority_surface_rows", "review_inputs"],
            "linkage_inputs": build_review_inputs(
                review_bundle,
                field_names=("review_queue", "sources", "events", "source_documents", "operator_views"),
                extra_fields={
                    "run": deepcopy(dict(run)),
                    "workflow_summary": deepcopy(dict(workflow_summary)),
                    "operator_workflow_surface": deepcopy(dict(operator_workflow_surface)),
                    "promotion_gate": deepcopy(dict(promotion_gate)),
                    "compiler_contract": deepcopy(dict(compiler_contract)),
                    "version": "fact.review.bundle.v1",
                },
            ),
        },
    )


def project_report(world_model: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(world_model)
    metadata = model.get("metadata") if isinstance(model.get("metadata"), Mapping) else {}
    run_id = _text(metadata.get("run_id"))
    from src.policy.au_linkage_depth import build_case as build_linkage_case

    review_surface = project_review_surface(
        model,
        projection_id=f"review_surface:{run_id or model.get('model_id')}",
        review_rows=model.get("claims") if isinstance(model.get("claims"), Sequence) else None,
        workflow_summary=metadata.get("workflow_summary") if isinstance(metadata.get("workflow_summary"), Mapping) else None,
        operator_workflow_surface=metadata.get("operator_workflow_surface")
        if isinstance(metadata.get("operator_workflow_surface"), Mapping)
        else None,
        summary={"review_row_count": int((model.get("summary") or {}).get("claim_count") or 0)},
        metadata={"linkage_inputs": deepcopy(dict(metadata.get("linkage_inputs") or {}))},
    )
    claim_table = project_claim_table(
        model,
        projection_id=f"claim_table:{run_id or model.get('model_id')}",
        summary={"row_count": int((model.get("summary") or {}).get("claim_count") or 0)},
    )
    linkage_case_payload = build_linkage_case({"world_model_ref": model, **deepcopy(dict(metadata.get("linkage_inputs") or {}))})
    linkage_case = project_linkage_case(
        model,
        projection_id=f"linkage_case:{run_id or model.get('model_id')}",
        case_id=_text(linkage_case_payload.get("case_id")) or "au_fact_review_bundle",
        contract_id=_text(linkage_case_payload.get("contract_id")),
        nodes=linkage_case_payload.get("nodes", []),
        edges=linkage_case_payload.get("edges", []),
        expected_anchor_ids=linkage_case_payload.get("expected_anchor_ids", []),
        expected_terminal_ids=linkage_case_payload.get("expected_terminal_ids", []),
        notes=linkage_case_payload.get("notes", []),
    )
    return _project_report(
        world_model=model,
        schema_version=AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION,
        artifact_id=_text(metadata.get("artifact_id")) or _text(model.get("model_id")),
        lane_id=_text(metadata.get("lane_id")) or "au",
        family_id=_text(model.get("lane_family")) or AU_FACT_REVIEW_BUNDLE_FAMILY_ID,
        compiler_contract=metadata.get("compiler_contract") if isinstance(metadata.get("compiler_contract"), Mapping) else None,
        promotion_gate=metadata.get("promotion_gate") if isinstance(metadata.get("promotion_gate"), Mapping) else None,
        workflow_summary=metadata.get("workflow_summary") if isinstance(metadata.get("workflow_summary"), Mapping) else None,
        operator_workflow_surface=metadata.get("operator_workflow_surface")
        if isinstance(metadata.get("operator_workflow_surface"), Mapping)
        else None,
        claims=model.get("claims") if isinstance(model.get("claims"), Sequence) else None,
        summary=model.get("summary") if isinstance(model.get("summary"), Mapping) else None,
        projection_metadata={"linkage_inputs": deepcopy(dict(metadata.get("linkage_inputs") or {}))},
        extra_fields={
            "claim_schema_version": _text(metadata.get("claim_schema_version")),
            "convergence_schema_version": _text(metadata.get("convergence_schema_version")),
            "temporal_schema_version": _text(metadata.get("temporal_schema_version")),
            "conflict_schema_version": _text(metadata.get("conflict_schema_version")),
            "action_policy_schema_version": _text(metadata.get("action_policy_schema_version")),
            "run_id": _text(metadata.get("run_id")),
            "semantic_run_id": _text(metadata.get("semantic_run_id")),
            "review_surface": review_surface,
            "claim_table": claim_table,
            "linkage_case": linkage_case,
        },
    )


def build_report(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    return project_report(build_world_model(review_bundle))


build_au_fact_review_bundle_world_model_report = build_report


__all__ = [
    "AU_FACT_REVIEW_BUNDLE_FAMILY_ID",
    "build_report",
    "build_world_model",
    "project_report",
]
