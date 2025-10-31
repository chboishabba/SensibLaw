"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from importlib import import_module
from typing import Any, Dict, List

from src.concepts.matcher import MATCHER

from src.tools.glossary import rewrite_text

from src.tools.harm_index import compute_harm_index as harm_index

from .tokens import Token, TokenStream, spacy_adapter



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



def tokenise(normalised_text: str) -> TokenStream:
    """Tokenise ``normalised_text`` using the configured spaCy adapter."""

    return spacy_adapter.parse(normalised_text)


@lru_cache(maxsize=1)
def _logic_tree_module() -> Any:
    for module_name in ("src.logic_tree", "logic_tree"):
        try:
            return import_module(module_name)
        except ImportError:  # pragma: no cover - depends on deployment
            continue
    raise RuntimeError("logic_tree module is not available")


def build_logic_tree(tokens: TokenStream) -> Any:
    """Build a logic tree structure from ``tokens``."""

    module = _logic_tree_module()
    return module.build(tokens)


__all__ = [
    "normalise",
    "match_concepts",
    "build_cloud",
    "tokenise",
    "build_logic_tree",
    "spacy_adapter",
    "Token",
    "TokenStream",
    "harm_index",
]
