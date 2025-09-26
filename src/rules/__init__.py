from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PartyLexeme:
    """Canonical information about a party classification."""

    role: str
    who_text: str
    aliases: Tuple[str, ...]


UNKNOWN_PARTY = "unknown"


PARTY_LEXICON: Dict[str, PartyLexeme] = {
    "court": PartyLexeme(
        role="decision_maker",
        who_text="the court",
        aliases=(
            "court",
            "the court",
            "judge",
            "the judge",
            "justice",
            "magistrate",
            "tribunal",
            "sentencing judge",
        ),
    ),
    "prosecution": PartyLexeme(
        role="prosecutor",
        who_text="the prosecution",
        aliases=(
            "prosecution",
            "the prosecution",
            "prosecutor",
            "prosecutors",
            "crown",
            "director of public prosecutions",
            "dpp",
            "attorney general",
            "the state",
            "district attorney",
        ),
    ),
    "defence": PartyLexeme(
        role="accused",
        who_text="the accused",
        aliases=(
            "defendant",
            "defendants",
            "defence",
            "defense",
            "accused",
            "respondent",
            "respondents",
            "appellant",
            "offender",
            "offenders",
            "prisoner",
            "person charged",
            "the person charged",
        ),
    ),
    "police": PartyLexeme(
        role="law_enforcement",
        who_text="law enforcement",
        aliases=(
            "police",
            "police officer",
            "police officers",
            "constable",
            "constables",
            "sheriff",
            "law enforcement",
        ),
    ),
    "victim": PartyLexeme(
        role="victim",
        who_text="the victim",
        aliases=(
            "victim",
            "victims",
            "complainant",
            "complainants",
            "survivor",
            "survivors",
        ),
    ),
    "other": PartyLexeme(
        role="public_body",
        who_text="the authority",
        aliases=(
            "minister",
            "the minister",
            "secretary",
            "director",
            "commission",
            "board",
            "authority",
            "department",
            "agency",
            "regulator",
            "council",
            "committee",
        ),
    ),
}


def _normalise(text: str) -> str:
    """Lowercase and collapse non-alphabetic characters for matching."""

    return re.sub(r"[^a-z]+", " ", text.lower()).strip()


def _contains_alias(normalised: str, alias: str) -> bool:
    """Return ``True`` if ``alias`` is a discrete substring of ``normalised``."""

    haystack = f" {normalised} "
    needle = f" {alias} "
    return needle in haystack


def _match_party(normalised: str) -> tuple[str, Optional[PartyLexeme]]:
    for party, info in PARTY_LEXICON.items():
        if any(_contains_alias(normalised, _normalise(alias)) for alias in info.aliases):
            return party, info
    return UNKNOWN_PARTY, None


def derive_party_metadata(actor: str, modality: Optional[str] = None) -> Tuple[str, Optional[str], str]:
    """Derive party metadata for an actor/modality pair."""

    text = (actor or "").strip()
    if not text:
        return UNKNOWN_PARTY, None, ""

    normalised = _normalise(text)
    party, info = _match_party(normalised)
    if info:
        return party, info.role, info.who_text

    role: Optional[str] = None
    who_text = text
    modality_lower = (modality or "").lower()
    tokens = normalised.split()

    if any(keyword in modality_lower for keyword in ("commits", "is guilty")):
        party = "defence"
        role = "accused"
        who_text = "the accused"
    elif any(token in tokens for token in ("person", "persons", "individual", "individuals")):
        party = "defence"
        role = "accused"
        if "person" in tokens:
            who_text = "the person"
        elif "persons" in tokens:
            who_text = "the persons"
        elif "individuals" in tokens:
            who_text = "the individuals"
        else:
            who_text = "the individual"
    else:
        party = UNKNOWN_PARTY

    return party, role, who_text


@dataclass
class Rule:
    """A simple representation of a normative rule."""

    actor: str
    modality: str
    action: str
    conditions: Optional[str] = None
    scope: Optional[str] = None
    elements: Dict[str, List[str]] = field(default_factory=dict)
    party: str = UNKNOWN_PARTY
    role: Optional[str] = None
    who_text: Optional[str] = None

    def __post_init__(self) -> None:
        if self.who_text is None:
            self.who_text = self.actor.strip()

