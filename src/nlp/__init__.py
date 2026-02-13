"""Adapters and utilities for third-party NLP toolkits."""

from .epistemic_classifier import ClassificationResult, EpistemicClassifier, PredicateType
from .ontology_mapping import canonical_action_morphology, unknown_action_morphology
from .spacy_adapter import parse

__all__ = [
    "ClassificationResult",
    "EpistemicClassifier",
    "PredicateType",
    "canonical_action_morphology",
    "parse",
    "unknown_action_morphology",
]
