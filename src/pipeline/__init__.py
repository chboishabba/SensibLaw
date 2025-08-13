"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from typing import List, Dict

from ..concepts.matcher import MATCHER


def normalise(text: str) -> str:
    """Basic text normalisation.

    Currently this is a placeholder that lowercases the text. Future
    implementations may perform tokenisation, lemmatisation and more.
    """
    return text.lower()


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


__all__ = ["normalise", "match_concepts", "build_cloud"]
