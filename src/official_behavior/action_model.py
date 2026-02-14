from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True, slots=True)
class ActionObservation:
    """Minimal action-episode observation for descriptive plumbing.

    This is input-only: no identity inference, no extraction logic, no linkage.
    """

    action_id: str
    jurisdiction_id: str
    institution_id: str
    institution_kind: str

    action_date: Optional[str] = None  # ISO date if known
    policy_area_id: Optional[str] = None
    action_type: Optional[str] = None
    subject_key: Optional[str] = None
    outcome_label: str = ""

    # Predicate feature keys for the slice/schema.
    predicate_keys: Sequence[str] = ()

    # Explicit normative references (commitments invoked, statutes invoked, etc).
    normative_reference_ids: Sequence[str] = ()

    # Optional individual-level fields (guarded in aggregators).
    official_id: Optional[str] = None
    party_id: Optional[str] = None

    # Optional context tags (constraint badges, posture tags).
    context_keys: Sequence[str] = ()

    def normalized(self) -> "ActionObservation":
        def uniq_sorted(xs: Iterable[str]) -> tuple[str, ...]:
            return tuple(sorted({str(x).strip() for x in (xs or []) if str(x).strip()}))

        return ActionObservation(
            action_id=str(self.action_id or "").strip(),
            jurisdiction_id=str(self.jurisdiction_id or "").strip(),
            institution_id=str(self.institution_id or "").strip(),
            institution_kind=str(self.institution_kind or "").strip(),
            action_date=str(self.action_date).strip() if self.action_date else None,
            policy_area_id=str(self.policy_area_id).strip() if self.policy_area_id else None,
            action_type=str(self.action_type).strip() if self.action_type else None,
            subject_key=str(self.subject_key).strip() if self.subject_key else None,
            outcome_label=str(self.outcome_label or "").strip(),
            predicate_keys=uniq_sorted(self.predicate_keys),
            normative_reference_ids=uniq_sorted(self.normative_reference_ids),
            official_id=str(self.official_id).strip() if self.official_id else None,
            party_id=str(self.party_id).strip() if self.party_id else None,
            context_keys=uniq_sorted(self.context_keys),
        )

