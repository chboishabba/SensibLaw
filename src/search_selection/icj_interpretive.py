from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class InterpretiveAuthority:
    name: str
    reference: str
    charter_article: str
    summary: str


ICJ_CASES: Mapping[str, InterpretiveAuthority] = {
    "nicaragua": InterpretiveAuthority(
        name="Nicaragua v. United States",
        reference="ICJ Reports 1986, p. 14",
        charter_article="Article 2(4)",
        summary="Reinforces prohibition on the use of force and affirms jurisdiction.",
    ),
    "oil_platforms": InterpretiveAuthority(
        name="Oil Platforms (Iran v. United States)",
        reference="ICJ Reports 2003, p. 161",
        charter_article="Article 51",
        summary="Clarifies self-defense scope, requiring necessity and proportionality.",
    ),
    "wall": InterpretiveAuthority(
        name="Legal Consequences of the Construction of a Wall",
        reference="ICJ Reports 2004, p. 136",
        charter_article="Article 2(4)",
        summary="Describes humanitarian obligations when a wall encroaches on territory.",
    ),
}


def lookup_interpretive_authority(tag: str) -> InterpretiveAuthority | None:
    return ICJ_CASES.get(tag.lower().strip())
