from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


class ProjectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DecisionObservation:
    """Projection-only decision observation for shared descriptive plumbing.

    This type is not a storage schema. It is a normalized view.
    """

    decision_id: str
    actor_id: str
    actor_kind: str  # "judge" | "official"
    domain: str  # "judicial" | "political"
    jurisdiction_id: str
    institution_id: str

    date: Optional[str] = None  # ISO date if present
    matter_type_id: Optional[str] = None
    predicate_keys: Sequence[str] = ()
    normative_reference_ids: Sequence[str] = ()
    output_label: str = ""
    context_keys: Sequence[str] = ()

    def normalized(self) -> "DecisionObservation":
        def uniq_sorted(xs: Iterable[str]) -> tuple[str, ...]:
            return tuple(sorted({str(x).strip() for x in (xs or []) if str(x).strip()}))

        return DecisionObservation(
            decision_id=str(self.decision_id or "").strip(),
            actor_id=str(self.actor_id or "").strip(),
            actor_kind=str(self.actor_kind or "").strip(),
            domain=str(self.domain or "").strip(),
            jurisdiction_id=str(self.jurisdiction_id or "").strip(),
            institution_id=str(self.institution_id or "").strip(),
            date=str(self.date).strip() if self.date else None,
            matter_type_id=str(self.matter_type_id).strip() if self.matter_type_id else None,
            predicate_keys=uniq_sorted(self.predicate_keys),
            normative_reference_ids=uniq_sorted(self.normative_reference_ids),
            output_label=str(self.output_label or "").strip(),
            context_keys=uniq_sorted(self.context_keys),
        )


def project_case_observation(case_obs: object) -> DecisionObservation:
    """Project a judicial CaseObservation into a DecisionObservation."""
    # Imported lazily to avoid circular imports and keep this as a projection layer.
    from ..judicial_behavior.model import CaseObservation

    if not isinstance(case_obs, CaseObservation):
        raise ProjectionError("expected CaseObservation")
    o = case_obs.normalized()
    if not o.judge_id:
        raise ProjectionError("CaseObservation.judge_id required for DecisionObservation projection")
    out = DecisionObservation(
        decision_id=o.case_id,
        actor_id=o.judge_id,
        actor_kind="judge",
        domain="judicial",
        jurisdiction_id=o.jurisdiction_id,
        institution_id=o.court_id,
        date=o.decision_date,
        matter_type_id=o.wrong_type_id,
        predicate_keys=o.predicate_keys,
        normative_reference_ids=(),
        output_label=o.outcome,
        context_keys=(),
    )
    return out.normalized()


def project_action_observation(action_obs: object) -> DecisionObservation:
    """Project an official ActionObservation into a DecisionObservation."""
    from ..official_behavior.action_model import ActionObservation

    if not isinstance(action_obs, ActionObservation):
        raise ProjectionError("expected ActionObservation")
    o = action_obs.normalized()
    if not o.official_id:
        raise ProjectionError("ActionObservation.official_id required for DecisionObservation projection")
    out = DecisionObservation(
        decision_id=o.action_id,
        actor_id=o.official_id,
        actor_kind="official",
        domain="political",
        jurisdiction_id=o.jurisdiction_id,
        institution_id=o.institution_id,
        date=o.action_date,
        matter_type_id=o.policy_area_id,
        predicate_keys=o.predicate_keys,
        normative_reference_ids=o.normative_reference_ids,
        output_label=o.outcome_label,
        context_keys=o.context_keys,
    )
    return out.normalized()

