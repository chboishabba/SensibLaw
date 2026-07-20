from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from src.ingestion.corpus_source_projection import project_source_families
from src.pnf.external_reconciliation import build_reconciliation_checkpoint
from src.runtime.tranche_pipeline import (
    PhaseReceipt,
    TranchePhase,
    checkpoint_payload,
    profile_for_tranche,
    validate_phase_receipts,
)


def _candidate(candidate_ref: str, external_id: str, label: str) -> dict[str, object]:
    return {
        "candidate_ref": candidate_ref,
        "provider_ref": "wikidata",
        "external_id": external_id,
        "label": label,
        "candidate_kind": "entity",
        "aliases": [],
        "type_refs": ["Q6256"],
        "snapshot_ref": "snapshot:q30",
        "evidence_refs": ["snapshot:q30"],
        "authority": "candidate_only",
    }


def _result(demand_ref: str, subject_ref: str, surface: str) -> dict[str, object]:
    candidate = _candidate("external-candidate:q30", "Q30", "United States of America")
    return {
        "demand": {
            "demand_ref": demand_ref,
            "subject_ref": subject_ref,
            "surface": surface,
            "demand_kind": "entity_identity",
            "local_type_refs": ["semantic.geopolitical_entity"],
            "context_terms": ["country"],
        },
        "candidate_sets": [
            {
                "candidate_set_ref": f"external-candidate-set:{demand_ref}",
                "demand_ref": demand_ref,
                "subject_ref": subject_ref,
                "provider_ref": "wikidata",
                "candidates": [candidate],
                "assessments": [
                    {
                        "candidate_ref": "external-candidate:q30",
                        "compatibility_state": "compatible_candidate",
                        "surface_score": 1.0,
                        "type_score": 0.5,
                        "context_score": 0.5,
                        "reasons": ["exact_label_or_alias", "type_evidence_incomplete"],
                    }
                ],
                "residuals": [
                    "external_candidates_available",
                    "external_identity_unresolved",
                ],
                "snapshot_refs": ["snapshot:q30"],
                "authority": "candidate_only",
                "identity_closed": False,
            }
        ],
        "pressure_receipts": [
            {
                "pressure_ref": f"pressure:{demand_ref}",
                "demand_ref": demand_ref,
                "before": {"lookup_absence": 1.0},
                "after": {"lookup_absence": 0.0, "candidate_ambiguity": 0.0},
                "identity_closed": False,
            }
        ],
    }


def test_shared_qid_emits_overlap_and_review_not_identity_closure() -> None:
    checkpoint = build_reconciliation_checkpoint(
        {
            "results": [
                _result("demand:us", "factor:us", "U.S."),
                _result("demand:america", "factor:america", "America"),
            ]
        }
    )

    assert checkpoint["summary"] == {
        "result_count": 2,
        "typed_meet_count": 2,
        "candidate_overlap_signal_count": 1,
        "review_packet_count": 2,
        "identity_closure_count": 0,
        "world_entity_promotion_count": 0,
    }
    signal = checkpoint["candidate_overlap_signals"][0]
    assert signal["external_id"] == "Q30"
    assert signal["surfaces"] == ["America", "U.S."]
    assert signal["same_entity_closed"] is False
    assert "metonymy_or_polysemy_unresolved" in signal["residuals"]
    assert all(packet["identity_closed"] is False for packet in checkpoint["review_packets"])
    assert all(
        "promote_equivalence" in packet["available_actions"]
        for packet in checkpoint["review_packets"]
    )


def test_source_projection_preserves_raw_and_canonical_coordinates(tmp_path: Path) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    html = source / "page.html"
    html.write_text(
        "<html><body><h1>United States</h1><script>bad()</script><p>America.</p></body></html>",
        encoding="utf-8",
    )
    epub = source / "book.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("chapter.xhtml", "<html><body><p>George W. Bush spoke.</p></body></html>")

    manifest = project_source_families([source], output_dir=tmp_path / "projection")
    payload = manifest.to_dict()

    assert payload["summary"]["document_count"] == 2
    assert payload["summary"]["failure_count"] == 0
    assert {row["media_type"] for row in payload["documents"]} == {
        "text/html",
        "application/epub+zip",
    }
    for row in payload["documents"]:
        assert row["raw_sha256"] != row["canonical_sha256"]
        assert row["anchor_state"] == "derived_text_with_source_anchor"
        raw_path = tmp_path / "projection" / row["raw_path"]
        canonical_path = tmp_path / "projection" / row["canonical_path"]
        assert raw_path.exists()
        assert canonical_path.exists()
        assert "<html" not in canonical_path.read_text(encoding="utf-8").lower()


def test_phase_contract_rejects_network_before_local_world() -> None:
    receipts = [
        PhaseReceipt(TranchePhase.SOURCE_INVENTORY, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.SOURCE_ACQUISITION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.CANONICAL_PROJECTION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.LOCAL_PNF_COMPILATION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.EXTERNAL_DEMAND_PLANNING, "completed", (), (), {}),
    ]
    with pytest.raises(ValueError, match="LOCAL_WORLD_PROJECTION"):
        validate_phase_receipts(receipts)


def test_legal_acquisition_requires_pnf_legal_demand_phase() -> None:
    receipts = [
        PhaseReceipt(TranchePhase.SOURCE_INVENTORY, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.SOURCE_ACQUISITION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.CANONICAL_PROJECTION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.LOCAL_PNF_COMPILATION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.LOCAL_WORLD_PROJECTION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.EXTERNAL_DEMAND_PLANNING, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.EXTERNAL_ACQUISITION, "completed", (), (), {}),
        PhaseReceipt(TranchePhase.LEGAL_ADJUNCT_ACQUISITION, "completed", (), (), {}),
    ]

    with pytest.raises(ValueError, match="LEGAL_ADJUNCT_DEMAND_PLANNING"):
        validate_phase_receipts(receipts)


def test_checkpoint_preserves_authority_boundaries() -> None:
    profile = profile_for_tranche("GWB")
    receipts = [
        PhaseReceipt(phase, "completed", (), (), {}) for phase in TranchePhase
    ]
    checkpoint = checkpoint_payload(profile=profile, receipts=receipts, artifacts={})

    assert checkpoint["authority_boundaries"] == {
        "one_media_adapter": True,
        "one_canonical_text_substrate": True,
        "one_parser_spine": True,
        "pnf_is_semantic_center": True,
        "legal_ir_is_pnf_projection": True,
        "source_mentions_preserved": True,
        "external_candidates_are_not_identity": True,
        "legal_relevance_is_not_applicability": True,
        "applicability_is_not_violation": True,
        "local_compilation_network_independent": True,
        "world_entity_promotion_performed": False,
        "review_required_for_identity_or_legal_closure": True,
    }
    json.dumps(checkpoint)
