"""Ego-Contest Mitigation Kit utilities.

This module provides deterministic helpers that support negotiators when an
exchange starts to drift into positional or adversarial territory.  The kit is
entirely rule-based so that unit tests can assert specific behaviours without
depending on external language models.

Features implemented here:

* Tone audit that flags inflammatory trigger phrases and suggests neutral
  alternatives.
* Offer normaliser that rewrites free-form positions into structured issue
  summaries with explicit constraints and ranges.
* Cooling-off macros that can be dropped into correspondence to de-escalate a
  conversation while preserving rights.
* A BATNA sheet builder that highlights objective litigation risks using
  information already contained in the matter file.
* A side-by-side diff helper to display the original and suggested text
  together.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from itertools import zip_longest
from typing import Iterable, List, Mapping, MutableSequence, Sequence


TRIGGER_REWRITES = {
    "refuses": "has not agreed to",
    "demands": "requests",
    "fails to": "has not yet",
}

ISSUE_KEYWORDS = {
    "payment": "Payment terms",
    "settlement": "Settlement amount",
    "apology": "Apology wording",
    "timeline": "Implementation timeline",
    "deadline": "Implementation timeline",
    "disclosure": "Disclosure obligations",
    "costs": "Costs liability",
    "meeting": "Meeting arrangements",
}

RANGE_PATTERN = re.compile(
    r"(?P<min>\$?\d[\d,]*(?:\.\d+)?)\s*(?:to|-|through)\s*(?P<max>\$?\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
SINGLE_VALUE_PATTERN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")


def _split_lines(text: str) -> tuple[List[str], bool]:
    lines = text.splitlines()
    trailing_newline = text.endswith("\n")
    return lines, trailing_newline


def _join_lines(lines: Sequence[str], trailing_newline: bool) -> str:
    combined = "\n".join(lines)
    if trailing_newline:
        combined += "\n"
    return combined


@dataclass(slots=True)
class ToneFlag:
    """Details about a flagged trigger phrase in a piece of text."""

    trigger: str
    suggestion: str
    replacement: str
    line_number: int
    original_line: str
    rewritten_line: str


@dataclass(slots=True)
class ToneAuditResult:
    """Aggregate result of running the tone audit."""

    flags: List[ToneFlag]
    revised_text: str

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)


@dataclass(slots=True)
class OfferSummary:
    """Structured summary of a negotiation position."""

    source: str
    issue: str
    constraints: str
    acceptable_range: str

    def as_dict(self) -> Mapping[str, str]:
        return {
            "issue": self.issue,
            "constraints": self.constraints,
            "acceptable_range": self.acceptable_range,
            "source": self.source,
        }


@dataclass(slots=True)
class BATNASheet:
    """Objective factors describing the best alternative to a negotiated agreement."""

    hearing_cost: str
    timeframe: str
    disclosure_gaps: List[str]
    objective_risks: List[str]


@dataclass(slots=True)
class EgoContestReport:
    """Full output of the ego-contest mitigation kit."""

    tone_audit: ToneAuditResult
    offers: List[OfferSummary]
    cooling_off_macros: List[str]
    batna_sheet: BATNASheet
    diff: List[tuple[int, str, str]]


def tone_audit(text: str) -> ToneAuditResult:
    """Flag deterministic trigger phrases and suggest neutral rewrites."""

    lines, trailing_newline = _split_lines(text)
    revised_lines: MutableSequence[str] = list(lines)
    flags: List[ToneFlag] = []

    for index, line in enumerate(lines):
        lowered = line.lower()
        new_line = line
        for trigger, replacement in TRIGGER_REWRITES.items():
            pattern = re.compile(rf"\b{re.escape(trigger)}\b", re.IGNORECASE)
            if pattern.search(lowered):
                rewritten_line = pattern.sub(replacement, new_line)
                suggestion = (
                    f"Replace '{trigger}' with '{replacement}' to keep the tone factual."
                )
                flags.append(
                    ToneFlag(
                        trigger=trigger,
                        suggestion=suggestion,
                        replacement=replacement,
                        line_number=index + 1,
                        original_line=line,
                        rewritten_line=rewritten_line,
                    )
                )
                new_line = rewritten_line
                lowered = new_line.lower()
        revised_lines[index] = new_line

    revised_text = _join_lines(revised_lines, trailing_newline)
    return ToneAuditResult(flags=flags, revised_text=revised_text)


def side_by_side_diff(original: str, revised: str) -> List[tuple[int, str, str]]:
    """Return a simple side-by-side diff between ``original`` and ``revised``."""

    original_lines, _ = _split_lines(original)
    revised_lines, _ = _split_lines(revised)
    diff: List[tuple[int, str, str]] = []
    for line_number, pair in enumerate(
        zip_longest(original_lines, revised_lines, fillvalue=""), start=1
    ):
        diff.append((line_number, pair[0], pair[1]))
    return diff


def _detect_issue(position: str) -> str:
    lowered = position.lower()
    for keyword, title in ISSUE_KEYWORDS.items():
        if keyword in lowered:
            return title
    return "General position"


def _extract_constraints(position: str) -> str:
    lowered = position.lower()
    markers = ["within", "by", "pending", "subject to", "provided", "after"]
    constraints: List[str] = []
    for marker in markers:
        idx = lowered.find(marker)
        if idx != -1:
            fragment = position[idx:].strip()
            constraints.append(fragment)
    if constraints:
        return "; ".join(constraints)
    return "None stated"


def _extract_range(position: str) -> str:
    if match := RANGE_PATTERN.search(position):
        return f"{match.group('min')} - {match.group('max')}"
    values = SINGLE_VALUE_PATTERN.findall(position)
    if len(values) == 1:
        return values[0]
    if len(values) >= 2:
        return f"{values[0]} - {values[-1]}"
    return "Not specified"


def normalise_offers(positions: Iterable[str]) -> List[OfferSummary]:
    """Rewrite positional statements into structured offer summaries."""

    summaries: List[OfferSummary] = []
    for position in positions:
        issue = _detect_issue(position)
        constraints = _extract_constraints(position)
        acceptable_range = _extract_range(position)
        summaries.append(
            OfferSummary(
                source=position.strip(),
                issue=issue,
                constraints=constraints,
                acceptable_range=acceptable_range,
            )
        )
    return summaries


def build_batna_sheet(file_data: Mapping[str, object]) -> BATNASheet:
    """Create a BATNA sheet populated with objective litigation risks."""

    cost = str(file_data.get("cost_to_hearing") or "Estimate pending")
    timeframe = str(
        file_data.get("timeframe_to_hearing")
        or file_data.get("hearing_timeframe")
        or "Timeframe requires confirmation"
    )

    raw_disclosure = file_data.get("disclosure_gaps") or []
    if isinstance(raw_disclosure, str):
        disclosure_items = [
            item.strip()
            for item in re.split(r"[,\n;]", raw_disclosure)
            if item.strip()
        ]
    else:
        disclosure_items = [str(item) for item in raw_disclosure if str(item).strip()]

    if not disclosure_items:
        disclosure_items = ["No outstanding disclosure recorded."]

    objective_risks = [
        f"Projected hearing cost: {cost}",
        f"Estimated timeframe: {timeframe}",
    ]
    if disclosure_items == ["No outstanding disclosure recorded."]:
        objective_risks.append("Disclosure appears complete.")
    else:
        objective_risks.append("Outstanding disclosure: " + ", ".join(disclosure_items))

    return BATNASheet(
        hearing_cost=cost,
        timeframe=timeframe,
        disclosure_gaps=disclosure_items,
        objective_risks=objective_risks,
    )


def generate_cooling_off_macros(
    batna: BATNASheet, tone_flags: Sequence[ToneFlag]
) -> List[str]:
    """Provide neutral de-escalation macros."""

    macros: List[str] = []
    disclosure = [item for item in batna.disclosure_gaps if "No outstanding" not in item]
    if disclosure:
        disclosure_clause = ", ".join(disclosure)
    else:
        disclosure_clause = "the outstanding preparation items"

    macros.append(
        f"Without prejudice, we propose pausing formal replies pending disclosure of {disclosure_clause}."
    )

    macros.append(
        "Without prejudice, we remain willing to confer once the timetable is settled; "
        f"current estimate: {batna.timeframe}."
    )

    if tone_flags:
        triggers = sorted({flag.trigger for flag in tone_flags})
        macros.append(
            "We suggest all parties adopt factual language going forward; the kit flagged "
            + ", ".join(triggers)
            + " in recent correspondence."
        )
    else:
        macros.append(
            "We suggest taking 48 hours for each party to reset before the next substantive exchange."
        )

    return macros


def run_ego_contest_kit(
    communication: str, offers: Iterable[str], file_data: Mapping[str, object]
) -> EgoContestReport:
    """Execute the full Ego-Contest Mitigation Kit workflow."""

    tone_result = tone_audit(communication)
    offer_summaries = normalise_offers(offers)
    batna_sheet = build_batna_sheet(file_data)
    macros = generate_cooling_off_macros(batna_sheet, tone_result.flags)
    diff = side_by_side_diff(communication, tone_result.revised_text)

    return EgoContestReport(
        tone_audit=tone_result,
        offers=offer_summaries,
        cooling_off_macros=macros,
        batna_sheet=batna_sheet,
        diff=diff,
    )


__all__ = [
    "BATNASheet",
    "EgoContestReport",
    "OfferSummary",
    "ToneAuditResult",
    "ToneFlag",
    "build_batna_sheet",
    "generate_cooling_off_macros",
    "normalise_offers",
    "run_ego_contest_kit",
    "side_by_side_diff",
    "tone_audit",
]

