from __future__ import annotations

from typing import Any, Iterable, Mapping

SEMANTIC_PROMOTION_VERSION = "semantic.promotion.v1"
CONTESTED_CANDIDATE_SCHEMA_VERSION = "contested.semantic_candidate.v1"
RELATION_CANDIDATE_SCHEMA_VERSION = "relation.semantic_candidate.v1"
HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION = "hotspot_pack.semantic_candidate.v1"

PROMOTED_TRUE = "promoted_true"
PROMOTED_FALSE = "promoted_false"
CANDIDATE_CONFLICT = "candidate_conflict"
ABSTAINED = "abstained"
NEEDS_RECONCILIATION = "needs_reconciliation"

PROMOTION_STATUSES = {
    PROMOTED_TRUE,
    PROMOTED_FALSE,
    CANDIDATE_CONFLICT,
    ABSTAINED,
}

CANDIDATE_BASES = {"structural", "heuristic", "mixed"}


def derive_relation_semantic_basis(
    *,
    receipts: Iterable[Mapping[str, Any]],
    subject: Mapping[str, Any] | None,
    object_: Mapping[str, Any] | None,
) -> str:
    has_participants = bool(subject) and bool(object_)
    kinds = {
        str(receipt.get("kind") or "").strip()
        for receipt in receipts
        if str(receipt.get("kind") or "").strip()
    }
    has_subject = any(kind == "subject" or kind.startswith("subject_") for kind in kinds)
    has_object = any(kind == "object" or kind.startswith("object_") for kind in kinds)
    has_predicate = "verb" in kinds or "predicate" in kinds
    if has_participants and has_subject and has_object and has_predicate:
        return "structural"
    if has_participants and (has_subject or has_object or has_predicate):
        return "mixed"
    return "heuristic"

TRUTH_BEARING_FIELDS = (
    "promotion_status",
    "support_direction",
    "conflict_state",
    "evidentiary_state",
    "operational_status",
)

NON_TRUTH_BEARING_FIELDS = (
    "coverage_status",
    "speech_act",
    "response_acts",
    "legal_significance_signals",
    "best_response_role",
    "justifications",
)

MANDATORY_CONTESTED_CANDIDATE_FIELDS = (
    "schema_version",
    "candidate_kind",
    "basis",
    "claim_span",
    "response_span",
    "speech_act",
    "polarity",
    "target_component",
    "support_direction",
    "conflict_state",
    "evidentiary_state",
)

MANDATORY_RELATION_CANDIDATE_FIELDS = (
    "schema_version",
    "candidate_kind",
    "basis",
    "event_id",
    "predicate_key",
    "subject",
    "object",
    "lane_promotion_status",
    "confidence_tier",
)

MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS = (
    "schema_version",
    "candidate_kind",
    "basis",
    "pack_id",
    "hotspot_family",
    "lane_promotion_status",
    "status",
    "cluster_count",
)


def build_contested_claim_candidate(
    *,
    basis: str,
    claim_span: Mapping[str, Any] | None,
    response_span: Mapping[str, Any] | None,
    speech_act: str,
    polarity: str,
    target_component: str,
    support_direction: str,
    conflict_state: str,
    evidentiary_state: str,
    modifiers: list[str] | None = None,
    justifications: list[Mapping[str, Any]] | None = None,
    evidence_spans: list[Mapping[str, Any]] | None = None,
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidate = {
        "schema_version": CONTESTED_CANDIDATE_SCHEMA_VERSION,
        "candidate_kind": "contested_claim",
        "basis": basis,
        "claim_span": claim_span,
        "response_span": response_span,
        "speech_act": speech_act,
        "polarity": polarity,
        "target_component": target_component,
        "support_direction": support_direction,
        "conflict_state": conflict_state,
        "evidentiary_state": evidentiary_state,
        "modifiers": list(modifiers or []),
        "justifications": list(justifications or []),
        "evidence_spans": list(evidence_spans or []),
        "rule_ids": list(rule_ids or []),
    }
    validate_contested_claim_candidate(candidate)
    return candidate


def validate_contested_claim_candidate(candidate: Mapping[str, Any]) -> None:
    missing = [field for field in MANDATORY_CONTESTED_CANDIDATE_FIELDS if field not in candidate]
    if missing:
        raise ValueError(f"Missing contested semantic candidate fields: {missing}")
    basis = str(candidate.get("basis") or "").strip()
    if basis not in CANDIDATE_BASES:
        raise ValueError(f"Unsupported candidate basis: {basis}")


def build_relation_candidate(
    *,
    basis: str,
    event_id: str,
    predicate_key: str,
    subject: Mapping[str, Any] | None,
    object: Mapping[str, Any] | None,
    lane_promotion_status: str,
    confidence_tier: str,
    receipts: list[Mapping[str, Any]] | None = None,
    evidence_spans: list[Mapping[str, Any]] | None = None,
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidate = {
        "schema_version": RELATION_CANDIDATE_SCHEMA_VERSION,
        "candidate_kind": "semantic_relation",
        "basis": basis,
        "event_id": event_id,
        "predicate_key": predicate_key,
        "subject": subject,
        "object": object,
        "lane_promotion_status": lane_promotion_status,
        "confidence_tier": confidence_tier,
        "receipts": list(receipts or []),
        "evidence_spans": list(evidence_spans or []),
        "rule_ids": list(rule_ids or []),
    }
    validate_relation_candidate(candidate)
    return candidate


def validate_relation_candidate(candidate: Mapping[str, Any]) -> None:
    missing = [field for field in MANDATORY_RELATION_CANDIDATE_FIELDS if field not in candidate]
    if missing:
        raise ValueError(f"Missing relation semantic candidate fields: {missing}")
    basis = str(candidate.get("basis") or "").strip()
    if basis not in CANDIDATE_BASES:
        raise ValueError(f"Unsupported candidate basis: {basis}")


def build_hotspot_pack_candidate(
    *,
    basis: str,
    pack_id: str,
    hotspot_family: str,
    lane_promotion_status: str,
    status: str,
    cluster_count: int,
    hold_reason: str | None = None,
    source_artifacts: list[str] | None = None,
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidate = {
        "schema_version": HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION,
        "candidate_kind": "hotspot_pack",
        "basis": basis,
        "pack_id": pack_id,
        "hotspot_family": hotspot_family,
        "lane_promotion_status": lane_promotion_status,
        "status": status,
        "cluster_count": int(cluster_count),
        "hold_reason": hold_reason,
        "source_artifacts": list(source_artifacts or []),
        "rule_ids": list(rule_ids or []),
    }
    validate_hotspot_pack_candidate(candidate)
    return candidate


def validate_hotspot_pack_candidate(candidate: Mapping[str, Any]) -> None:
    missing = [field for field in MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS if field not in candidate]
    if missing:
        raise ValueError(f"Missing hotspot pack semantic candidate fields: {missing}")
    basis = str(candidate.get("basis") or "").strip()
    if basis not in CANDIDATE_BASES:
        raise ValueError(f"Unsupported candidate basis: {basis}")


def promote_hotspot_pack_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validate_hotspot_pack_candidate(candidate)
    basis = str(candidate.get("basis") or "").strip() or "heuristic"
    lane_promotion_status = str(candidate.get("lane_promotion_status") or "").strip()

    if basis != "structural":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "non_structural_basis",
        }

    if lane_promotion_status == "promoted":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": PROMOTED_TRUE,
            "basis": basis,
            "reason": "structural_hotspot_promoted",
        }

    if lane_promotion_status in {"anchored", "promotable", "candidate"}:
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "hotspot_not_yet_promoted",
        }

    return {
        "version": SEMANTIC_PROMOTION_VERSION,
        "status": ABSTAINED,
        "basis": basis,
        "reason": "unknown_hotspot_promotion_state",
    }


def promote_relation_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validate_relation_candidate(candidate)
    basis = str(candidate.get("basis") or "").strip() or "heuristic"
    lane_promotion_status = str(candidate.get("lane_promotion_status") or "").strip()
    confidence_tier = str(candidate.get("confidence_tier") or "").strip()

    if basis != "structural":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "non_structural_basis",
        }

    if lane_promotion_status == "promoted" and confidence_tier in {"high", "medium"}:
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": PROMOTED_TRUE,
            "basis": basis,
            "reason": "structural_relation_promoted",
        }

    if lane_promotion_status == "candidate":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "relation_candidate_not_promoted",
        }

    if lane_promotion_status == "abstained":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "relation_abstained_by_lane",
        }

    return {
        "version": SEMANTIC_PROMOTION_VERSION,
        "status": ABSTAINED,
        "basis": basis,
        "reason": "unknown_relation_promotion_state",
    }


def promote_contested_claim(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validate_contested_claim_candidate(candidate)
    basis = str(candidate.get("basis") or "").strip() or "heuristic"
    support_direction = str(candidate.get("support_direction") or "").strip()
    conflict_state = str(candidate.get("conflict_state") or "").strip()
    evidentiary_state = str(candidate.get("evidentiary_state") or "").strip()

    if basis != "structural":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": ABSTAINED,
            "basis": basis,
            "reason": "non_structural_basis",
        }

    if support_direction == "mixed" or conflict_state in {"partially_reconciled", "unresolved"}:
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": CANDIDATE_CONFLICT,
            "basis": basis,
            "reason": "conflicting_structural_state",
            "needs_reconciliation": NEEDS_RECONCILIATION,
        }

    if support_direction == "against" and conflict_state == "disputed":
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": PROMOTED_FALSE,
            "basis": basis,
            "reason": "structural_denial_path",
        }

    if (
        support_direction == "for"
        and conflict_state == "undisputed"
        and evidentiary_state in {"weakly_supported", "supported", "strongly_supported"}
    ):
        return {
            "version": SEMANTIC_PROMOTION_VERSION,
            "status": PROMOTED_TRUE,
            "basis": basis,
            "reason": "structural_support_path",
        }

    return {
        "version": SEMANTIC_PROMOTION_VERSION,
        "status": ABSTAINED,
        "basis": basis,
        "reason": "insufficient_structural_promotion",
    }
