from __future__ import annotations

import pytest

from src.pnf.mabo_cross_source_alignment_specimen import (
    NTA_PREAMBLE_MABO_TEXT,
    build_cross_source_mabo_alignment_specimen,
)
from src.pnf.mabo_legal_proof_graph_specimen import MABO_FIXTURE_TEXT


def test_cross_source_alignment_recovers_common_coordinates_without_surface_identity() -> None:
    specimen = build_cross_source_mabo_alignment_specimen(
        mabo_summary_text=MABO_FIXTURE_TEXT,
        nta_preamble_text=NTA_PREAMBLE_MABO_TEXT,
    )

    assert specimen.common_ground_candidate_coordinates == 2
    assert specimen.controversy_residual_count == 0
    assert specimen.exact_surface_equality_required_for_alignment is False
    assert [edge.alignment_kind for edge in specimen.alignments] == [
        "same_native_title_recognition_coordinate",
        "same_terra_nullius_rejection_coordinate",
    ]


def test_cross_source_alignment_preserves_both_provenances_and_does_not_make_fact() -> None:
    specimen = build_cross_source_mabo_alignment_specimen(
        mabo_summary_text=MABO_FIXTURE_TEXT,
        nta_preamble_text=NTA_PREAMBLE_MABO_TEXT,
    )

    assert specimen.source_provenance_preserved is True
    assert specimen.alignment_merges_sources is False
    assert specimen.alignment_implies_world_truth is False
    assert all(edge.merged_as_single_fact is False for edge in specimen.alignments)
    assert specimen.left_source_path != specimen.right_source_path


def test_cross_source_alignment_retains_source_specific_predicates() -> None:
    specimen = build_cross_source_mabo_alignment_specimen(
        mabo_summary_text=MABO_FIXTURE_TEXT,
        nta_preamble_text=NTA_PREAMBLE_MABO_TEXT,
    )

    assert specimen.left_nodes[0].predicate == "recognise_native_title"
    assert specimen.right_nodes[1].predicate == "hold_common_law_recognises_native_title"
    assert specimen.left_nodes[0].source_span.text != specimen.right_nodes[1].source_span.text


def test_cross_source_alignment_rejects_unbounded_right_source() -> None:
    with pytest.raises(ValueError, match="exact bounded Native Title preamble"):
        build_cross_source_mabo_alignment_specimen(
            mabo_summary_text=MABO_FIXTURE_TEXT,
            nta_preamble_text=NTA_PREAMBLE_MABO_TEXT + " unrelated material",
        )
