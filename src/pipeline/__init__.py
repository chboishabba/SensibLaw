"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from typing import List, Dict

from tools.harm_index import compute_harm_index as harm_index


def normalise(text: str) -> str:
    """Basic text normalisation.

    Currently this is a placeholder that lowercases the text. Future
    implementations may perform tokenisation, lemmatisation and more.
    """
    return text.lower()


def match_concepts(text: str) -> List[str]:
    """Match concepts within the text.

    This stub implementation simply splits the text into whitespace
    separated tokens.
    """
    return text.split()


def build_cloud(concepts: List[str]) -> Dict[str, int]:
    """Build a frequency cloud of concepts.

    The current version counts the occurrences of each concept. This will
    eventually be replaced with richer semantic representations.
    """
    return dict(Counter(concepts))


__all__ = ["normalise", "match_concepts", "build_cloud", "harm_index"]
