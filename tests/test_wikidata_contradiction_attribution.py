from src.ontology.wikidata_contradiction_attribution import (
    EvidenceSquare,
    LayerEvidence,
    build_cross_ontology_attribution,
    target_evidence_from_disjoint_union_report,
)


def _support(*evidence: str) -> LayerEvidence:
    return LayerEvidence(EvidenceSquare(True, False), evidence=tuple(evidence))


def _refute(*evidence: str) -> LayerEvidence:
    return LayerEvidence(EvidenceSquare(False, True), evidence=tuple(evidence))


def _neither(*obligations: str) -> LayerEvidence:
    return LayerEvidence(EvidenceSquare(False, False), obligations=tuple(obligations))


def test_opposite_layers_pool_to_conflict_before_trit_collapse() -> None:
    packet = build_cross_ontology_attribution(
        claim_id="alignment-local-stress",
        claim_surface="mapped relation survives alignment",
        source=_support("source relation present"),
        transcription=_support("source transcription exact"),
        alignment=_refute("mapped edge fails transport"),
        target=_support("target relation present"),
    )

    assert packet["pooled_support_square"] == {"supports": True, "refutes": True}
    assert packet["pooled_corner"] == "both"
    assert packet["pooled_trit_projection"] == "unresolved"
    assert packet["required_resolution"] == "conflict"
    assert packet["layers"]["alignment"]["corner"] == "refute-only"


def test_missing_required_axis_remains_unresolved_not_refuted() -> None:
    packet = build_cross_ontology_attribution(
        claim_id="bfo-continuant-occurrent",
        claim_surface="BFO disjointness is licensed through the mapped Wikidata alignment",
        source=_support("BFO continuant disjointWith occurrent"),
        transcription=_support("P12602 maps 0000002/0000003"),
        alignment=_neither("instance transport witness required"),
        target=_neither("target disjointness evidence required"),
    )

    assert packet["pooled_support_square"] == {"supports": True, "refutes": False}
    assert packet["pooled_trit_projection"] == "supported"
    assert packet["required_resolution"] == "unresolved-required-axis"
    assert packet["layers"]["alignment"]["corner"] == "neither"
    assert packet["layers"]["target"]["corner"] == "neither"


def test_target_evidence_keeps_absence_separate_from_failure() -> None:
    absent = target_evidence_from_disjoint_union_report(
        {"source_window_id": "w", "disjoint_unions": []},
        spec_id="QH:QA|QB",
    )
    assert absent.square.corner == "neither"

    failing = target_evidence_from_disjoint_union_report(
        {
            "source_window_id": "w",
            "disjoint_unions": [
                {
                    "spec_id": "QH:QA|QB",
                    "finite_dun_ok": False,
                    "component_not_subclass_count": 0,
                    "union_exhaustivity_failure_count": 1,
                    "pairwise_disjointness_failure_count": 0,
                }
            ],
        },
        spec_id="QH:QA|QB",
    )
    assert failing.square.corner == "refute-only"
    assert failing.evidence == ("union_exhaustivity_failure_count=1",)

    passing = target_evidence_from_disjoint_union_report(
        {
            "source_window_id": "w",
            "disjoint_unions": [
                {
                    "spec_id": "QH:QA|QB",
                    "finite_dun_ok": True,
                    "component_not_subclass_count": 0,
                    "union_exhaustivity_failure_count": 0,
                    "pairwise_disjointness_failure_count": 0,
                }
            ],
        },
        spec_id="QH:QA|QB",
    )
    assert passing.square.corner == "support-only"
