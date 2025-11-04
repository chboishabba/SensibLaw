"""Shared spaCy matcher utilities for rule extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.vocab import Vocab

from .taxonomy import ConditionalConnector, Modality

MODALITY_LABEL = "MODALITY"
CONDITION_LABEL = "CONDITION"
REFERENCE_LABEL = "REFERENCE"
PENALTY_LABEL = "PENALTY"

__all__ = [
    "MODALITY_LABEL",
    "CONDITION_LABEL",
    "REFERENCE_LABEL",
    "PENALTY_LABEL",
    "RuleMatch",
    "RuleMatchSummary",
    "get_rule_matcher",
    "match_rules",
]


@dataclass(frozen=True)
class RuleMatch:
    """A matched span returned by the rule matcher."""

    label: str
    start: int
    end: int

    def span(self, doc: Doc) -> Span:
        return doc[self.start : self.end]


@dataclass
class RuleMatchSummary:
    """Aggregate rule matches grouped by semantic role."""

    matches: List[RuleMatch]
    modalities: List[str]
    primary_modality: str | None
    conditions: List[str]
    references: List[str]


_MATCHER_CACHE: Dict[int, Matcher] = {}


_MODALITY_PATTERNS: Sequence[Sequence[Dict[str, object]]] = [
    [{"LOWER": "must"}, {"LOWER": "not"}],
    [{"LOWER": "may"}, {"LOWER": "not"}],
    [{"LOWER": "shall"}, {"LOWER": "not"}],
    [{"LOWER": "must"}],
    [{"LOWER": "may"}],
    [{"LOWER": "shall"}],
]

_CONDITION_PATTERNS: Sequence[Sequence[Dict[str, object]]] = [
    [{"LOWER": "if"}],
    [{"LOWER": "unless"}],
    [{"LOWER": "despite"}],
    [{"LOWER": "subject"}, {"LOWER": "to"}],
    [{"LOWER": "when"}],
    [{"LOWER": "where"}],
    [{"LOWER": "while"}],
    [{"LOWER": "provided"}, {"LOWER": "that"}],
]

_REFERENCE_PATTERNS: Sequence[Sequence[Dict[str, object]]] = [
    [
        {"LOWER": {"IN": ["s", "ss", "section", "sections", "rule", "rules", "regulation", "regulations"]}},
        {"TEXT": {"REGEX": r"^\d+[A-Za-z]*(?:\([^)]*\))*\.?$"}},
    ],
    [
        {"LOWER": {"IN": ["part", "division", "chapter", "schedule"]}},
        {"TEXT": {"REGEX": r"^[A-Z0-9IVXLC]+(?:\.\d+)?$"}},
    ],
    [
        {"LOWER": "this"},
        {"LOWER": {"IN": ["act", "part", "division", "chapter", "schedule"]}},
    ],
]

_PENALTY_PATTERNS: Sequence[Sequence[Dict[str, object]]] = [
    [
        {"LOWER": {"IN": ["penalty", "maximum"]}},
        {"LOWER": {"IN": ["units", "unit"]}, "OP": "?"},
    ],
]

_PATTERN_TABLE: Sequence[tuple[str, Sequence[Sequence[Dict[str, object]]]]] = (
    (MODALITY_LABEL, _MODALITY_PATTERNS),
    (CONDITION_LABEL, _CONDITION_PATTERNS),
    (REFERENCE_LABEL, _REFERENCE_PATTERNS),
    (PENALTY_LABEL, _PENALTY_PATTERNS),
)


def get_rule_matcher(vocab: Vocab) -> Matcher:
    """Return a cached :class:`~spacy.matcher.Matcher` for the provided vocab."""

    key = id(vocab)
    matcher = _MATCHER_CACHE.get(key)
    if matcher is not None:
        return matcher

    matcher = Matcher(vocab, validate=True)
    for label, patterns in _PATTERN_TABLE:
        matcher.add(label, list(patterns), greedy="LONGEST")
    _MATCHER_CACHE[key] = matcher
    return matcher


def _normalise_modality(span: Span) -> str | None:
    text = " ".join(token.lower_ for token in span if not token.is_space)
    modality = Modality.normalise(text)
    return modality.value if modality else None


def _normalise_condition(span: Span) -> str | None:
    text = " ".join(token.lower_ for token in span if not token.is_space)
    connector = ConditionalConnector.normalise(text)
    return connector.value if connector else None


def _normalise_reference(span: Span) -> str:
    text = span.text.strip()
    while text and text[-1] in ",.;:":
        text = text[:-1].rstrip()
    return text


def match_rules(doc: Doc) -> RuleMatchSummary:
    """Apply the shared matcher to ``doc`` returning aggregated matches."""

    matcher = get_rule_matcher(doc.vocab)
    matches_raw = matcher(doc)
    matches: List[RuleMatch] = []
    modalities: List[str] = []
    conditions: List[str] = []
    references: List[str] = []
    seen_modalities: set[str] = set()
    seen_conditions: set[str] = set()
    seen_references: set[str] = set()

    for match_id, start, end in matches_raw:
        label = doc.vocab.strings[match_id]
        span = doc[start:end]
        matches.append(RuleMatch(label=label, start=start, end=end))
        if label == MODALITY_LABEL:
            value = _normalise_modality(span)
            if value and value not in seen_modalities:
                seen_modalities.add(value)
                modalities.append(value)
        elif label == CONDITION_LABEL:
            value = _normalise_condition(span)
            if value and value not in seen_conditions:
                seen_conditions.add(value)
                conditions.append(value)
        elif label == REFERENCE_LABEL:
            value = _normalise_reference(span)
            key = value.lower()
            if value and key not in seen_references:
                seen_references.add(key)
                references.append(value)

    primary_modality = modalities[0] if modalities else None

    return RuleMatchSummary(
        matches=matches,
        modalities=modalities,
        primary_modality=primary_modality,
        conditions=conditions,
        references=references,
    )
