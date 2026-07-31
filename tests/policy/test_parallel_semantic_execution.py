from __future__ import annotations

from src.language.annotations import AnnotationLayer, SpanAnnotation
from src.policy import corpus_compilation as legacy
from src.policy import operational_corpus_compilation as operational
from src.policy.parallel_semantic_execution import (
    indexed_atom_mention_refs,
    indexed_parser_observation_refs_by_mention,
)


def _semantic_layer() -> AnnotationLayer:
    return AnnotationLayer(
        layer_ref="layer:semantic-test",
        tokenizer_ref="parser:test",
        text_sha256="text-sha",
        span_annotations=(
            SpanAnnotation("parser:0", 0, 1, "parser_token", {}),
            SpanAnnotation("parser:1", 1, 2, "parser_token", {}),
            SpanAnnotation("parser:2", 2, 3, "parser_token", {}),
            SpanAnnotation("parser:3", 3, 4, "parser_token", {}),
            SpanAnnotation("atom-span:1", 0, 2, "semantic_atom", {}),
            SpanAnnotation("atom-span:2", 2, 4, "semantic_atom", {}),
        ),
    )


def _mentions() -> tuple[dict[str, object], ...]:
    return (
        {"mention_ref": "mention:1", "start_token": 0, "end_token": 1},
        {"mention_ref": "mention:2", "start_token": 1, "end_token": 3},
        {"mention_ref": "mention:3", "start_token": 3, "end_token": 4},
    )


def test_parallel_semantic_strategy_is_installed_after_bounded_closure() -> None:
    assert getattr(operational, "_parallel_semantic_execution_installed", False)
    assert hasattr(operational, "_bounded_streaming_semantic_build")
    assert hasattr(operational, "_canonical_compile_document_operational")
    assert hasattr(legacy, "_serial_atom_mention_refs")
    assert hasattr(legacy, "_serial_parser_observation_refs_by_mention")


def test_indexed_atom_mention_matching_preserves_canonical_output() -> None:
    layer = _semantic_layer()
    atom_span_refs = {"atom:1": "atom-span:1", "atom:2": "atom-span:2"}
    mentions = _mentions()

    serial = legacy._serial_atom_mention_refs(
        semantic_layer=layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )
    indexed = indexed_atom_mention_refs(
        semantic_layer=layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )

    assert indexed == serial == {
        "atom:1": ("mention:1", "mention:2"),
        "atom:2": ("mention:2", "mention:3"),
    }


def test_indexed_parser_observation_matching_preserves_canonical_output() -> None:
    layer = _semantic_layer()
    mentions = _mentions()

    serial = legacy._serial_parser_observation_refs_by_mention(
        semantic_layer=layer,
        mentions=mentions,
    )
    indexed = indexed_parser_observation_refs_by_mention(
        semantic_layer=layer,
        mentions=mentions,
    )

    assert indexed == serial == {
        "mention:1": ("parser:0",),
        "mention:2": ("parser:1", "parser:2"),
        "mention:3": ("parser:3",),
    }
