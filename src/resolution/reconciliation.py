"""Derive structural reconciliation outcomes from typed meet products."""

from __future__ import annotations

from dataclasses import dataclass

from src.policy.algebra import MeetState, TypedMeet
from src.policy.carriers.canonical import canonical_refs, require_text


@dataclass(frozen=True)
class ReconciliationAssessment:
    assessment_ref: str
    subject_ref: str
    meets: tuple[TypedMeet, ...]
    outcome: str
    residual_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "sl.reconciliation_assessment.v0_1",
            "assessment_ref": require_text(self.assessment_ref, "assessment_ref"),
            "subject_ref": require_text(self.subject_ref, "subject_ref"),
            "meets": [
                row.to_dict()
                for row in sorted(self.meets, key=lambda value: value.meet_ref)
            ],
            "outcome": require_text(self.outcome, "outcome"),
            "residual_refs": list(canonical_refs(self.residual_refs)),
            "authority": "assessment_only",
        }


def reconcile_meets(
    *, assessment_ref: str, subject_ref: str, meets: tuple[TypedMeet, ...]
) -> ReconciliationAssessment:
    states = {MeetState(meet.state) for meet in meets}
    residuals = tuple(
        sorted({ref for meet in meets for ref in meet.residual_refs})
    )
    if MeetState.CONTRADICTION in states:
        outcome = "contradiction"
    elif MeetState.NO_TYPED_MEET in states:
        outcome = "no_typed_meet"
    elif not meets or MeetState.NOT_EVALUATED in states:
        outcome = "not_evaluated"
    elif states.issubset({MeetState.COMPATIBLE, MeetState.NOT_APPLICABLE}):
        outcome = "resolved"
    elif states.issubset(
        {
            MeetState.COMPATIBLE,
            MeetState.COMPATIBLE_WITH_REFINEMENT,
            MeetState.NOT_APPLICABLE,
        }
    ):
        outcome = "compatible_with_refinement"
    else:
        outcome = "possible_same"
    return ReconciliationAssessment(
        assessment_ref=assessment_ref,
        subject_ref=subject_ref,
        meets=meets,
        outcome=outcome,
        residual_refs=residuals,
    )
