from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


class AlignmentLabel:
    """Canonical labels for commitment↔action alignment aggregation."""

    ALIGNED = "aligned"
    MISALIGNED = "misaligned"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"

    @classmethod
    def canonicalize(cls, raw: str) -> str:
        s = str(raw or "").strip().lower()
        if not s:
            return cls.UNKNOWN
        if s in {cls.ALIGNED, "match"}:
            return cls.ALIGNED
        if s in {cls.MISALIGNED, "mismatch", "divergent"}:
            return cls.MISALIGNED
        if s in {cls.AMBIGUOUS, "unclear"}:
            return cls.AMBIGUOUS
        if s in {cls.NOT_APPLICABLE, "n/a", "notapplicable"}:
            return cls.NOT_APPLICABLE
        return cls.UNKNOWN


@dataclass(frozen=True, slots=True)
class AlignmentObservation:
    """Minimal link-level observation for descriptive aggregation.

    This is intentionally input-only: no identity inference, no linkage logic.
    """

    link_id: str
    action_id: str
    jurisdiction_id: str
    institution_id: str
    institution_kind: str

    action_date: Optional[str] = None  # ISO date if known
    policy_area_id: Optional[str] = None
    alignment: str = AlignmentLabel.UNKNOWN

    # Optional individual-level fields (guarded in aggregation).
    official_id: Optional[str] = None
    party_id: Optional[str] = None

    # Optional descriptive context tags.
    constraint_keys: Sequence[str] = ()

    def normalized(self) -> "AlignmentObservation":
        return AlignmentObservation(
            link_id=str(self.link_id or "").strip(),
            action_id=str(self.action_id or "").strip(),
            jurisdiction_id=str(self.jurisdiction_id or "").strip(),
            institution_id=str(self.institution_id or "").strip(),
            institution_kind=str(self.institution_kind or "").strip(),
            action_date=str(self.action_date).strip() if self.action_date else None,
            policy_area_id=str(self.policy_area_id).strip() if self.policy_area_id else None,
            alignment=AlignmentLabel.canonicalize(self.alignment),
            official_id=str(self.official_id).strip() if self.official_id else None,
            party_id=str(self.party_id).strip() if self.party_id else None,
            constraint_keys=tuple(sorted({str(x).strip() for x in (self.constraint_keys or []) if str(x).strip()})),
        )


def normalize_observations(rows: Iterable[AlignmentObservation]) -> list[AlignmentObservation]:
    out: list[AlignmentObservation] = []
    for r in rows:
        if not isinstance(r, AlignmentObservation):
            continue
        n = r.normalized()
        if n.link_id and n.action_id and n.jurisdiction_id and n.institution_id and n.institution_kind:
            out.append(n)
    # Stable ordering for deterministic downstream grouping.
    out.sort(
        key=lambda x: (
            x.jurisdiction_id,
            x.institution_id,
            x.institution_kind,
            x.action_date or "",
            x.action_id,
            x.link_id,
        )
    )
    return out

