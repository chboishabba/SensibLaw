"""Immutable assessments of declared PNF constraints."""

from __future__ import annotations

from dataclasses import dataclass

from src.policy.carriers.canonical import canonical_refs, require_text


CONSTRAINT_EVALUATION_STATES = {
    "not_evaluated",
    "satisfied",
    "satisfied_with_alternatives",
    "contradicted",
    "insufficient_evidence",
}


@dataclass(frozen=True)
class ConstraintAssessment:
    """A candidate-only evaluation of one immutable constraint declaration."""

    assessment_ref: str
    constraint_ref: str
    state: str
    evidence_refs: tuple[str, ...] = ()
    residual_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.assessment_ref, "assessment_ref")
        require_text(self.constraint_ref, "constraint_ref")
        if self.state not in CONSTRAINT_EVALUATION_STATES:
            raise ValueError(f"unsupported constraint assessment state: {self.state}")

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_ref": self.assessment_ref,
            "constraint_ref": self.constraint_ref,
            "state": self.state,
            "evidence_refs": list(canonical_refs(self.evidence_refs)),
            "residual_refs": list(canonical_refs(self.residual_refs)),
            "authority": "assessment_only",
        }
