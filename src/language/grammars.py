"""Declarative grammar values over the shared annotation graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from src.policy.algebra import Factor, FactorConstraint, TypedAlternative
from src.policy.carriers.canonical import canonical_mapping, canonical_refs, require_text

from .graph import AnnotationGraph


@dataclass(frozen=True)
class ReductionGrammar:
    grammar_ref: str
    required_span_types: tuple[str, ...]
    required_relation_types: tuple[str, ...] = ()
    output_factor_type: str = "semantic.unknown"
    output_type_ref: str = "semantic.unknown"
    factor_bindings: Mapping[str, Any] = field(default_factory=dict)
    residuals_on_failure: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "grammar_ref": require_text(self.grammar_ref, "grammar_ref"),
            "required_span_types": list(canonical_refs(self.required_span_types)),
            "required_relation_types": list(canonical_refs(self.required_relation_types)),
            "output_factor_type": require_text(
                self.output_factor_type, "output_factor_type"
            ),
            "output_type_ref": require_text(self.output_type_ref, "output_type_ref"),
            "factor_bindings": canonical_mapping(self.factor_bindings),
            "residuals_on_failure": list(canonical_refs(self.residuals_on_failure)),
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
            "authority": "grammar_only",
        }


@dataclass(frozen=True)
class ReductionResult:
    grammar_ref: str
    matched: bool
    factor: Factor[Any]
    annotation_refs: tuple[str, ...] = ()


def apply_reduction_grammar(
    *, graph: AnnotationGraph, grammar: ReductionGrammar, factor_ref: str
) -> ReductionResult:
    """Apply structural requirements without selecting among semantic branches.

    Every matching span becomes a separate typed alternative. A grammar match
    therefore expands a factor; it never ranks alternatives or resolves identity.
    """

    required_spans = set(grammar.required_span_types)
    required_relations = set(grammar.required_relation_types)
    spans = tuple(
        row for row in graph.span_annotations() if row.annotation_type in required_spans
    )
    relation_types = {row.relation_type for row in graph.relation_annotations()}
    matched = bool(spans) and required_relations.issubset(relation_types)
    if not matched:
        return ReductionResult(
            grammar_ref=grammar.grammar_ref,
            matched=False,
            factor=Factor(
                factor_ref=factor_ref,
                factor_type=grammar.output_factor_type,
                residuals=grammar.residuals_on_failure,
                closure_state="open",
                metadata={"grammar_ref": grammar.grammar_ref},
            ),
        )
    alternatives = tuple(
        TypedAlternative(
            alternative_ref=f"{factor_ref}:{row.span_ref}:{grammar.output_type_ref}",
            value={"span_ref": row.span_ref, "annotation_value": row.value},
            type_ref=grammar.output_type_ref,
            derivation_refs=(grammar.grammar_ref, row.span_ref),
            authority_state="candidate_only",
        )
        for row in spans
    )
    constraint = FactorConstraint(
        constraint_ref=f"constraint:{factor_ref}:{grammar.grammar_ref}",
        constraint_type="grammar_match",
        payload={"factor_bindings": dict(grammar.factor_bindings)},
        provenance_refs=grammar.provenance_refs,
    )
    return ReductionResult(
        grammar_ref=grammar.grammar_ref,
        matched=True,
        factor=Factor(
            factor_ref=factor_ref,
            factor_type=grammar.output_factor_type,
            alternatives=alternatives,
            constraints=(constraint,),
            closure_state="locally_closed",
            metadata={"grammar_ref": grammar.grammar_ref},
        ),
        annotation_refs=tuple(row.span_ref for row in spans),
    )
