"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from typing import List, Dict

from tools.glossary import rewrite_text


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


__all__ = ["normalise", "match_concepts", "build_cloud"]
