"""Rule matching utilities built on spaCy matchers."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, List, Optional

import spacy
from spacy.language import Language
from spacy.matcher import DependencyMatcher, Matcher
from spacy.tokens import Doc, Span


CONDITION_MARKER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("subject to", "subject to"),
    ("if", "if"),
    ("unless", "unless"),
    ("despite", "despite"),
    ("when", "when"),
    ("where", "where"),
)


@dataclass
class RuleMatchResult:
    """Container for the lexical elements extracted from a provision."""

    modalities: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._modality_positions: dict[str, int] = {}

    def as_dict(self) -> dict[str, List[str]]:
        """Return the matches as a serialisable dictionary."""

        return {
            "modalities": list(self.modalities),
            "conditions": list(self.conditions),
            "condition_markers": self.condition_markers,
            "references": list(self.references),
            "penalties": list(self.penalties),
        }

    @property
    def condition_markers(self) -> List[str]:
        """Return the unique lexical triggers for conditional clauses."""

        markers: List[str] = []
        seen: set[str] = set()
        for condition in self.conditions:
            marker = _normalise_condition_marker(condition)
            if marker and marker not in seen:
                seen.add(marker)
                markers.append(marker)
        return markers

    @property
    def primary_modality(self) -> Optional[str]:
        """Return the most specific modality match, if any."""

        if not self.modalities:
            return None
        return min(
            self.modalities,
            key=lambda mod: (self._modality_positions.get(mod, float("inf")), -len(mod)),
        )


def _normalise_condition_marker(condition: str) -> Optional[str]:
    lowered = condition.strip().lower()
    for prefix, marker in CONDITION_MARKER_PREFIXES:
        if lowered.startswith(prefix):
            return marker
    return None


class RuleMatcher:
    """High-level helper that exposes spaCy matcher utilities."""

    def __init__(self, nlp: Language | None = None) -> None:
        self.nlp = nlp or _create_default_language()
        if "sentencizer" not in self.nlp.pipe_names:
            self.nlp.add_pipe("sentencizer")

        self.matcher = Matcher(self.nlp.vocab)
        self.dep_matcher = DependencyMatcher(self.nlp.vocab)
        self._register_patterns()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, text: str) -> RuleMatchResult:
        """Process ``text`` and extract the lexical rule components."""

        doc = self.nlp(text)
        return self.extract_from_doc(doc)

    def extract_from_doc(self, doc: Doc) -> RuleMatchResult:
        """Return rule matches for a pre-tokenised document."""

        result = RuleMatchResult()
        seen: dict[str, set[str]] = {
            "MODALITY": set(),
            "CONDITION": set(),
            "REFERENCE": set(),
            "PENALTY": set(),
        }

        condition_marks: List[Span] = []
        for match_id, start, end in self.matcher(doc):
            label = self.nlp.vocab.strings[match_id]
            span = doc[start:end]
            text = span.text.strip()
            key = text.lower()

            if label == "MODALITY":
                if key not in seen[label]:
                    result.modalities.append(key)
                    seen[label].add(key)
                    result._modality_positions[key] = start
            elif label == "REFERENCE":
                if key not in seen[label]:
                    result.references.append(text)
                    seen[label].add(key)
            elif label == "PENALTY":
                if key not in seen[label]:
                    result.penalties.append(text)
                    seen[label].add(key)
            elif label == "CONDITION_MARK":
                condition_marks.append(span)

        extracted_token_ranges: set[tuple[int, int]] = set()
        if doc.has_annotation("DEP"):
            for match_id, token_ids in self.dep_matcher(doc):
                label = self.nlp.vocab.strings[match_id]
                if label != "CONDITION":
                    continue

                tokens = [doc[i] for i in token_ids]
                mark_token = tokens[0]
                clause_token = tokens[1] if len(tokens) > 1 else tokens[0]
                subtree_tokens = list(clause_token.subtree)
                span_tokens = subtree_tokens + [mark_token]
                start = min(token.i for token in span_tokens)
                end = max(token.i for token in span_tokens) + 1

                span = doc[start:end]
                text = span.text.strip().rstrip(".,;:").strip()
                key = text.lower()
                if key and key not in seen["CONDITION"]:
                    result.conditions.append(key)
                    seen["CONDITION"].add(key)
                    extracted_token_ranges.add((start, end))

        if not result.conditions:
            for mark in condition_marks:
                sentence = mark.sent if mark.doc.has_annotation("SENT_START") else doc[:]
                start = mark.start
                end = sentence.end
                # ensure we do not duplicate ranges already captured via dependencies
                if any(start >= r[0] and end <= r[1] for r in extracted_token_ranges):
                    continue
                text = doc[start:end].text.strip().rstrip(".,;:").strip()
                key = text.lower()
                if key and key not in seen["CONDITION"]:
                    result.conditions.append(key)
                    seen["CONDITION"].add(key)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _register_patterns(self) -> None:
        self.matcher.add(
            "MODALITY",
            [
                [{"LOWER": {"IN": ["must", "shall", "may"]}}, {"LOWER": "not"}],
                [{"LOWER": {"IN": ["must", "shall", "may"]}}],
                [
                    {"LOWER": "commits"},
                    {"OP": "?", "LOWER": "the"},
                    {"OP": "?", "LOWER": "offence"},
                    {"OP": "?", "LOWER": "of"},
                ],
                [{"LOWER": "is"}, {"LOWER": "guilty"}, {"LOWER": "of"}],
            ],
            greedy="LONGEST",
        )

        self.matcher.add(
            "CONDITION_MARK",
            [
                [{"LOWER": {"IN": ["if", "unless", "despite", "when", "where"]}}],
                [{"LOWER": "subject"}, {"LOWER": "to"}],
            ],
        )

        self.matcher.add(
            "REFERENCE",
            [
                [{"LOWER": {"IN": ["s", "section"]}}, {"TEXT": {"REGEX": r"\d+[A-Za-z]?"}}],
                [
                    {"LOWER": "this"},
                    {"LOWER": {"IN": ["act", "part", "division", "subdivision"]}},
                ],
            ],
        )

        self.matcher.add(
            "PENALTY",
            [
                [
                    {"LOWER": "penalty"},
                    {"LOWER": "of"},
                    {"OP": "?", "IS_CURRENCY": True},
                    {"LIKE_NUM": True},
                    {"OP": "?", "LOWER": "penalty"},
                    {"OP": "?", "LOWER": "units"},
                ],
                [{"LIKE_NUM": True}, {"LOWER": "penalty"}, {"LOWER": "units"}],
            ],
        )

        self.matcher.add(
            "CONDITION",
            [[{"LOWER": {"IN": ["if", "unless", "despite", "when", "where"]}}]],
        )

        self.dep_matcher.add(
            "CONDITION",
            [
                [
                    {
                        "RIGHT_ID": "mark",
                        "RIGHT_ATTRS": {
                            "DEP": "mark",
                            "LEMMA": {"IN": ["if", "unless", "when", "where"]},
                        },
                    },
                    {
                        "LEFT_ID": "mark",
                        "REL_OP": ">",
                        "RIGHT_ID": "clause",
                        "RIGHT_ATTRS": {
                            "DEP": {"IN": ["advcl", "ccomp", "xcomp", "acl"]}
                        },
                    },
                ],
                [
                    {
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": ["despite", "subject"]},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "pobj",
                        "RIGHT_ATTRS": {"DEP": {"IN": ["pobj", "pcomp"]}},
                    },
                ],
            ],
        )

    def pipe(self, texts: Iterable[str]) -> Iterable[RuleMatchResult]:
        """Yield matches for an iterable of texts."""

        for doc in self.nlp.pipe(texts):
            yield self.extract_from_doc(doc)


def _create_default_language() -> Language:
    """Return a blank English pipeline suitable for matching."""

    return spacy.blank("en")


def create_rule_matcher(nlp: Language | None = None) -> RuleMatcher:
    """Convenience helper mirroring :class:`RuleMatcher` construction."""

    return RuleMatcher(nlp=nlp)


@lru_cache(maxsize=1)
def get_rule_matcher() -> RuleMatcher:
    """Return a lazily-instantiated shared :class:`RuleMatcher`."""

    return create_rule_matcher()
