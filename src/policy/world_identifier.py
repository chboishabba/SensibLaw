"""Boundary adapters for external identifiers.

Human protocol identifiers are parsed once at the external boundary.  The
semantic hot path stores provider enum + numeric payload; it does not repeatedly
compare strings such as ``Q123``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class WorldProvider(IntEnum):
    WIKIDATA = 1


@dataclass(frozen=True, slots=True)
class NumericWorldIdentifier:
    provider: WorldProvider
    numeric_id: int

    def __post_init__(self) -> None:
        if self.numeric_id < 0:
            raise ValueError("external numeric identifier must be non-negative")


def parse_wikidata_qid(identifier: str) -> NumericWorldIdentifier:
    """Parse a Wikidata Q identifier without regex.

    This is explicitly an external-protocol boundary, not semantic inference.
    """

    value = identifier.strip()
    if len(value) < 2 or value[0] not in ("Q", "q"):
        raise ValueError("Wikidata identifier must have Q<number> form")
    digits = value[1:]
    if not digits.isascii() or not digits.isdigit():
        raise ValueError("Wikidata identifier must have Q<number> form")
    numeric = int(digits)
    if numeric <= 0:
        raise ValueError("Wikidata entity id must be positive")
    return NumericWorldIdentifier(WorldProvider.WIKIDATA, numeric)
