from __future__ import annotations

import pytest

from src.language import AnnotationGraph
from src.pnf.document_fibres import DocumentFibre
from src.pnf.document_projection_manifests import (
    build_logical_layer_manifest,
    build_partition_manifest,
    document_projection_join,
)


def _fibre(sequence_no: int, start: int, end: int) -> DocumentFibre:
    return DocumentFibre(
        document_ref="document:manifest",
        fibre_ref=f"document-fibre:{sequence_no}",
        sequence_no=sequence_no,
        owner_start=start,
        owner_end=end,
        context_start=max(0, start - 2),
        context_end=end + 2,
        text_sha256="a" * 64,
    )


def test_document_projection_manifest_is_partition_independent() -> None:
    layer = {
        "token_annotations": [{"token_index": 0, "annotation_type": "token", "value": "Ada"}],
        "span_annotations": [{"span_ref": "span:ada", "start_token": 0, "end_token": 1, "annotation_type": "mention", "value": {}}],
    }
    logical = build_logical_layer_manifest(
        document_ref="document:manifest", source_sha256="b" * 64, layer=layer
    )
    parts = [
        build_partition_manifest(
            fibre=_fibre(0, 0, 5), carrier_ref="carrier:1", source_sha256="b" * 64,
            build_key_sha256="c" * 64, parser_contract_ref="parser:1", reducer_contract_ref="reducer:1",
        ),
        build_partition_manifest(
            fibre=_fibre(1, 5, 10), carrier_ref="carrier:1", source_sha256="b" * 64,
            build_key_sha256="c" * 64, parser_contract_ref="parser:1", reducer_contract_ref="reducer:1",
        ),
    ]
    manifest = document_projection_join(partitions=parts, logical_layers=(logical,), canonical_length=10)

    assert manifest.graph_ref == AnnotationGraph.from_layer_refs((logical.layer_ref,)).graph_ref
    assert manifest.coverage_proof["exactly_once"] is True
    assert manifest.partition_refs == tuple(part.partition_ref for part in parts)


def test_document_projection_join_rejects_noncontiguous_ownership() -> None:
    logical = build_logical_layer_manifest(
        document_ref="document:manifest", source_sha256="b" * 64, layer={}
    )
    parts = [
        build_partition_manifest(
            fibre=_fibre(0, 0, 4), carrier_ref="carrier:1", source_sha256="b" * 64,
            build_key_sha256="c" * 64, parser_contract_ref="parser:1", reducer_contract_ref="reducer:1",
        ),
        build_partition_manifest(
            fibre=_fibre(1, 5, 10), carrier_ref="carrier:1", source_sha256="b" * 64,
            build_key_sha256="c" * 64, parser_contract_ref="parser:1", reducer_contract_ref="reducer:1",
        ),
    ]
    with pytest.raises(ValueError, match="contiguous"):
        document_projection_join(partitions=parts, logical_layers=(logical,), canonical_length=10)
