from __future__ import annotations

from dataclasses import replace

import pytest

from src.pnf.evidential_pnf_receipt import EvidentialPNFBridgeReceipt
from src.pnf.mabo_legal_proof_graph_specimen import (
    MABO_FIXTURE_SHA256,
    MABO_FIXTURE_TEXT,
    build_mabo_legal_proof_graph_specimen,
)


def _bridge() -> EvidentialPNFBridgeReceipt:
    return EvidentialPNFBridgeReceipt(
        schema_version="sl.evidential_pnf_bridge.v0_1",
        run_ref="run:mabo-fixture",
        document_ref="document:mabo-fixture",
        canonical_text_sha256=MABO_FIXTURE_SHA256,
        parser_contract_ref="streaming-spacy:test",
        numeric_pnf_compiler_contract_ref="numeric-pnf-hyperfabric-compiler:v1",
        graph_ref="numeric-pnf-interface:mabo",
        residual_demand_refs=(),
        representation="numeric_postgresql_hyperfabric",
        world_resolution_deferred=True,
        cross_document_identity_closed=False,
        legacy_document_materialisation=False,
        parser_observation_is_semantic_authority=False,
        semantic_correspondence_required=True,
    )


def test_mabo_fixture_builds_two_source_exact_reviewed_predicates() -> None:
    specimen = build_mabo_legal_proof_graph_specimen(
        bridge_receipt=_bridge(),
        source_text=MABO_FIXTURE_TEXT,
    )

    assert [node.predicate for node in specimen.nodes] == [
        "recognise_native_title",
        "reject_doctrine",
    ]
    assert specimen.nodes[0].source_span.text == (
        "The High Court recognised native title in Australia"
    )
    assert specimen.nodes[1].source_span.text == (
        "rejected the doctrine of terra nullius"
    )
    assert specimen.source_is_repository_fixture_summary is True
    assert specimen.source_is_authoritative_judgment_text is False
    assert specimen.world_truth_claimed is False


def test_single_fixture_graph_does_not_invent_adversarial_residual_or_probe() -> None:
    specimen = build_mabo_legal_proof_graph_specimen(
        bridge_receipt=_bridge(),
        source_text=MABO_FIXTURE_TEXT,
    )

    assert specimen.party_alignment_complete is False
    assert specimen.controversy_residual_compiled is False
    assert specimen.next_evidence_probe_authorised is False


def test_mabo_fixture_rejects_concatenated_or_contaminated_source() -> None:
    contaminated = MABO_FIXTURE_TEXT + " Later unrelated case material."

    with pytest.raises(ValueError, match="exact bounded repository fixture text"):
        build_mabo_legal_proof_graph_specimen(
            bridge_receipt=_bridge(),
            source_text=contaminated,
        )


def test_mabo_fixture_rejects_bridge_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="canonical-text hash"):
        build_mabo_legal_proof_graph_specimen(
            bridge_receipt=replace(_bridge(), canonical_text_sha256="bad"),
            source_text=MABO_FIXTURE_TEXT,
        )


def test_mabo_fixture_rejects_parser_semantic_authority() -> None:
    with pytest.raises(ValueError, match="semantic authority"):
        build_mabo_legal_proof_graph_specimen(
            bridge_receipt=replace(
                _bridge(), parser_observation_is_semantic_authority=True
            ),
            source_text=MABO_FIXTURE_TEXT,
        )


def test_mabo_fixture_requires_reviewed_correspondence_boundary() -> None:
    with pytest.raises(ValueError, match="reviewed correspondence"):
        build_mabo_legal_proof_graph_specimen(
            bridge_receipt=replace(_bridge(), semantic_correspondence_required=False),
            source_text=MABO_FIXTURE_TEXT,
        )
