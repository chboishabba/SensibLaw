"""Generic, coverage-qualified residual profiles for review and topology views.

Profiles normalize a diagnostic assessment with caller-supplied admissibility
context.  They do not infer a role, type, authority, truth, promotion, or edit.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .domain_pressure import COVERAGE_STATES, DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION


TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION = "sl.typed_residual_profile.v0_1"
CONTEXT_GATE_NAMES = (
    "entity_kind_compatible",
    "relation_compatible",
    "temporal_compatible",
    "source_pnf_compatible",
    "superclass_compatible",
    "disjointness_clear",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _gate_state(value: Any) -> str:
    if value is True:
        return "compatible"
    if value is False:
        return "incompatible"
    return "unknown"


def build_typed_residual_profile(
    *,
    assessment: Mapping[str, Any],
    context: Mapping[str, Any],
    source_revision_ref: str,
    source_anchor_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one reviewable residual carrier from an assessment and context.

    `context` is deliberately caller supplied: profiles may gate a comparison
    but cannot manufacture domain or local-role facts.
    """

    if (
        _text(assessment.get("schema_version"))
        != DOMAIN_PRESSURE_ASSESSMENT_SCHEMA_VERSION
    ):
        raise ValueError("typed residual profile requires a domain pressure assessment")
    candidate_ref = _text(assessment.get("candidate_ref"))
    revision_ref = _text(source_revision_ref)
    if not candidate_ref or not revision_ref:
        raise ValueError(
            "typed residual profile requires candidate and source revision"
        )
    coverage_state = _text(assessment.get("coverage_state"))
    if coverage_state not in COVERAGE_STATES:
        raise ValueError("typed residual profile requires known assessment coverage")
    residuals = assessment.get("residuals")
    if not isinstance(residuals, list) or not residuals:
        raise ValueError("typed residual profile requires assessment residuals")

    gates = {name: _gate_state(context.get(name)) for name in CONTEXT_GATE_NAMES}
    if coverage_state != "observed" or any(
        _text(row.get("state")) == "unresolved"
        for row in residuals
        if isinstance(row, Mapping)
    ):
        comparison_state = "unknown"
    elif any(value == "incompatible" for value in gates.values()):
        comparison_state = "masked"
    elif any(value == "unknown" for value in gates.values()):
        comparison_state = "unknown"
    else:
        comparison_state = "admissible"

    normalized_residuals = [
        deepcopy(dict(row)) for row in residuals if isinstance(row, Mapping)
    ]
    normalized_residuals.sort(key=lambda row: _text(row.get("residual_kind")))
    feature_vector = [
        {
            "feature": _text(row.get("residual_kind")),
            "state": _text(row.get("state")),
            "coverage_state": _text(row.get("coverage_state")) or coverage_state,
        }
        for row in normalized_residuals
    ]
    return {
        "schema_version": TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION,
        "candidate_ref": candidate_ref,
        "source_revision_ref": revision_ref,
        "domain_invariant_ref": _text(assessment.get("domain_invariant_ref")),
        "coverage_state": coverage_state,
        "comparison_state": comparison_state,
        "context_gates": gates,
        "residuals": normalized_residuals,
        "feature_vector": feature_vector,
        "source_anchor_refs": _strings(source_anchor_refs),
        "review_disposition": _text(assessment.get("review_disposition")),
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = [
    "CONTEXT_GATE_NAMES",
    "TYPED_RESIDUAL_PROFILE_SCHEMA_VERSION",
    "build_typed_residual_profile",
]
