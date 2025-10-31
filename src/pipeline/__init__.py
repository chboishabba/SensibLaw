"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

from src.concepts.matcher import MATCHER

from src.tools.glossary import rewrite_text

from src.tools.harm_index import compute_harm_index as harm_index

from .ner import (
    analyze_references,
    get_ner_pipeline,
    REFERENCE_SPAN_KEY,
    REFERENCE_LABEL,
)



def normalise(text: str) -> str:
    """Normalise text for downstream processing.

    Institutional terminology is first rewritten using the glossary's
    movement equivalents to ensure consistent vocabulary. The rewritten text
    is then lowercased. Future implementations may add tokenisation or
    lemmatisation.
    """
    rewritten = rewrite_text(text)
    return rewritten.lower()


def match_concepts(text: str) -> List[str]:
    """Match concepts within the text.

    Uses an Aho-Corasick automaton to locate concept triggers and returns
    the matched concept IDs.
    """
    return [hit.concept_id for hit in MATCHER.match(text)]


def build_cloud(concepts: List[str]) -> Dict[str, int]:
    """Build a frequency cloud of concepts.

    The current version counts the occurrences of each concept. This will
    eventually be replaced with richer semantic representations.
    """
    return dict(Counter(concepts))


__all__ = [
    "normalise",
    "match_concepts",
    "build_cloud",
    "harm_index",
    "analyze_references",
    "get_ner_pipeline",
    "REFERENCE_SPAN_KEY",
    "REFERENCE_LABEL",
]
