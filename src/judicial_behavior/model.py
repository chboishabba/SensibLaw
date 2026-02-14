from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


class OutcomeLabel:
    """Canonical labels for descriptive outcome aggregation."""

    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    MIXED = "mixed"
    REMITTED = "remitted"
    PROCEDURAL = "procedural"
    UNKNOWN = "unknown"

    @classmethod
    def canonicalize(cls, raw: str) -> str:
        s = str(raw or "").strip().lower()
        if not s:
            return cls.UNKNOWN
        if s in {cls.PLAINTIFF, "applicant"}:
            return cls.PLAINTIFF
        if s in {cls.DEFENDANT, "respondent"}:
            return cls.DEFENDANT
        if s in {cls.MIXED, "partial"}:
            return cls.MIXED
        if s in {cls.REMITTED, "remit", "remand"}:
            return cls.REMITTED
        if s in {cls.PROCEDURAL, "strike", "dismissed_on_procedure"}:
            return cls.PROCEDURAL
        return cls.UNKNOWN


@dataclass(frozen=True, slots=True)
class CaseObservation:
    """Minimal case observation for descriptive aggregation.

    All IDs are explicit inputs; this layer performs no identity inference.
    """

    case_id: str
    jurisdiction_id: str
    court_id: str
    court_level: str
    decision_date: Optional[str] = None  # ISO date, if known
    wrong_type_id: Optional[str] = None
    predicate_keys: Sequence[str] = ()
    outcome: str = OutcomeLabel.UNKNOWN

    # Optional individual-level fields. Use only behind an explicit opt-in.
    judge_id: Optional[str] = None
    panel_ids: Sequence[str] = ()

    def normalized(self) -> "CaseObservation":
        return CaseObservation(
            case_id=str(self.case_id or "").strip(),
            jurisdiction_id=str(self.jurisdiction_id or "").strip(),
            court_id=str(self.court_id or "").strip(),
            court_level=str(self.court_level or "").strip(),
            decision_date=str(self.decision_date).strip() if self.decision_date else None,
            wrong_type_id=str(self.wrong_type_id).strip() if self.wrong_type_id else None,
            predicate_keys=tuple(sorted({str(x).strip() for x in (self.predicate_keys or []) if str(x).strip()})),
            outcome=OutcomeLabel.canonicalize(self.outcome),
            judge_id=str(self.judge_id).strip() if self.judge_id else None,
            panel_ids=tuple(sorted({str(x).strip() for x in (self.panel_ids or []) if str(x).strip()})),
        )


def normalize_observations(rows: Iterable[CaseObservation]) -> list[CaseObservation]:
    out: list[CaseObservation] = []
    for r in rows:
        if not isinstance(r, CaseObservation):
            continue
        n = r.normalized()
        if n.case_id and n.jurisdiction_id and n.court_id and n.court_level:
            out.append(n)
    # Stable ordering for deterministic downstream grouping.
    out.sort(key=lambda x: (x.jurisdiction_id, x.court_id, x.court_level, x.decision_date or "", x.case_id))
    return out

