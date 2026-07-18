"""Generic language annotations and grammar reductions."""

from .annotations import AnnotationLayer, RelationAnnotation, SpanAnnotation, TokenAnnotation
from .grammars import ReductionGrammar, ReductionResult, apply_reduction_grammar
from .graph import AnnotationGraph

__all__ = [
    "AnnotationGraph",
    "AnnotationLayer",
    "ReductionGrammar",
    "ReductionResult",
    "RelationAnnotation",
    "SpanAnnotation",
    "TokenAnnotation",
    "apply_reduction_grammar",
]
