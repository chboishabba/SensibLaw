"""Adapters and utilities for third-party NLP toolkits."""

from .event_classifier import EventActionMatch, EventClassifier
from .epistemic_classifier import ClassificationResult, EpistemicClassifier, PredicateType
from .ontology_mapping import canonical_action_morphology, unknown_action_morphology
from .spacy_adapter import parse
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
    "parse",
    "unknown_action_morphology",
]
