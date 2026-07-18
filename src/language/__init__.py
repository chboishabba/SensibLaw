"""Generic language annotations and grammar reductions."""

from .annotations import (
    AnnotationLayer,
    RelationAnnotation,
    SpanAnnotation,
    TokenAnnotation,
)
from .grammars import ReductionGrammar, ReductionResult, apply_reduction_grammar
from .graph import AnnotationGraph
from .semantic_reductions import (
    LocalTypeProjection,
    SemanticReductionDeclaration,
    SemanticReductionOutput,
    diagnose_untyped_mentions,
    derive_relational_type_hypotheses,
    default_semantic_reduction_declarations,
    reduce_relational_bundle,
    summarize_untyped_diagnostics,
)

__all__ = [
    "AnnotationGraph",
    "AnnotationLayer",
    "ReductionGrammar",
    "ReductionResult",
    "RelationAnnotation",
    "LocalTypeProjection",
    "SemanticReductionDeclaration",
    "SemanticReductionOutput",
    "diagnose_untyped_mentions",
    "derive_relational_type_hypotheses",
    "SpanAnnotation",
    "TokenAnnotation",
    "apply_reduction_grammar",
    "default_semantic_reduction_declarations",
    "reduce_relational_bundle",
    "summarize_untyped_diagnostics",
]
