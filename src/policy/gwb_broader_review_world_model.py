from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION, build_nat_claim_dict
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope


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


def build_gwb_broader_review_world_model_report(payload: Mapping[str, Any]) -> dict[str, Any]:
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

    promotion_gate = payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), Mapping) else {}
    workflow_summary = payload.get("workflow_summary") if isinstance(payload.get("workflow_summary"), Mapping) else {}
    operator_views = payload.get("operator_views") if isinstance(payload.get("operator_views"), Mapping) else {}
    legal_follow_view = (
        operator_views.get("legal_follow_graph")
        if isinstance(operator_views.get("legal_follow_graph"), Mapping)
        else {}
    )
    queue = _mapping_rows(legal_follow_view.get("queue"))

    claims: list[dict[str, Any]] = []
    for row in queue:
        item_id = _as_text(row.get("item_id"))
        if not item_id:
            continue
        canonical_form = {
            "subject": item_id,
            "property": "legal_follow_target",
            "value": _as_text(row.get("title")),
            "qualifiers": _qualifiers_for_queue_row(row),
            "references": [],
            "window_id": artifact_id,
        }
        evidence_paths = [
            {
                "evidence_path_id": f"{item_id}:{artifact_id}",
                "run_id": artifact_id,
                "root_artifact_id": artifact_id,
                "source_unit_id": item_id,
                "source_family": "gwb_legal_follow",
                "authority_level": "legal_follow_queue_item",
                "verification_status": _as_text(row.get("resolution_status")) or "open",
                "provenance_chain": {
                    "artifact_id": artifact_id,
                    "lane": _as_text(promotion_gate.get("lane")) or "gwb",
                    "promotion_decision": _as_text(promotion_gate.get("decision")),
                    "workflow_stage": _as_text(workflow_summary.get("stage")),
                    "recommended_view": _as_text(workflow_summary.get("recommended_view")),
                    "route_target": _as_text(row.get("route_target")),
                },
            }
        ]
        root_artifact_ids = [artifact_id]
        claim_status = _claim_status(_as_text(row.get("resolution_status")) or "open")
        claim = {
            "claim_id": item_id,
            "candidate_id": item_id,
            "family_id": GWB_BROADER_REVIEW_FAMILY_ID,
            "cohort_id": artifact_id,
            "status": claim_status,
            "canonical_form": canonical_form,
            "evidence_paths": evidence_paths,
            "independent_root_artifact_ids": root_artifact_ids,
            "evidence_count": len(evidence_paths),
        }
        claim["nat_claim"] = build_nat_claim_dict(
            claim_id=item_id,
            family_id=GWB_BROADER_REVIEW_FAMILY_ID,
            cohort_id=artifact_id,
            candidate_id=item_id,
            canonical_form=canonical_form,
            source_property="gwb_broader_review",
            target_property="legal_follow_target",
            state="review_claim",
            state_basis="gwb_broader_review_artifact",
            root_artifact_id=artifact_id,
            provenance={
                "source_family": "gwb_legal_follow",
                "lane": _as_text(promotion_gate.get("lane")) or "gwb",
                "workflow_stage": _as_text(workflow_summary.get("stage")),
                "route_target": _as_text(row.get("route_target")),
            },
            evidence_status=_as_text(row.get("resolution_status")) or "open",
        )
        claim["convergence"] = build_convergence_record(
            claim_id=item_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
            claim_status=claim_status,
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=item_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=item_id,
            candidate_ids=[item_id],
            evidence_rows=[
                {
                    "run_id": artifact_id,
                    "root_artifact_id": artifact_id,
                    "canonical_form": canonical_form,
                }
            ],
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=item_id,
            claim_status=claim_status,
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claims.append(claim)

    return {
        "schema_version": GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
        "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
        "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
        "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
        "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
        "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "lane_id": _as_text(promotion_gate.get("lane")) or "gwb",
        "family_id": GWB_BROADER_REVIEW_FAMILY_ID,
        "decision": _as_text(promotion_gate.get("decision")),
        "claims": claims,
        "summary": {
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
    }


__all__ = [
    "GWB_BROADER_REVIEW_FAMILY_ID",
    "GWB_BROADER_REVIEW_WORLD_MODEL_SCHEMA_VERSION",
    "build_gwb_broader_review_world_model_report",
]
