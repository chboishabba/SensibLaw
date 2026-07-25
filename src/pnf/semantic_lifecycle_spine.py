"""Canonical pre-memory lifecycle orchestration for the PostgreSQL spine.

Definitive invalidation is constitutive, not counter-support.  It therefore
normalises to ``violated`` and ``rejected`` even when derivational evidence
produced the candidate.  ``both`` remains reserved for genuine derivational
support plus counter-support.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from .semantic_lifecycle import (
    AdmissibilityReceipt,
    CandidateAssessment,
    SemanticLifecycleResult,
    admit_factor_proposals,
    assess_factor_proposals,
    resolve_reduced_factors,
)

_DEFINITIVE_INVALIDATION_GROUNDS = {
    "missing_span",
    "incompatible_role",
    "impossible_temporal_scope",
    "incompatible_entity_type",
    "wrong_jurisdiction",
    "excess_authority",
    "failed_typed_meet",
    "invalid_translation_transport",
    "constraint_violation",
}


def normalize_definitive_invalidation(
    assessments: Sequence[CandidateAssessment],
) -> tuple[CandidateAssessment, ...]:
    output: list[CandidateAssessment] = []
    for assessment in assessments:
        grounds = set(assessment.invalidation_grounds)
        if assessment.applicable and grounds.intersection(_DEFINITIVE_INVALIDATION_GROUNDS):
            assessment = replace(assessment, outcome="violated")
        output.append(assessment)
    return tuple(sorted(output, key=lambda row: row.assessment_ref))


def build_semantic_lifecycle_spine(
    *,
    document_ref: str,
    proposals: Sequence[Any],
    reduced_factors: Sequence[Any],
    fibre_elements: Sequence[Any] = (),
    constraint_assessments: Sequence[Mapping[str, Any]] = (),
    reduction_residuals: Sequence[Any] = (),
) -> SemanticLifecycleResult:
    assessments = normalize_definitive_invalidation(
        assess_factor_proposals(
            proposals=proposals,
            fibre_elements=fibre_elements,
            constraint_assessments=constraint_assessments,
        )
    )
    admissions = admit_factor_proposals(assessments)
    resolutions = resolve_reduced_factors(
        reduced_factors=reduced_factors,
        proposals=proposals,
        assessments=assessments,
        admissions=admissions,
        reduction_residuals=reduction_residuals,
    )
    return SemanticLifecycleResult(
        document_ref=document_ref,
        assessments=assessments,
        admissions=admissions,
        resolutions=resolutions,
    )


def validate_projection_demand_factor_closure(
    *,
    demands: Iterable[Mapping[str, Any]],
    durable_factor_refs: Iterable[str],
) -> None:
    durable = {str(value) for value in durable_factor_refs if str(value)}
    missing: list[tuple[str, str]] = []
    for row in demands:
        demand_ref = str(row.get("demand_ref") or "")
        factor_ref = str(
            row.get("source_factor_ref") or row.get("factor_ref") or ""
        )
        if not factor_ref or factor_ref not in durable:
            missing.append((demand_ref, factor_ref))
    if missing:
        raise ValueError(
            "projection demands must bind durable graph factors before persistence: "
            + repr(sorted(missing))
        )


def bind_projection_demand_provenance(
    *,
    demand: Mapping[str, Any],
    durable_factor_ref: str,
    fibre_summary_ref: str,
    resolution_ref: str,
    alternative_refs: Iterable[str] = (),
) -> dict[str, Any]:
    if not durable_factor_ref:
        raise ValueError("projection demand requires durable factor ref")
    return {
        **dict(demand),
        "factor_ref": durable_factor_ref,
        "source_factor_ref": durable_factor_ref,
        "fibre_summary_ref": fibre_summary_ref,
        "source_resolution_ref": resolution_ref,
        "plural_alternative_refs": sorted(
            {str(value) for value in alternative_refs if str(value)}
        ),
        "durable_factor_binding": True,
        "fibre_summary_is_fk_target": False,
    }


__all__ = [
    "bind_projection_demand_provenance",
    "build_semantic_lifecycle_spine",
    "normalize_definitive_invalidation",
    "validate_projection_demand_factor_closure",
]
