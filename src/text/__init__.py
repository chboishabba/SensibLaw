"""Text processing utilities.

The package is on the canonical compiler import path.  Importing its optional
spaCy-backed compatibility types at package import time made every document
compiler process pay the full spaCy import footprint before it had admitted a
single parser fibre.  Keep those historical re-exports available, but resolve
them only for callers that actually request them.
"""

from importlib import import_module
from typing import Any
from .shared_text_normalization import (
    split_semicolon_clauses,
    split_text_clauses,
    split_text_segments,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)
from .phrase_cues import extract_text_cues
from .residual_lattice import (
    CandidateResidual,
    PredicateIndex,
    PredicatePNF,
    PredicateAtom,
    QualifierState,
    Residual,
    ResidualLevel,
    RoleState,
    TypedArg,
    WrapperState,
    build_predicate_index,
    build_predicate_ref_map,
    collect_candidate_predicate_refs,
    collect_candidate_residuals,
    coerce_predicate_atom,
    comparable,
    compute_indexed_residual,
    compute_residual,
    join_role_states,
    join_residual,
    join_typed_args,
    meet_atom,
)
from .dashi_carrier_motif_spine import (
    CARRIER_MOTIF_MODIFIER_KEY,
    CARRIER_MOTIF_SCHEMA,
    CarrierMotif,
    CarrierMotifAnnotation,
    CarrierRole,
    ProjectionTarget,
    attach_carrier_motif_modifier,
    coerce_carrier_motif_annotation,
)
from .utterance_latent_fibres import (
    LATENT_FIBRE_INDEX_SCHEMA,
    LatentFibreCandidate,
    UtteranceLatentIndex,
    enrich_utterance_atoms,
    load_latent_index,
    meet_atom_with_latent_fibres,
    parse_latent_index,
)

__all__ = [
    "FastTextLanguageDetector",
    "LanguageDetector",
    "SimpleDoc",
    "SpacyNLP",
    "TikaLanguageDetector",
    "split_semicolon_clauses",
    "split_text_clauses",
    "split_text_segments",
    "strip_enumeration_prefix",
    "tokenize_canonical_text",
    "extract_text_cues",
    "PredicatePNF",
    "PredicateAtom",
    "PredicateIndex",
    "CandidateResidual",
    "QualifierState",
    "Residual",
    "ResidualLevel",
    "RoleState",
    "TypedArg",
    "WrapperState",
    "build_predicate_index",
    "build_predicate_ref_map",
    "collect_candidate_predicate_refs",
    "collect_candidate_residuals",
    "coerce_predicate_atom",
    "comparable",
    "compute_indexed_residual",
    "compute_residual",
    "join_role_states",
    "join_residual",
    "join_typed_args",
    "meet_atom",
    "CARRIER_MOTIF_MODIFIER_KEY",
    "CARRIER_MOTIF_SCHEMA",
    "CarrierMotif",
    "CarrierMotifAnnotation",
    "CarrierRole",
    "ProjectionTarget",
    "attach_carrier_motif_modifier",
    "coerce_carrier_motif_annotation",
    "LATENT_FIBRE_INDEX_SCHEMA",
    "LatentFibreCandidate",
    "UtteranceLatentIndex",
    "enrich_utterance_atoms",
    "load_latent_index",
    "meet_atom_with_latent_fibres",
    "parse_latent_index",
]


_NLP_COMPAT_EXPORTS = frozenset(
    {
        "FastTextLanguageDetector",
        "LanguageDetector",
        "SimpleDoc",
        "SpacyNLP",
        "TikaLanguageDetector",
    }
)


def __getattr__(name: str) -> Any:
    """Lazily retain optional NLP compatibility re-exports."""

    if name not in _NLP_COMPAT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.nlp"), name)
    globals()[name] = value
    return value
