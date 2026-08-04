from __future__ import annotations

import pytest

from src.language import AnnotationGraph, AnnotationLayer


def _layer(ref: str) -> AnnotationLayer:
    return AnnotationLayer(
        layer_ref=ref,
        tokenizer_ref="tokenizer:test",
        text_sha256="a" * 64,
    )


def test_annotation_graph_identity_uses_ordered_layer_refs() -> None:
    first = _layer("annotation-layer:first")
    second = _layer("annotation-layer:second")

    assert AnnotationGraph.from_layers((first, second)).graph_ref == (
        AnnotationGraph.from_layers((first, second)).graph_ref
    )
    assert AnnotationGraph.from_layers((first, second)).graph_ref != (
        AnnotationGraph.from_layers((second, first)).graph_ref
    )


def test_annotation_graph_identity_never_serializes_layer_payload(monkeypatch) -> None:
    first = _layer("annotation-layer:first")
    second = _layer("annotation-layer:second")

    def fail_to_dict(self):
        raise AssertionError("graph identity must use layer_ref, not layer payload")

    monkeypatch.setattr(AnnotationLayer, "to_dict", fail_to_dict)
    graph = AnnotationGraph.from_layers((first, second))

    assert graph.layers == (first, second)


def test_annotation_graph_rejects_empty_or_duplicate_layer_refs() -> None:
    layer = _layer("annotation-layer:one")

    with pytest.raises(ValueError, match="at least one"):
        AnnotationGraph.from_layers(())
    with pytest.raises(ValueError, match="distinct"):
        AnnotationGraph.from_layers((layer, layer))
