from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION, build_nat_claim_dict
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope


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
    promotion_gate: Mapping[str, Any],
    workflow_summary: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "lane": _as_text(promotion_gate.get("lane")),
        "promotion_decision": _as_text(promotion_gate.get("decision")),
        "workflow_stage": _as_text(workflow_summary.get("stage")),
        "recommended_view": _as_text(workflow_summary.get("recommended_view")),
        "source_ref": source_ref,
    }


def _build_claim(
    *,
    claim_id: str,
    artifact_id: str,
    source_family: str,
    authority_level: str,
    claim_status: str,
    canonical_form: Mapping[str, Any],
    provenance_chain: Mapping[str, Any],
    evidence_status: str,
) -> dict[str, Any]:
    evidence_paths = [
        {
            "evidence_path_id": f"{claim_id}:{artifact_id}",
            "run_id": artifact_id,
            "root_artifact_id": artifact_id,
            "source_unit_id": claim_id,
            "source_family": source_family,
            "authority_level": authority_level,
            "verification_status": evidence_status,
            "provenance_chain": dict(provenance_chain),
        }
    ]
    root_artifact_ids = [artifact_id]
    claim = {
        "claim_id": claim_id,
        "candidate_id": claim_id,
        "family_id": BREXIT_REVIEW_FAMILY_ID,
        "cohort_id": artifact_id,
        "status": claim_status,
        "canonical_form": dict(canonical_form),
        "evidence_paths": evidence_paths,
        "independent_root_artifact_ids": root_artifact_ids,
        "evidence_count": 1,
    }
    claim["nat_claim"] = build_nat_claim_dict(
        claim_id=claim_id,
        family_id=BREXIT_REVIEW_FAMILY_ID,
        cohort_id=artifact_id,
        candidate_id=claim_id,
        canonical_form=canonical_form,
        source_property="brexit_review",
        target_property=_as_text(canonical_form.get("property")),
        state="review_claim",
        state_basis="brexit_artifact",
        root_artifact_id=artifact_id,
        provenance={"source_family": source_family, **dict(provenance_chain)},
        evidence_status=evidence_status,
    )
    claim["convergence"] = build_convergence_record(
        claim_id=claim_id,
        evidence_paths=evidence_paths,
        independent_root_artifact_ids=root_artifact_ids,
        claim_status=claim_status,
    )
    claim["temporal"] = build_temporal_envelope(
        claim_id=claim_id,
        evidence_paths=evidence_paths,
        independent_root_artifact_ids=root_artifact_ids,
    )
    claim["conflict_set"] = build_conflict_set(
        claim_id=claim_id,
        candidate_ids=[claim_id],
        evidence_rows=[
            {
                "run_id": artifact_id,
                "root_artifact_id": artifact_id,
                "canonical_form": canonical_form,
            }
        ],
    )
    claim["action_policy"] = build_action_policy_record(
        claim_id=claim_id,
        claim_status=claim_status,
        convergence=claim["convergence"],
        temporal=claim["temporal"],
        conflict_set=claim["conflict_set"],
    )
    return claim


def build_brexit_review_world_model_report(payload: Mapping[str, Any]) -> dict[str, Any]:
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

    promotion_gate = payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), Mapping) else {}
    workflow_summary = payload.get("workflow_summary") if isinstance(payload.get("workflow_summary"), Mapping) else {}

    claims: list[dict[str, Any]] = []
    for row in _review_rows(payload):
        source_ref = _as_text(row.get("source_row_id"))
        review_status = _as_text(row.get("review_status"))
        claim_id = f"brexit-review:{source_ref}"
        canonical_form = {
            "subject": source_ref,
            "property": "review_status",
            "value": review_status,
            "qualifiers": _qualifiers_for_review_row(row),
            "references": [],
        }
        claims.append(
            _build_claim(
                claim_id=claim_id,
                artifact_id=artifact_id,
                source_family=_as_text(row.get("source_family")) or "brexit_review_row",
                authority_level=_as_text(row.get("source_kind")) or "brexit_review_row",
                claim_status=_claim_status(review_status),
                canonical_form=canonical_form,
                provenance_chain=_provenance_chain(artifact_id, promotion_gate, workflow_summary, source_ref),
                evidence_status=review_status or "review_required",
            )
        )

    for row in _archive_rows(payload):
        doc_id = _as_text(row.get("doc_id"))
        canonical_form = {
            "subject": doc_id,
            "property": "archive_follow_title",
            "value": _as_text(row.get("title")),
            "qualifiers": _qualifiers_for_archive_row(row),
            "references": [],
        }
        claims.append(
            _build_claim(
                claim_id=f"brexit-archive:{doc_id}",
                artifact_id=artifact_id,
                source_family="brexit_national_archives",
                authority_level="national_archive_record",
                claim_status="REVIEW",
                canonical_form=canonical_form,
                provenance_chain=_provenance_chain(artifact_id, promotion_gate, workflow_summary, doc_id),
                evidence_status="archive_follow_live" if row.get("live_fetch") else "archive_follow_fixture",
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

    return {
        "schema_version": BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
        "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
        "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
        "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
        "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
        "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "lane_id": _as_text(promotion_gate.get("lane") or "gwb"),
        "family_id": BREXIT_REVIEW_FAMILY_ID,
        "decision": _as_text(promotion_gate.get("decision")),
        "claims": claims,
        "summary": summary,
    }


__all__ = [
    "BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION",
    "build_brexit_review_world_model_report",
]
