"""Utilities for parsing legal case citations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from src.models.provision import RuleReference


_PINPOINT_RE = re.compile(r"(?:[,;]?\s+at\s+(?P<pinpoint>.+))$", re.IGNORECASE)
_NEUTRAL_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s*(?P<court>[A-Z][A-Z0-9]+)\s*(?P<number>\d+)",
)
_REPORTED_RE = re.compile(
    r"\((?P<year>\d{4})\)\s*(?P<volume>\d+)\s*(?P<reporter>[A-Z][A-Za-z. ]*?)\s+(?P<page>\d+)",
)


def _strip_pinpoint(text: str) -> tuple[str, Optional[str]]:
    match = _PINPOINT_RE.search(text)
    if not match:
        return text, None

    pinpoint = match.group("pinpoint").strip().rstrip(". ")
    pinpoint = re.sub(
        r"^(?:pp?\.?|paras?\.?|para\.?|par\.?)\s+", "", pinpoint, flags=re.IGNORECASE
    )
    cleaned = text[: match.start()].rstrip(" ,;.")
    return cleaned, pinpoint or None


@dataclass(frozen=True)
class CaseCitation:
    """Structured representation of a case citation."""

    raw: str
    case_name: Optional[str] = None
    neutral_citation: Optional[str] = None
    court: Optional[str] = None
    year: Optional[str] = None
    number: Optional[str] = None
    reported_citation: Optional[str] = None
    reporter: Optional[str] = None
    volume: Optional[str] = None
    page: Optional[str] = None
    pinpoint: Optional[str] = None

    def section_text(self) -> Optional[str]:
        if self.reported_citation:
            return self.reported_citation
        if self.neutral_citation:
            return self.neutral_citation
        return None

    def work_text(self) -> Optional[str]:
        if self.case_name:
            return self.case_name
        if self.court:
            return self.court
        if self.reporter:
            return self.reporter
        return None

    def to_rule_reference(self) -> "RuleReference":
        """Build a :class:`RuleReference` populated with parsed metadata."""

        from src.models.provision import RuleReference

        section = self.section_text()
        work = self.work_text()
        pinpoint = self.pinpoint

        return RuleReference(
            work=work,
            section=section,
            pinpoint=pinpoint,
            citation_text=self.raw or None,
        )


def parse_case_citation(raw: str) -> CaseCitation:
    """Parse ``raw`` text into structured citation components."""

    original = (raw or "").strip()
    text = re.sub(r"\s+", " ", original)
    if not text:
        return CaseCitation(raw="")

    text, pinpoint = _strip_pinpoint(text)

    neutral_match = _NEUTRAL_RE.search(text)
    reported_match = _REPORTED_RE.search(text)

    match_positions = [m.start() for m in (neutral_match, reported_match) if m]
    case_name: Optional[str] = None
    if match_positions:
        start_index = min(match_positions)
        case_name = text[:start_index].strip(" ,;") or None
    else:
        case_name = text or None

    neutral_citation: Optional[str] = None
    court: Optional[str] = None
    year: Optional[str] = None
    number: Optional[str] = None

    if neutral_match:
        neutral_citation = neutral_match.group(0).strip()
        year = neutral_match.group("year")
        court = neutral_match.group("court")
        number = neutral_match.group("number")

    reported_citation: Optional[str] = None
    reporter: Optional[str] = None
    volume: Optional[str] = None
    page: Optional[str] = None

    if reported_match:
        reported_citation = reported_match.group(0).strip()
        year = year or reported_match.group("year")
        volume = reported_match.group("volume")
        reporter = reported_match.group("reporter").strip()
        page = reported_match.group("page")

    if page is None and number is not None:
        page = number

    return CaseCitation(
        raw=original,
        case_name=case_name,
        neutral_citation=neutral_citation,
        court=court,
        year=year,
        number=number,
        reported_citation=reported_citation,
        reporter=reporter,
        volume=volume,
        page=page,
        pinpoint=pinpoint,
    )


__all__ = ["CaseCitation", "parse_case_citation"]
