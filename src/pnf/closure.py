"""Declared closure contracts over factorized PNF graphs."""

from __future__ import annotations

from dataclasses import dataclass

from src.policy.algebra import PressureAssessment, PressureKind
from src.policy.carriers.canonical import canonical_refs, require_text

from .graph import PNFGraph


@dataclass(frozen=True)
class ClosureContract:
    contract_ref: str
    required_factor_types: tuple[str, ...]
    accepted_closure_states: tuple[str, ...] = ("closed", "locally_closed")


def assess_pnf_closure(
    graph: PNFGraph, contract: ClosureContract
) -> tuple[PressureAssessment, ...]:
    accepted = set(canonical_refs(contract.accepted_closure_states))
    factors_by_type: dict[str, list] = {}
    for factor in graph.factors:
        factors_by_type.setdefault(factor.factor_type, []).append(factor)
    assessments: list[PressureAssessment] = []
    for factor_type in canonical_refs(contract.required_factor_types):
        factors = factors_by_type.get(factor_type, [])
        if not factors:
            assessments.append(
                PressureAssessment(
                    target_ref=f"{graph.graph_ref}:{factor_type}",
                    pressure_kind=PressureKind.CLOSURE,
                    state="missing_factor",
                    reasons=("required_factor_missing",),
                    requested_actions=("construct_factor",),
                )
            )
            continue
        for factor in factors:
            closed = factor.closure_state in accepted and not factor.residuals
            assessments.append(
                PressureAssessment(
                    target_ref=factor.factor_ref,
                    pressure_kind=PressureKind.CLOSURE,
                    state="closed" if closed else "open",
                    reasons=() if closed else tuple(factor.residuals) or ("closure_state_open",),
                    requested_actions=() if closed else ("derive_resolution_demand",),
                )
            )
    require_text(contract.contract_ref, "contract_ref")
    return tuple(assessments)
