"""Immutable factor refinements and residual transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from src.policy.carriers.canonical import canonical_refs, require_text

from .factors import Factor

T = TypeVar("T")


@dataclass(frozen=True)
class ResidualTransition:
    residual_ref: str
    prior_state: str
    resulting_state: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "residual_ref": require_text(self.residual_ref, "residual_ref"),
            "prior_state": require_text(self.prior_state, "prior_state"),
            "resulting_state": require_text(self.resulting_state, "resulting_state"),
            "evidence_refs": list(canonical_refs(self.evidence_refs)),
        }


@dataclass(frozen=True)
class FactorRefinement(Generic[T]):
    refinement_ref: str
    prior_factor: Factor[T]
    resulting_factor: Factor[T]
    added_alternative_refs: tuple[str, ...] = ()
    retained_alternative_refs: tuple[str, ...] = ()
    rejected_alternative_refs: tuple[str, ...] = ()
    residual_transitions: tuple[ResidualTransition, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        if self.prior_factor.factor_ref != self.resulting_factor.factor_ref:
            raise ValueError("factor refinement cannot change factor identity")
        groups = [
            set(canonical_refs(self.added_alternative_refs)),
            set(canonical_refs(self.retained_alternative_refs)),
            set(canonical_refs(self.rejected_alternative_refs)),
        ]
        if groups[0].intersection(groups[2]):
            raise ValueError("an alternative cannot be both added and rejected")
        return {
            "refinement_ref": require_text(self.refinement_ref, "refinement_ref"),
            "prior_factor": self.prior_factor.to_dict(),
            "resulting_factor": self.resulting_factor.to_dict(),
            "added_alternative_refs": sorted(groups[0]),
            "retained_alternative_refs": sorted(groups[1]),
            "rejected_alternative_refs": sorted(groups[2]),
            "residual_transitions": [
                row.to_dict()
                for row in sorted(
                    self.residual_transitions, key=lambda value: value.residual_ref
                )
            ],
            "evidence_refs": list(canonical_refs(self.evidence_refs)),
            "authority": "pnf_refinement_only",
        }
