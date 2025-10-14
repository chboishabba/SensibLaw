"""Reliability-first pre-brief generation.

This module assembles a deterministic "pre-brief" for family law matters.
It focuses on high precision extractions using rule-based techniques only –
no machine learning models are involved.  The pipeline surfaces:

* Parties and key dates referenced in the source material.
* Orders sought.
* Section 60CC factor hits.
* Timestamped contradictions.
* Red flags covering missing material, deadlines and inconsistencies.
* Proof-debt summaries (facts without exhibits and vice versa).

Every extracted highlight carries a stable anchor pointing back to the
originating section so that downstream UIs can render pin-cites without
fear of dead links.  The implementation is hash-stable: given identical
inputs, the resulting :class:`PreBrief` is identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_ALLOWED_DATE_LABELS = {
    "filed",
    "filing",
    "hearing",
    "judgment",
    "trial",
    "conference",
    "deadline",
    "review",
    "order",
    "report",
    "application",
}

_S60CC_FACTOR_PATTERNS: Mapping[str, Tuple[re.Pattern[str], ...]] = {
    "benefit_meaningful_relationship": (
        re.compile(
            r"benefit\s+to\s+the\s+child\s+of\s+a\s+meaningful\s+relationship",
            re.IGNORECASE,
        ),
        re.compile(
            r"meaningful\s+relationship\s+with\s+both\s+parents",
            re.IGNORECASE,
        ),
    ),
    "need_to_protect_from_harm": (
        re.compile(
            r"protect\s+the\s+child\s+from\s+(physical|psychological)\s+harm",
            re.IGNORECASE,
        ),
        re.compile(
            r"exposure\s+to\s+(family\s+violence|abuse)",
            re.IGNORECASE,
        ),
    ),
    "child_views": (
        re.compile(
            r"views\s+of\s+the\s+child",
            re.IGNORECASE,
        ),
        re.compile(
            r"wishes\s+expressed\s+by\s+the\s+child",
            re.IGNORECASE,
        ),
    ),
    "practical_difficulty": (
        re.compile(
            r"practical\s+difficult(y|ies)\s+of\s+a\s+child\s+spending",
            re.IGNORECASE,
        ),
        re.compile(
            r"likely\s+effect\s+of\s+changes\s+in\s+circumstances",
            re.IGNORECASE,
        ),
    ),
    "capacity_of_each_parent": (
        re.compile(
            r"capacity\s+of\s+each\s+parent",
            re.IGNORECASE,
        ),
        re.compile(
            r"ability\s+of\s+(?:each|the)\s+parent\s+to\s+provide",
            re.IGNORECASE,
        ),
    ),
}

_ON_DATE_EVENT_RE = re.compile(
    r"\bOn\s+(?P<date>\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}),?\s+(?P<event>[^.;:\n]+)",
    re.IGNORECASE,
)

_DEADLINE_RE = re.compile(
    r"(?:must|shall|to)\s+(?:be\s+)?(?:filed|served|provided|completed)\s+(?:by|before)\s+(?P<date>\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_DEADLINE_LABEL_RE = re.compile(
    r"deadline\s*(?:[:\-]|on)\s*(?P<date>\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_ORDER_LINE_RE = re.compile(
    r"^(?:[-*•]|\([a-z]\)|\d+\.|Order(?:s)?\s+(?:sought|that)\s+)(?P<text>.+)$",
    re.IGNORECASE,
)

_PARTY_LINE_RE = re.compile(
    r"^\s*(?P<role>Applicant|Respondent|Mother|Father|Child|Intervener|Independent Children's Lawyer)\s*:\s*(?P<name>[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*)\s*$",
    re.MULTILINE,
)

_BETWEEN_RE = re.compile(
    r"Between\s+(?P<party1>[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*)\s+\((?P<role1>Applicant|Respondent|Mother|Father)\)\s+and\s+(?P<party2>[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*)\s+\((?P<role2>Applicant|Respondent|Mother|Father)\)",
    re.IGNORECASE,
)

_DATE_LINE_RE = re.compile(
    r"^\s*(?P<label>[A-Z][A-Za-z\s]+?)\s*(?:date|deadline)?\s*(?:[:\-]|on)\s*(?P<date>\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE | re.MULTILINE,
)

_EVENT_KEYWORDS = (
    "incident",
    "hearing",
    "application",
    "order",
    "filing",
    "conference",
    "report",
)


@dataclass(frozen=True)
class DocumentSection:
    """Simplified representation of a textual section."""

    anchor: Optional[str]
    text: str
    heading: Optional[str] = None


@dataclass(frozen=True)
class FactClaim:
    """A fact asserted in the material along with any supporting exhibits."""

    id: str
    text: str
    anchor: Optional[str]
    exhibit_ids: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class Exhibit:
    """Supporting exhibit metadata."""

    id: str
    description: str
    anchor: Optional[str]
    fact_ids: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class PartyEntry:
    role: str
    name: str
    anchor: str
    source_text: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "role": self.role,
            "name": self.name,
            "anchor": self.anchor,
            "source_text": self.source_text,
        }


@dataclass(frozen=True)
class KeyDateEntry:
    label: str
    date: str
    anchor: str
    source_text: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "date": self.date,
            "anchor": self.anchor,
            "source_text": self.source_text,
        }


@dataclass(frozen=True)
class OrderEntry:
    text: str
    anchor: str

    def to_dict(self) -> Dict[str, str]:
        return {"text": self.text, "anchor": self.anchor}


@dataclass(frozen=True)
class FactorHit:
    factor: str
    anchor: str
    snippet: str

    def to_dict(self) -> Dict[str, str]:
        return {"factor": self.factor, "anchor": self.anchor, "snippet": self.snippet}


@dataclass(frozen=True)
class ContradictionEntry:
    event: str
    dates: Tuple[str, ...]
    anchors: Tuple[str, ...]
    statements: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "event": self.event,
            "dates": list(self.dates),
            "anchors": list(self.anchors),
            "statements": list(self.statements),
        }


@dataclass(frozen=True)
class RedFlag:
    kind: str
    detail: str
    anchor: Optional[str]

    def to_dict(self) -> Dict[str, Optional[str]]:
        data: Dict[str, Optional[str]] = {"type": self.kind, "detail": self.detail}
        if self.anchor is not None:
            data["anchor"] = self.anchor
        return data


@dataclass(frozen=True)
class ProofDebtItem:
    identifier: str
    text: str
    anchor: Optional[str]

    def to_dict(self) -> Dict[str, Optional[str]]:
        data: Dict[str, Optional[str]] = {"id": self.identifier, "text": self.text}
        if self.anchor is not None:
            data["anchor"] = self.anchor
        return data


@dataclass(frozen=True)
class ProofDebtSummary:
    facts_without_exhibits: Tuple[ProofDebtItem, ...]
    exhibits_without_relevance: Tuple[ProofDebtItem, ...]

    def to_dict(self) -> Dict[str, List[Dict[str, Optional[str]]]]:
        return {
            "facts_without_exhibits": [
                item.to_dict() for item in self.facts_without_exhibits
            ],
            "exhibits_without_relevance": [
                item.to_dict() for item in self.exhibits_without_relevance
            ],
        }


@dataclass(frozen=True)
class PreBrief:
    parties: Tuple[PartyEntry, ...]
    key_dates: Tuple[KeyDateEntry, ...]
    orders_sought: Tuple[OrderEntry, ...]
    s60cc_hits: Mapping[str, Tuple[FactorHit, ...]]
    contradictions: Tuple[ContradictionEntry, ...]
    red_flags: Tuple[RedFlag, ...]
    proof_debt: ProofDebtSummary

    def to_dict(self) -> Dict[str, object]:
        return {
            "parties": [entry.to_dict() for entry in self.parties],
            "key_dates": [entry.to_dict() for entry in self.key_dates],
            "orders_sought": [entry.to_dict() for entry in self.orders_sought],
            "s60cc_hits": {
                factor: [hit.to_dict() for hit in hits]
                for factor, hits in sorted(self.s60cc_hits.items())
            },
            "contradictions": [entry.to_dict() for entry in self.contradictions],
            "red_flags": [entry.to_dict() for entry in self.red_flags],
            "proof_debt": self.proof_debt.to_dict(),
        }


def _normalise_anchor(anchor: Optional[str], fallback: str) -> str:
    anchor = (anchor or "").strip()
    if anchor:
        return anchor
    return fallback


def _parse_date(value: str) -> Optional[str]:
    value = value.strip()
    if not value:
        return None
    try:
        datetime_obj = datetime.strptime(value, "%Y-%m-%d")
        return datetime_obj.date().isoformat()
    except ValueError:
        pass
    parts = value.replace(",", "").split()
    if len(parts) == 3:
        day, month_name, year = parts
        if month_name.lower() in _MONTHS:
            try:
                day_int = int(day)
                year_int = int(year)
                datetime_obj = datetime(year_int, _MONTHS[month_name.lower()], day_int)
                return datetime_obj.date().isoformat()
            except ValueError:
                return None
    return None


def _sentence_for_span(text: str, start: int, end: int) -> str:
    before = text.rfind(".", 0, start)
    before = before + 1 if before != -1 else 0
    after = text.find(".", end)
    after = after + 1 if after != -1 else len(text)
    snippet = text[before:after].strip()
    return snippet or text[start:end].strip()


def _extract_parties(sections: Sequence[DocumentSection]) -> List[PartyEntry]:
    parties: Dict[Tuple[str, str], PartyEntry] = {}
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        text = section.text
        for match in _PARTY_LINE_RE.finditer(text):
            role = match.group("role")
            name = match.group("name")
            key = (role, name)
            if key not in parties:
                parties[key] = PartyEntry(
                    role=role,
                    name=name,
                    anchor=anchor,
                    source_text=match.group(0).strip(),
                )
        between = _BETWEEN_RE.search(text)
        if between:
            for role, name in (
                (between.group("role1"), between.group("party1")),
                (between.group("role2"), between.group("party2")),
            ):
                norm_role = role.title()
                norm_name = " ".join(part.capitalize() for part in name.split())
                key = (norm_role, norm_name)
                if key not in parties:
                    parties[key] = PartyEntry(
                        role=norm_role,
                        name=norm_name,
                        anchor=anchor,
                        source_text=between.group(0).strip(),
                    )
    ordered_roles = [
        "Applicant",
        "Respondent",
        "Mother",
        "Father",
        "Child",
        "Intervener",
        "Independent Children's Lawyer",
    ]
    return sorted(
        parties.values(),
        key=lambda entry: (
            ordered_roles.index(entry.role)
            if entry.role in ordered_roles
            else len(ordered_roles),
            entry.name,
        ),
    )


def _extract_dates(sections: Sequence[DocumentSection]) -> List[KeyDateEntry]:
    dates: Dict[Tuple[str, str], KeyDateEntry] = {}
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        text = section.text
        for match in _DATE_LINE_RE.finditer(text):
            raw_label = match.group("label").strip()
            lower_label = raw_label.lower()
            if not any(token in lower_label for token in _ALLOWED_DATE_LABELS):
                continue
            raw_date = match.group("date").strip()
            parsed_date = _parse_date(raw_date)
            if not parsed_date:
                continue
            key = (lower_label, parsed_date)
            if key not in dates:
                dates[key] = KeyDateEntry(
                    label=raw_label,
                    date=parsed_date,
                    anchor=anchor,
                    source_text=match.group(0).strip(),
                )
    return sorted(dates.values(), key=lambda entry: (entry.date, entry.label.lower()))


def _extract_orders(sections: Sequence[DocumentSection]) -> List[OrderEntry]:
    orders: List[OrderEntry] = []
    seen: set[Tuple[str, str]] = set()
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        heading = (section.heading or "").lower()
        text = section.text
        relevant = "order" in heading or "orders sought" in text.lower()
        if not relevant:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            match = _ORDER_LINE_RE.match(line)
            if not match:
                continue
            order_text = match.group("text").strip()
            key = (order_text.lower(), anchor)
            if key in seen:
                continue
            seen.add(key)
            orders.append(OrderEntry(text=order_text, anchor=anchor))
    return orders


def _extract_s60cc_hits(
    sections: Sequence[DocumentSection],
) -> Dict[str, Tuple[FactorHit, ...]]:
    hits: Dict[str, List[FactorHit]] = {factor: [] for factor in _S60CC_FACTOR_PATTERNS}
    recorded: Dict[str, set[Tuple[str, Tuple[int, int]]]] = {
        factor: set() for factor in _S60CC_FACTOR_PATTERNS
    }
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        text = section.text
        for factor, patterns in _S60CC_FACTOR_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    span = match.span()
                    key = (anchor, span)
                    if key in recorded[factor]:
                        continue
                    recorded[factor].add(key)
                    snippet = _sentence_for_span(text, *span)
                    hits[factor].append(
                        FactorHit(factor=factor, anchor=anchor, snippet=snippet)
                    )
    return {
        factor: tuple(
            sorted(entries, key=lambda hit: (hit.anchor, hit.snippet.lower()))
        )
        for factor, entries in hits.items()
        if entries
    }


def _normalize_event(event: str) -> Optional[str]:
    event_lower = re.sub(r"\s+", " ", event.strip().lower())
    if not event_lower:
        return None
    if not any(keyword in event_lower for keyword in _EVENT_KEYWORDS):
        return None
    return event_lower


def _detect_contradictions(
    sections: Sequence[DocumentSection],
) -> Tuple[ContradictionEntry, ...]:
    occurrences: Dict[str, List[Tuple[str, str, str]]] = {}
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        text = section.text
        for match in _ON_DATE_EVENT_RE.finditer(text):
            raw_date = match.group("date")
            parsed_date = _parse_date(raw_date)
            if not parsed_date:
                continue
            event_text = match.group("event")
            normalized_event = _normalize_event(event_text)
            if not normalized_event:
                continue
            statement = _sentence_for_span(text, *match.span())
            occurrences.setdefault(normalized_event, []).append(
                (parsed_date, anchor, statement)
            )
    contradictions: List[ContradictionEntry] = []
    for event, records in occurrences.items():
        unique_dates = sorted({date for date, _, _ in records})
        if len(unique_dates) <= 1:
            continue
        anchors = sorted({anchor for _, anchor, _ in records})
        statements = tuple(sorted({statement for _, _, statement in records}))
        contradictions.append(
            ContradictionEntry(
                event=event,
                dates=tuple(unique_dates),
                anchors=tuple(anchors),
                statements=statements,
            )
        )
    return tuple(sorted(contradictions, key=lambda item: item.event))


def _detect_deadlines(
    sections: Sequence[DocumentSection],
) -> List[Tuple[str, str, str]]:
    deadlines: List[Tuple[str, str, str]] = []
    for index, section in enumerate(sections):
        anchor = _normalise_anchor(section.anchor, f"section-{index + 1}")
        text = section.text
        for pattern in (_DEADLINE_RE, _DEADLINE_LABEL_RE):
            for match in pattern.finditer(text):
                parsed = _parse_date(match.group("date"))
                if not parsed:
                    continue
                snippet = _sentence_for_span(text, *match.span())
                deadlines.append((parsed, anchor, snippet))
    unique: Dict[Tuple[str, str], Tuple[str, str, str]] = {}
    for date, anchor, snippet in deadlines:
        key = (date, anchor)
        if key not in unique:
            unique[key] = (date, anchor, snippet)
    return sorted(unique.values(), key=lambda item: (item[0], item[1]))


def _build_red_flags(
    parties: Sequence[PartyEntry],
    dates: Sequence[KeyDateEntry],
    orders: Sequence[OrderEntry],
    contradictions: Sequence[ContradictionEntry],
    deadlines: Sequence[Tuple[str, str, str]],
) -> List[RedFlag]:
    flags: List[RedFlag] = []
    if not parties:
        flags.append(RedFlag(kind="missing", detail="parties", anchor=None))
    if not dates:
        flags.append(RedFlag(kind="missing", detail="key_dates", anchor=None))
    if not orders:
        flags.append(RedFlag(kind="missing", detail="orders_sought", anchor=None))
    for date, anchor, snippet in deadlines:
        flags.append(
            RedFlag(kind="deadline", detail=f"Deadline on {date}", anchor=anchor)
        )
    for contradiction in contradictions:
        flags.append(
            RedFlag(
                kind="inconsistency",
                detail=f"Conflicting dates for {contradiction.event}",
                anchor=contradiction.anchors[0] if contradiction.anchors else None,
            )
        )
    return sorted(flags, key=lambda flag: (flag.kind, flag.detail))


def _summarise_proof_debt(
    facts: Sequence[FactClaim],
    exhibits: Sequence[Exhibit],
) -> ProofDebtSummary:
    fact_items: List[ProofDebtItem] = []
    for fact in facts:
        if not list(fact.exhibit_ids):
            fact_items.append(
                ProofDebtItem(
                    identifier=fact.id,
                    text=fact.text,
                    anchor=_normalise_anchor(fact.anchor, fact.id),
                )
            )
    exhibit_items: List[ProofDebtItem] = []
    fact_links: Dict[str, set[str]] = {}
    for fact in facts:
        fact_links.setdefault(fact.id, set()).update(fact.exhibit_ids)
    referenced_exhibits: set[str] = set()
    for ids in fact_links.values():
        referenced_exhibits.update(ids)
    for exhibit in exhibits:
        if exhibit.id not in referenced_exhibits:
            exhibit_items.append(
                ProofDebtItem(
                    identifier=exhibit.id,
                    text=exhibit.description,
                    anchor=_normalise_anchor(exhibit.anchor, exhibit.id),
                )
            )
    fact_items.sort(key=lambda item: item.identifier)
    exhibit_items.sort(key=lambda item: item.identifier)
    return ProofDebtSummary(
        facts_without_exhibits=tuple(fact_items),
        exhibits_without_relevance=tuple(exhibit_items),
    )


def build_pre_brief(
    sections: Sequence[DocumentSection],
    *,
    facts: Sequence[FactClaim] | None = None,
    exhibits: Sequence[Exhibit] | None = None,
) -> PreBrief:
    """Build a :class:`PreBrief` from deterministic cues.

    Parameters
    ----------
    sections:
        Sequence of :class:`DocumentSection` objects representing the source
        material.  Anchors are required for pin-cites; missing anchors are
        filled deterministically.
    facts, exhibits:
        Optional inputs feeding the proof-debt panel.  Facts reference exhibits
        by identifier, and exhibits list any fact identifiers they support.
    """

    resolved_sections = [
        DocumentSection(
            anchor=_normalise_anchor(section.anchor, f"section-{index + 1}"),
            text=section.text,
            heading=section.heading,
        )
        for index, section in enumerate(sections)
    ]
    parties = _extract_parties(resolved_sections)
    key_dates = _extract_dates(resolved_sections)
    orders = _extract_orders(resolved_sections)
    factor_hits = _extract_s60cc_hits(resolved_sections)
    contradictions = _detect_contradictions(resolved_sections)
    deadlines = _detect_deadlines(resolved_sections)
    red_flags = _build_red_flags(parties, key_dates, orders, contradictions, deadlines)
    proof_debt = _summarise_proof_debt(facts or [], exhibits or [])
    return PreBrief(
        parties=tuple(parties),
        key_dates=tuple(key_dates),
        orders_sought=tuple(orders),
        s60cc_hits=factor_hits,
        contradictions=contradictions,
        red_flags=tuple(red_flags),
        proof_debt=proof_debt,
    )


__all__ = [
    "DocumentSection",
    "FactClaim",
    "Exhibit",
    "PreBrief",
    "build_pre_brief",
]
