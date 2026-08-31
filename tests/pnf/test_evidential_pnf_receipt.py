from __future__ import annotations

import pytest

from src.pnf.evidential_pnf_receipt import (
    EVIDENTIAL_PNF_BRIDGE_SCHEMA_VERSION,
    build_evidential_pnf_bridge_receipt,
)


def _artifacts() -> dict[str, object]:
    return {
        "numeric_pnf_authority": {
            "compiler_contract_ref": "numeric-pnf-hyperfabric-compiler:v1",
            "parser_execution_contract_ref": "streaming-spacy:test",
            "run_ref": "run:test",
            "document_ref": "document:test",
            "graph_ref": "numeric-pnf-interface:abc",
            "demand_refs": ("numeric-pnf-demand:1", "numeric-pnf-demand:2"),
            "representation": "numeric_postgresql_hyperfabric",
            "legacy_document_materialisation": False,
            "world_resolution_deferred": True,
        },
        "phase_boundary": {
            "cross_document_identity_closed": False,
        },
    }


def test_bridge_receipt_preserves_non_semantic_boundary() -> None:
    receipt = build_evidential_pnf_bridge_receipt(
        compilation_artifacts=_artifacts(),
        canonical_text_sha256="deadbeef",
    )

    assert receipt.schema_version == EVIDENTIAL_PNF_BRIDGE_SCHEMA_VERSION
    assert receipt.residual_demand_refs == (
        "numeric-pnf-demand:1",
        "numeric-pnf-demand:2",
    )
    assert receipt.world_resolution_deferred is True
    assert receipt.cross_document_identity_closed is False
    assert receipt.parser_observation_is_semantic_authority is False
    assert receipt.semantic_correspondence_required is True


def test_bridge_rejects_world_closed_document_artifact() -> None:
    artifacts = _artifacts()
    authority = dict(artifacts["numeric_pnf_authority"])  # type: ignore[arg-type]
    authority["world_resolution_deferred"] = False
    artifacts["numeric_pnf_authority"] = authority

    with pytest.raises(ValueError, match="world resolution"):
        build_evidential_pnf_bridge_receipt(
            compilation_artifacts=artifacts,
            canonical_text_sha256="deadbeef",
        )


def test_bridge_rejects_cross_document_identity_closure() -> None:
    artifacts = _artifacts()
    phase = dict(artifacts["phase_boundary"])  # type: ignore[arg-type]
    phase["cross_document_identity_closed"] = True
    artifacts["phase_boundary"] = phase

    with pytest.raises(ValueError, match="cross-document identity"):
        build_evidential_pnf_bridge_receipt(
            compilation_artifacts=artifacts,
            canonical_text_sha256="deadbeef",
        )
