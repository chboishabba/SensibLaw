"""Generic language annotations and grammar reductions."""

from .annotations import (
    AnnotationLayer,
    RelationAnnotation,
    SpanAnnotation,
    TokenAnnotation,
)
from .grammars import ReductionGrammar, ReductionResult, apply_reduction_grammar
from .graph import AnnotationGraph
from .operator_composition import (
    OPERATOR_COMPOSITION_CONTRACT,
    compose_operator_factors,
)
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
    "OPERATOR_COMPOSITION_CONTRACT",
    "SemanticReductionDeclaration",
    "SemanticReductionOutput",
    "compose_operator_factors",
    "diagnose_untyped_mentions",
    "derive_relational_type_hypotheses",
    "SpanAnnotation",
    "TokenAnnotation",
    "apply_reduction_grammar",
    "default_semantic_reduction_declarations",
    "reduce_relational_bundle",
    "summarize_untyped_diagnostics",
]
