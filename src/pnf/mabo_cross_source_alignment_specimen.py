"""Cross-source Mabo alignment specimen for common-ground recovery.

The two sources are deliberately kept distinct:

1. SensibLaw's tiny Mabo corpus summary fixture.
2. The Native Title (New South Wales) Act 1994 preamble as captured in the
   repository's JADE fixture.

Human-reviewed alignment edges say only that two proposition nodes occupy the
same controversy coordinate.  They do not merge provenance, prove the
underlying proposition, or claim that the statutory preamble is authoritative
judgment text.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.pnf.mabo_legal_proof_graph_specimen import (
    MABO_FIXTURE_TEXT,
    ReviewedPredicateNode,
    SourceSpan,
)


NTA_PREAMBLE_MABO_TEXT = (
    "The High Court of Australia, in Mabo and ors v. The State of Queensland "
    "(No. 2)(1992) 175 CLR 1, rejected the doctrine that Australia was terra "
    "nullius (land belonging to no-one) at the time of European settlement and "
    "held that the common law of Australia recognises the native title rights of "
    "the indigenous inhabitants of Australia—"
)
NTA_PREAMBLE_MABO_SHA256 = sha256(NTA_PREAMBLE_MABO_TEXT.encode("utf-8")).hexdigest()
NTA_PREAMBLE_SOURCE_PATH = "Jadepage.raw.copypaste"


@dataclass(frozen=True, slots=True)
class AlignmentEdge:
    left_node_ref: str
    right_node_ref: str
    alignment_kind: str
    alignment_status: str
    merged_as_single_fact: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_node_ref": self.left_node_ref,
            "right_node_ref": self.right_node_ref,
            "alignment_kind": self.alignment_kind,
            "alignment_status": self.alignment_status,
            "merged_as_single_fact": self.merged_as_single_fact,
        }


@dataclass(frozen=True, slots=True)
class CrossSourceMaboAlignmentSpecimen:
    schema_version: str
    left_source_path: str
    right_source_path: str
    left_source_sha256: str
    right_source_sha256: str
    left_nodes: tuple[ReviewedPredicateNode, ...]
    right_nodes: tuple[ReviewedPredicateNode, ...]
    alignments: tuple[AlignmentEdge, ...]
    source_provenance_preserved: bool
    exact_surface_equality_required_for_alignment: bool
    alignment_implies_world_truth: bool
    alignment_merges_sources: bool
    common_ground_candidate_coordinates: int
    controversy_residual_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "left_source_path": self.left_source_path,
            "right_source_path": self.right_source_path,
            "left_source_sha256": self.left_source_sha256,
            "right_source_sha256": self.right_source_sha256,
            "left_nodes": [node.to_dict() for node in self.left_nodes],
            "right_nodes": [node.to_dict() for node in self.right_nodes],
            "alignments": [edge.to_dict() for edge in self.alignments],
            "source_provenance_preserved": self.source_provenance_preserved,
            "exact_surface_equality_required_for_alignment": (
                self.exact_surface_equality_required_for_alignment
            ),
            "alignment_implies_world_truth": self.alignment_implies_world_truth,
            "alignment_merges_sources": self.alignment_merges_sources,
            "common_ground_candidate_coordinates": self.common_ground_candidate_coordinates,
            "controversy_residual_count": self.controversy_residual_count,
        }


def _exact_span(source_text: str, expected: str) -> SourceSpan:
    start = source_text.find(expected)
    if start < 0:
        raise ValueError(f"reviewed clause absent from bounded source: {expected!r}")
    if source_text.find(expected, start + 1) >= 0:
        raise ValueError(f"reviewed clause not unique in bounded source: {expected!r}")
    end = start + len(expected)
    return SourceSpan(start=start, end=end, text=source_text[start:end])


def build_cross_source_mabo_alignment_specimen(
    *,
    mabo_summary_text: str,
    nta_preamble_text: str,
) -> CrossSourceMaboAlignmentSpecimen:
    """Align the two bounded source descriptions without flattening provenance."""

    left_hash = sha256(mabo_summary_text.encode("utf-8")).hexdigest()
    right_hash = sha256(nta_preamble_text.encode("utf-8")).hexdigest()
    if mabo_summary_text != MABO_FIXTURE_TEXT:
        raise ValueError("left source must be the exact bounded Mabo summary fixture")
    if right_hash != NTA_PREAMBLE_MABO_SHA256:
        raise ValueError("right source must be the exact bounded Native Title preamble excerpt")

    left_recognition = ReviewedPredicateNode(
        node_ref="mabo-summary:recognise-native-title",
        predicate="recognise_native_title",
        agent="High Court",
        theme="native title in Australia",
        qualifier="asserted_by_fixture_summary",
        source_span=_exact_span(
            mabo_summary_text,
            "The High Court recognised native title in Australia",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )
    left_rejection = ReviewedPredicateNode(
        node_ref="mabo-summary:reject-terra-nullius",
        predicate="reject_doctrine",
        agent="High Court",
        theme="doctrine of terra nullius",
        qualifier="asserted_by_fixture_summary",
        source_span=_exact_span(
            mabo_summary_text,
            "rejected the doctrine of terra nullius",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )

    right_rejection = ReviewedPredicateNode(
        node_ref="nta-preamble:reject-terra-nullius",
        predicate="reject_terra_nullius",
        agent="High Court of Australia",
        theme="Australia was terra nullius at European settlement",
        qualifier="asserted_by_statutory_preamble",
        source_span=_exact_span(
            nta_preamble_text,
            "rejected the doctrine that Australia was terra nullius "
            "(land belonging to no-one) at the time of European settlement",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )
    right_recognition = ReviewedPredicateNode(
        node_ref="nta-preamble:common-law-recognises-native-title",
        predicate="hold_common_law_recognises_native_title",
        agent="High Court of Australia",
        theme="native title rights of the indigenous inhabitants of Australia",
        qualifier="asserted_by_statutory_preamble",
        source_span=_exact_span(
            nta_preamble_text,
            "held that the common law of Australia recognises the native title "
            "rights of the indigenous inhabitants of Australia",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )

    alignments = (
        AlignmentEdge(
            left_node_ref=left_recognition.node_ref,
            right_node_ref=right_recognition.node_ref,
            alignment_kind="same_native_title_recognition_coordinate",
            alignment_status="human_reviewed_common_ground_candidate",
            merged_as_single_fact=False,
        ),
        AlignmentEdge(
            left_node_ref=left_rejection.node_ref,
            right_node_ref=right_rejection.node_ref,
            alignment_kind="same_terra_nullius_rejection_coordinate",
            alignment_status="human_reviewed_common_ground_candidate",
            merged_as_single_fact=False,
        ),
    )

    return CrossSourceMaboAlignmentSpecimen(
        schema_version="sl.mabo_cross_source_alignment.v0_1",
        left_source_path="data/corpus/mabo_v_queensland_no2.json",
        right_source_path=NTA_PREAMBLE_SOURCE_PATH,
        left_source_sha256=left_hash,
        right_source_sha256=right_hash,
        left_nodes=(left_recognition, left_rejection),
        right_nodes=(right_rejection, right_recognition),
        alignments=alignments,
        source_provenance_preserved=True,
        exact_surface_equality_required_for_alignment=False,
        alignment_implies_world_truth=False,
        alignment_merges_sources=False,
        common_ground_candidate_coordinates=2,
        controversy_residual_count=0,
    )


__all__ = [
    "AlignmentEdge",
    "CrossSourceMaboAlignmentSpecimen",
    "NTA_PREAMBLE_MABO_SHA256",
    "NTA_PREAMBLE_MABO_TEXT",
    "NTA_PREAMBLE_SOURCE_PATH",
    "build_cross_source_mabo_alignment_specimen",
]
