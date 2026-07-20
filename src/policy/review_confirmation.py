"""Explicit, non-mutating reviewer confirmations for generic candidates."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .domain_invariants import (
    CONFIRMING_DISPOSITIONS,
    SELECTED_CANDIDATE_ONLY_SCOPE,
    build_trusted_conforming_member,
)


REVIEW_CONFIRMATION_SCHEMA_VERSION = "sl.review_confirmation.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_review_confirmation(
    *,
    candidate_ref: str,
    source_revision_ref: str,
    review_packet_ref: str,
    review_disposition: str,
    reviewer_authority_ref: str,
    coverage_state: str,
    decision_summary: str,
    feature_contributions: Sequence[Mapping[str, Any]],
    source_statement_refs: Sequence[str] = (),
    approved_split_plan_ref: str | None = None,
    conformance_context_ref: str | None = None,
    contribution_scope: str = SELECTED_CANDIDATE_ONLY_SCOPE,
    dependency_group_ref: str | None = None,
) -> dict[str, Any]:
    """Record a reviewer decision without promoting or editing the candidate."""

    required = {
        "candidate_ref": _text(candidate_ref),
        "source_revision_ref": _text(source_revision_ref),
        "review_packet_ref": _text(review_packet_ref),
        "reviewer_authority_ref": _text(reviewer_authority_ref),
        "decision_summary": _text(decision_summary),
    }
    missing = sorted(name for name, value in required.items() if not value)
    if missing:
        raise ValueError("review confirmation requires " + ", ".join(missing))
    disposition = _text(review_disposition)
    if disposition not in CONFIRMING_DISPOSITIONS:
        raise ValueError(
            "review confirmation requires a supported confirmed disposition"
        )
    if _text(coverage_state) != "observed":
        raise ValueError("review confirmation requires observed coverage")
    normalized_features = [
        dict(feature)
        for feature in feature_contributions
        if isinstance(feature, Mapping)
    ]
    if not normalized_features:
        raise ValueError("review confirmation requires feature contributions")
    split_plan_ref = _text(approved_split_plan_ref)
    if disposition == "confirmed_conformant_after_split" and not split_plan_ref:
        raise ValueError("confirmed split requires approved_split_plan_ref")
    context_ref = _text(conformance_context_ref)
    group_ref = _text(dependency_group_ref)
    scope = _text(contribution_scope) or SELECTED_CANDIDATE_ONLY_SCOPE
    if scope != SELECTED_CANDIDATE_ONLY_SCOPE:
        raise ValueError("review confirmation scope must be selected_candidate_only")
    if bool(context_ref) != bool(group_ref):
        raise ValueError(
            "conformance_context_ref and dependency_group_ref must be supplied together"
        )
    payload = {
        "schema_version": REVIEW_CONFIRMATION_SCHEMA_VERSION,
        **required,
        "review_disposition": disposition,
        "coverage_state": "observed",
        "source_statement_refs": _strings(source_statement_refs),
        "feature_contributions": normalized_features,
        "approved_split_plan_ref": split_plan_ref or None,
        "conformance_context_ref": context_ref or None,
        "contribution_scope": scope,
        "dependency_group_ref": group_ref or None,
        "authority": "review_confirmation_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    payload["review_decision_ref"] = "review-confirmation:" + _digest(payload)
    return payload


def build_trusted_member_from_confirmation(
    confirmation: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert an explicit confirmation into the generic invariant input."""

    if _text(confirmation.get("schema_version")) != REVIEW_CONFIRMATION_SCHEMA_VERSION:
        raise ValueError("trusted-member conversion requires a review confirmation")
    return build_trusted_conforming_member(
        candidate_ref=_text(confirmation.get("candidate_ref")),
        source_revision_ref=_text(confirmation.get("source_revision_ref")),
        review_disposition=_text(confirmation.get("review_disposition")),
        review_decision_ref=_text(confirmation.get("review_decision_ref")),
        reviewer_authority_ref=_text(confirmation.get("reviewer_authority_ref")),
        coverage_state=_text(confirmation.get("coverage_state")),
        feature_contributions=confirmation.get("feature_contributions") or (),
        source_statement_refs=confirmation.get("source_statement_refs") or (),
        conformance_context_ref=_text(confirmation.get("conformance_context_ref"))
        or None,
        contribution_scope=_text(confirmation.get("contribution_scope")),
        dependency_group_ref=_text(confirmation.get("dependency_group_ref")) or None,
    )


__all__ = [
    "REVIEW_CONFIRMATION_SCHEMA_VERSION",
    "build_review_confirmation",
    "build_trusted_member_from_confirmation",
]
