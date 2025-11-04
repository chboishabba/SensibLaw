"""Controlled vocabularies for NLP rule extraction."""

from __future__ import annotations

from enum import Enum
from typing import Dict

__all__ = [
    "Modality",
    "ConditionalPolarity",
    "ConditionalConnector",
]


class Modality(str, Enum):
    """Enumeration of supported normative modalities."""

    MUST = "modality.must"
    MUST_NOT = "modality.must_not"
    MAY = "modality.may"
    MAY_NOT = "modality.may_not"
    SHALL = "modality.shall"
    SHALL_NOT = "modality.shall_not"

    @property
    def is_negative(self) -> bool:
        """Return ``True`` if the modality expresses a prohibition."""

        return self in _NEGATIVE_MODALITIES

    @classmethod
    def normalise(cls, text: str | None) -> "Modality | None":
        """Map arbitrary text or identifier onto a canonical modality."""

        if not text:
            return None

        candidate = text.strip()
        if not candidate:
            return None

        try:
            return cls(candidate)
        except ValueError:
            pass

        key = " ".join(candidate.lower().split())
        return _MODALITY_ALIASES.get(key)


# Populate alias table after class definition to avoid mypy complaints.
_MODALITY_ALIASES: Dict[str, Modality] = {
    "must": Modality.MUST,
    "must not": Modality.MUST_NOT,
    "mustn't": Modality.MUST_NOT,
    "may": Modality.MAY,
    "may not": Modality.MAY_NOT,
    "shall": Modality.SHALL,
    "shall not": Modality.SHALL_NOT,
    "shan't": Modality.SHALL_NOT,
}

_NEGATIVE_MODALITIES: frozenset[Modality] = frozenset(
    {Modality.MUST_NOT, Modality.MAY_NOT, Modality.SHALL_NOT}
)


class ConditionalPolarity(str, Enum):
    """Polarity metadata for conditional connectors."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ConditionalConnector(str, Enum):
    """Enumeration of conditional connectors with polarity metadata."""

    IF = "condition.if"
    UNLESS = "condition.unless"
    WHEN = "condition.when"
    WHERE = "condition.where"
    PROVIDED_THAT = "condition.provided_that"
    SUBJECT_TO = "condition.subject_to"
    DESPITE = "condition.despite"
    WHILE = "condition.while"

    @property
    def polarity(self) -> ConditionalPolarity:
        """Return the polarity metadata associated with the connector."""

        return _CONNECTOR_POLARITY[self]

    @classmethod
    def normalise(cls, text: str | None) -> "ConditionalConnector | None":
        """Normalise free text onto a controlled connector identifier."""

        if not text:
            return None

        candidate = text.strip()
        if not candidate:
            return None

        try:
            return cls(candidate)
        except ValueError:
            pass

        key = " ".join(candidate.lower().split())
        return _CONNECTOR_ALIASES.get(key)


_CONNECTOR_ALIASES: Dict[str, ConditionalConnector] = {
    "if": ConditionalConnector.IF,
    "unless": ConditionalConnector.UNLESS,
    "when": ConditionalConnector.WHEN,
    "where": ConditionalConnector.WHERE,
    "provided that": ConditionalConnector.PROVIDED_THAT,
    "provided": ConditionalConnector.PROVIDED_THAT,
    "subject to": ConditionalConnector.SUBJECT_TO,
    "despite": ConditionalConnector.DESPITE,
    "while": ConditionalConnector.WHILE,
}

_CONNECTOR_POLARITY: Dict[ConditionalConnector, ConditionalPolarity] = {
    ConditionalConnector.IF: ConditionalPolarity.POSITIVE,
    ConditionalConnector.UNLESS: ConditionalPolarity.NEGATIVE,
    ConditionalConnector.WHEN: ConditionalPolarity.POSITIVE,
    ConditionalConnector.WHERE: ConditionalPolarity.POSITIVE,
    ConditionalConnector.PROVIDED_THAT: ConditionalPolarity.POSITIVE,
    ConditionalConnector.SUBJECT_TO: ConditionalPolarity.NEUTRAL,
    ConditionalConnector.DESPITE: ConditionalPolarity.NEGATIVE,
    ConditionalConnector.WHILE: ConditionalPolarity.NEUTRAL,
}

