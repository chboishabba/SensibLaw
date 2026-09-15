"""Mabo cross-pollination into the existing fact-intake residual probe.

This module does not introduce another comparison calculus.  It converts the
human-reviewed Mabo summary / Native Title preamble alignment into the existing
``fact_extraction_probe_v0_1`` input shape so PredicatePNF structural fibres and
residual comparison remain the one comparison authority.
"""

from __future__ import annotations

from typing import Any

from src.fact_intake.fact_extraction_probe import build_fact_extraction_probe
from src.pnf.mabo_cross_source_alignment_specimen import (
    NTA_PREAMBLE_MABO_TEXT,
)
from src.pnf.mabo_legal_proof_graph_specimen import MABO_FIXTURE_TEXT


def _receipts(prefix: str) -> dict[str, str]:
    return {
        "source_receipt_id": f"src:{prefix}",
        "excerpt_receipt_id": f"excerpt:{prefix}",
        "statement_receipt_id": f"statement:{prefix}",
        "observation_receipt_id": f"obs:{prefix}",
    }


def _atom(
    *,
    atom_id: str,
    predicate: str,
    structural_signature: str,
    roles: dict[str, dict[str, str]],
    provenance: str,
    wrapper_status: str,
) -> dict[str, Any]:
    return {
        "atom_id": atom_id,
        "predicate": predicate,
        "structural_signature": structural_signature,
        "roles": roles,
        "qualifiers": {"polarity": "positive", "certainty": "asserted"},
        "wrapper": {"status": wrapper_status, "evidence_only": True},
        "provenance": [provenance],
    }


def build_mabo_cross_source_fact_probe() -> dict[str, Any]:
    """Run the existing residual probe over two reviewed Mabo coordinates."""

    recognition_roles = {
        "authority": {"value": "High Court of Australia", "entity_type": "court"},
        "subject": {"value": "native title", "entity_type": "legal_interest"},
        "jurisdiction": {"value": "Australia", "entity_type": "jurisdiction"},
    }
    rejection_roles = {
        "authority": {"value": "High Court of Australia", "entity_type": "court"},
        "doctrine": {"value": "terra nullius", "entity_type": "legal_doctrine"},
        "jurisdiction": {"value": "Australia", "entity_type": "jurisdiction"},
    }

    cases = (
        {
            "case_id": "mabo_native_title_cross_source",
            "lane": "legal_common_ground_candidate",
            "source_span": MABO_FIXTURE_TEXT,
            "receipts": _receipts("mabo-native-title"),
            "fact_candidate": {
                "fact_id": "fact:mabo-native-title",
                "label": "High Court recognised native title in Australia",
                "predicate_atom": _atom(
                    atom_id="query:mabo-native-title",
                    predicate="legal_holding",
                    structural_signature="legal_holding(authority,subject,jurisdiction)",
                    roles=recognition_roles,
                    provenance="statement:mabo-summary:native-title",
                    wrapper_status="repository_case_summary",
                ),
            },
            "evidence_atoms": (
                _atom(
                    atom_id="evidence:nta-preamble-native-title",
                    predicate="legal_holding",
                    structural_signature="legal_holding(authority,subject,jurisdiction)",
                    roles=recognition_roles,
                    provenance="obs:nta-preamble:native-title",
                    wrapper_status="statutory_preamble_characterisation",
                ),
            ),
            "promotion_gate": {"promote": False},
        },
        {
            "case_id": "mabo_terra_nullius_cross_source",
            "lane": "legal_common_ground_candidate",
            "source_span": MABO_FIXTURE_TEXT,
            "receipts": _receipts("mabo-terra-nullius"),
            "fact_candidate": {
                "fact_id": "fact:mabo-terra-nullius",
                "label": "High Court rejected terra nullius",
                "predicate_atom": _atom(
                    atom_id="query:mabo-terra-nullius",
                    predicate="legal_rejection",
                    structural_signature="legal_rejection(authority,doctrine,jurisdiction)",
                    roles=rejection_roles,
                    provenance="statement:mabo-summary:terra-nullius",
                    wrapper_status="repository_case_summary",
                ),
            },
            "evidence_atoms": (
                _atom(
                    atom_id="evidence:nta-preamble-terra-nullius",
                    predicate="legal_rejection",
                    structural_signature="legal_rejection(authority,doctrine,jurisdiction)",
                    roles=rejection_roles,
                    provenance="obs:nta-preamble:terra-nullius",
                    wrapper_status="statutory_preamble_characterisation",
                ),
            ),
            "promotion_gate": {"promote": False},
        },
    )

    probe = build_fact_extraction_probe(
        fact_cases=cases,
        source={
            "kind": "bounded_cross_source_legal_fixture",
            "left_source_text": MABO_FIXTURE_TEXT,
            "right_source_text": NTA_PREAMBLE_MABO_TEXT,
            "live_query": False,
            "receipt_policy": "no_fabricated_PNFEmissionReceipt",
        },
    )
    probe["mabo_alignment_boundary"] = {
        "surface_texts_differ": True,
        "typed_coordinates_human_reviewed": True,
        "shared_coordinate_is_world_truth": False,
        "shared_coordinate_is_party_admission": False,
        "promotion_requested": False,
        "source_provenance_preserved": True,
    }
    return probe


__all__ = ["build_mabo_cross_source_fact_probe"]
