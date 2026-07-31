"""Adapters and utilities for third-party NLP toolkits.

The parser adapter is resolved lazily so parser-agnostic semantic workers do
not load the parser runtime merely by importing this package.
"""

from importlib import import_module
from typing import Any

from .event_classifier import EventActionMatch, EventClassifier
from .epistemic_classifier import (
    ClassificationResult,
    EpistemicClassifier,
    PredicateType,
)
from .ontology_mapping import canonical_action_morphology, unknown_action_morphology
from .synset_mapper import DeterministicSynsetActionMapper, SynsetActionMatch

__all__ = [
    "EventActionMatch",
    "EventClassifier",
    "ClassificationResult",
    "EpistemicClassifier",
    "PredicateType",
    "DeterministicSynsetActionMapper",
    "SynsetActionMatch",
    "canonical_action_morphology",
    "unknown_action_morphology",
]


def __getattr__(name: str) -> Any:
    """Resolve the optional parser export only when explicitly requested."""

    if name != "parse":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.spacy_adapter"), name)
    globals()[name] = value
    return value


__all__.append("parse")
