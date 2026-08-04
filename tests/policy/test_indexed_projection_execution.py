from __future__ import annotations

import hashlib

from src.policy import corpus_compilation as legacy
from src.policy.corpus_compilation import default_compiler_context
from src.policy.indexed_projection_execution import indexed_semantic_annotation_layer
from src.policy.operational_corpus_compilation import compile_document_operational


def _source(text: str) -> dict[str, str]:
    return {
        "document_ref": "document:indexed-projection-test",
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "media_type": "text/plain",
        "canonical_text": text,
        "source_ref": "source:indexed-projection-test",
    }


def test_indexed_projection_strategy_is_installed_with_serial_fallback() -> None:
    assert legacy._semantic_annotation_layer is indexed_semantic_annotation_layer
    assert callable(legacy._serial_semantic_annotation_layer)
    assert (
        legacy._serial_semantic_annotation_layer
        is not indexed_semantic_annotation_layer
    )


def test_indexed_projection_preserves_serial_semantic_artifacts(monkeypatch) -> None:
    text = "Ada must leave the hall. She may return tomorrow."
    source = _source(text)
    context = default_compiler_context()

    indexed = compile_document_operational(source, context)
    monkeypatch.setattr(
        legacy,
        "_semantic_annotation_layer",
        legacy._serial_semantic_annotation_layer,
    )
    serial = compile_document_operational(source, context)

    assert indexed.status == "compiled"
    assert serial.status == "compiled"
    assert (
        indexed.artifacts["semantic_annotation_layer"]
        == serial.artifacts["semantic_annotation_layer"]
    )
    assert (
        indexed.artifacts["relational_bundle"] == serial.artifacts["relational_bundle"]
    )
    assert indexed.artifacts["pnf_graph"] == serial.artifacts["pnf_graph"]
    assert (
        indexed.artifacts["resolution_demands"]
        == serial.artifacts["resolution_demands"]
    )
