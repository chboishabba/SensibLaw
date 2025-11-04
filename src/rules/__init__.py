from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .dependencies import DependencyCandidate, SentenceDependencies, get_dependencies


@dataclass(frozen=True)
class PartyLexeme:
    """Canonical information about a party classification."""

    role: str
    who_text: str
    aliases: Tuple[str, ...]


UNKNOWN_PARTY = "unknown"


ACTOR_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "data" / "ontology" / "actors.yaml"


def _load_party_lexicon() -> Dict[str, PartyLexeme]:
    with ACTOR_TAXONOMY_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    actors = data.get("actors", {})
    if not actors:
        raise ValueError("Actor taxonomy did not define any actors")

    lexicon: Dict[str, PartyLexeme] = {}
    for canonical, info in actors.items():
        role = info.get("role")
        who_text = info.get("who_text")
        if not role or not who_text:
            raise ValueError(f"Actor taxonomy entry '{canonical}' must define 'role' and 'who_text'")

        aliases = list(info.get("aliases", ()))
        if canonical not in aliases:
            aliases.append(canonical)

        seen = set()
        unique_aliases = [alias for alias in aliases if not (alias in seen or seen.add(alias))]

        lexicon[canonical] = PartyLexeme(
            role=role,
            who_text=who_text,
            aliases=tuple(unique_aliases),
        )

    return lexicon


PARTY_LEXICON: Dict[str, PartyLexeme] = _load_party_lexicon()


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

