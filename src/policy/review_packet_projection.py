"""Compact generic reviewer-packet projections from residual profiles."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .residual_profiles import TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION


REVIEW_PACKET_PROJECTION_SCHEMA_VERSION = "sl.review_packet_projection.v0_2"
DECOMPOSITION_CONFIRMATION_CHOICES = (
    "confirm_split_plan",
    "reject_split_plan",
    "request_revised_split",
    "hold_unresolved",
)
MODEL_CONFIRMATION_CHOICES = (
    "confirm_model_conformant",
    "reject_conformance",
    "hold_unresolved",
)
CONFLICT_CONFIRMATION_CHOICES = (
    "confirm_hold",
    "request_reconstruction",
    "mark_legitimate_exception",
    "hold_unresolved",
)
CONFIRMATION_CHOICES = DECOMPOSITION_CONFIRMATION_CHOICES


def _review_kind(candidate_record: Mapping[str, Any]) -> str:
    """Classify generic packet interaction, never a domain decision."""

    classification = _text(candidate_record.get("classification"))
    if classification in {"safe_equivalent", "safe_with_reference_transfer"}:
        return "model_conformance"
    context = candidate_record.get("statement_family_context")
    if isinstance(context, Mapping) and (
        _text(context.get("scope_partition_state"))
        in {"overlapping", "overloaded", "incomplete"}
        or _text(context.get("total_component_relation")) == "contradiction"
    ):
        return "family_conflict"
    if classification == "split_required":
        return "decomposition"
    return "model_conformance"


def _confirmation_choices(review_kind: str) -> tuple[str, ...]:
    if review_kind == "decomposition":
        return DECOMPOSITION_CONFIRMATION_CHOICES
    if review_kind == "family_conflict":
        return CONFLICT_CONFIRMATION_CHOICES
    return MODEL_CONFIRMATION_CHOICES


def _text(value: Any) -> str:
    return str(value or "").strip()


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rows(values: Sequence[Any]) -> list[dict[str, Any]]:
    return [deepcopy(dict(value)) for value in values if isinstance(value, Mapping)]


def build_review_packet_projection(
    *,
    residual_profile: Mapping[str, Any],
    candidate_record: Mapping[str, Any],
    source_revision_ref: str,
    proposed_decomposition: Mapping[str, Any] | None = None,
    source_anchor_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Project one generic review packet; no decision or edit is performed."""

    if (
        _text(residual_profile.get("schema_version"))
        != TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION
    ):
        raise ValueError("review packet requires a typed residual profile")
    candidate_ref = _text(residual_profile.get("candidate_ref"))
    revision_ref = _text(source_revision_ref)
    if not candidate_ref or not revision_ref:
        raise ValueError("review packet requires candidate and source revision")
    before = candidate_record.get("claim_bundle_before")
    after = candidate_record.get("claim_bundle_after")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ValueError("review packet requires before and proposed after records")
    review_kind = _review_kind(candidate_record)
    family_context = candidate_record.get("statement_family_context")
    residuals = _rows(residual_profile.get("residuals") or ())
    payload = {
        "schema_version": REVIEW_PACKET_PROJECTION_SCHEMA_VERSION,
        "candidate_ref": candidate_ref,
        "source_revision_ref": revision_ref,
        "source_statement_id": _text(candidate_record.get("source_statement_id"))
        or None,
        "subject_ref": _text(candidate_record.get("entity_qid"))
        or _text(before.get("subject")),
        "source_statement": deepcopy(dict(before)),
        "proposed_target_statement": deepcopy(dict(after)),
        "statement_family": {
            "classification": _text(candidate_record.get("classification")),
            "review_disposition": _text(residual_profile.get("review_disposition")),
            "subject_family": _text(candidate_record.get("subject_family")),
            "semantic_family": _text(candidate_record.get("ghg_semantic_family")),
            "context": deepcopy(dict(family_context))
            if isinstance(family_context, Mapping)
            else {},
        },
        "review_kind": review_kind,
        "residual_profile": deepcopy(dict(residual_profile)),
        "conflict_evidence": [
            row
            for row in residuals
            if _text(row.get("residual_kind"))
            in {
                "scope_overlap",
                "component_total_contradiction",
                "period_mismatch",
                "multi_year_family",
                "duplicate_scope",
                "unknown_scope_partition",
                "reference_partition_ambiguity",
            }
        ],
        "split_boundaries": _rows(candidate_record.get("split_axes") or ()),
        "proposed_decomposition": deepcopy(dict(proposed_decomposition or {})),
        "qualifier_reference_carry_plan": {
            "qualifiers": deepcopy(dict(before.get("qualifiers") or {})),
            "references": _rows(before.get("references") or ()),
            "preserve_exactly": (
                before.get("qualifiers") == after.get("qualifiers")
                and before.get("references") == after.get("references")
            ),
        },
        "coverage_limitations": [
            row["residual_kind"]
            for row in residual_profile.get("residuals", [])
            if isinstance(row, Mapping) and _text(row.get("state")) == "unresolved"
        ],
        "source_anchor_refs": sorted(
            {_text(ref) for ref in source_anchor_refs if _text(ref)}
        ),
        "confirmation_choices": list(_confirmation_choices(review_kind)),
        "authority": "review_packet_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    payload["packet_id"] = "review-packet:" + _digest(payload)
    return payload


__all__ = [
    "CONFLICT_CONFIRMATION_CHOICES",
    "CONFIRMATION_CHOICES",
    "DECOMPOSITION_CONFIRMATION_CHOICES",
    "MODEL_CONFIRMATION_CHOICES",
    "REVIEW_PACKET_PROJECTION_SCHEMA_VERSION",
    "build_review_packet_projection",
]
