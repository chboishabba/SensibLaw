"""Canonical orchestration for the explicit PNF semantic lifecycle.

The lower-level reducer reports all incompatibility relationships. This wrapper
applies admissibility before semantic resolution: positively rejected readings
no longer keep an otherwise unique admissible reading conflicted, while blocked
or underdetermined alternatives continue to prevent premature selection.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.pnf.semantic_lifecycle import (
    SemanticLifecycleResult,
    admit_factor_proposals,
    assess_factor_proposals,
    resolve_reduced_factors,
)


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(
        value, name, default
    )


def _admission_aware_residuals(
    *,
    residuals: Sequence[Any],
    admission_states: Mapping[str, str],
) -> tuple[Any, ...]:
    output: list[Any] = []
    for residual in residuals:
        residual_type = str(_get(residual, "residual_type", "") or "")
        if residual_type != "incompatible_alternatives":
            output.append(residual)
            continue
        live_refs = tuple(
            sorted(
                {
                    str(ref)
                    for ref in _get(residual, "proposal_refs", ()) or ()
                    if admission_states.get(str(ref)) != "rejected"
                }
            )
        )
        if len(live_refs) < 2:
            continue
        output.append(
            {
                "residual_ref": str(_get(residual, "residual_ref", "") or ""),
                "document_ref": str(_get(residual, "document_ref", "") or ""),
                "residual_type": residual_type,
                "proposal_refs": live_refs,
                "message": str(_get(residual, "message", "") or ""),
                "semantic_coordinate_ref": _get(
                    residual, "semantic_coordinate_ref", None
                ),
                "boundary_kind": str(
                    _get(residual, "boundary_kind", "fibre") or "fibre"
                ),
            }
        )
    return tuple(output)


def build_admission_aware_semantic_lifecycle(
    *,
    document_ref: str,
    proposals: Sequence[Any],
    reduced_factors: Sequence[Any],
    fibre_elements: Sequence[Any] = (),
    constraint_assessments: Sequence[Mapping[str, Any]] = (),
    reduction_residuals: Sequence[Any] = (),
) -> SemanticLifecycleResult:
    assessments = assess_factor_proposals(
        proposals=proposals,
        fibre_elements=fibre_elements,
        constraint_assessments=constraint_assessments,
    )
    admissions = admit_factor_proposals(assessments)
    admission_states = {row.proposal_ref: row.state for row in admissions}
    filtered_residuals = _admission_aware_residuals(
        residuals=reduction_residuals,
        admission_states=admission_states,
    )
    return SemanticLifecycleResult(
        document_ref=document_ref,
        assessments=assessments,
        admissions=admissions,
        resolutions=resolve_reduced_factors(
            reduced_factors=reduced_factors,
            proposals=proposals,
            assessments=assessments,
            admissions=admissions,
            reduction_residuals=filtered_residuals,
        ),
    )


__all__ = ["build_admission_aware_semantic_lifecycle"]
