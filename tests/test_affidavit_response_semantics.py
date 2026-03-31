from __future__ import annotations

from src.policy.affidavit_response_semantics import (
    derive_claim_state,
    derive_missing_dimensions,
    derive_primary_target_component,
    derive_relation_classification,
    derive_semantic_basis,
    infer_response_packet,
)


def test_infer_response_packet_marks_characterization_dispute() -> None:
    packet = infer_response_packet(
        proposition_text="I felt his behaviour was coercive and controlling.",
        best_match_excerpt="I do not feel I acted in a controlling or coercive manner.",
        duplicate_match_excerpt=None,
        response_role="hedged_denial",
        coverage_status="partial",
        characterization_terms={"coercive", "controlling"},
        justification_matches={},
    )

    assert "deny_characterisation" in packet["response_acts"]
    assert "hedged_denial" in packet["response_acts"]
    assert "characterization_dispute" in packet["legal_significance_signals"]


def test_derive_primary_target_component_prefers_characterization() -> None:
    target = derive_primary_target_component(
        response={"component_targets": ["predicate_text", "characterization"]},
        response_acts=["deny_characterisation"],
    )

    assert target == "characterization"


def test_derive_semantic_basis_mixed_for_structural_and_heuristic() -> None:
    basis = derive_semantic_basis(
        response_cues=[],
        response={"speech_act": "other"},
        response_component_bindings=[{"component": "time"}],
        justifications=[{"type": "consent"}],
    )

    assert basis == "mixed"


def test_derive_claim_state_mixed_support_becomes_partially_reconciled() -> None:
    state = derive_claim_state(
        response_acts=["admit_fact", "deny_fact"],
        legal_significance_signals=[],
        support_status="substantively_addressed",
        duplicate_match_excerpt=None,
    )

    assert state["support_direction"] == "mixed"
    assert state["conflict_state"] == "partially_reconciled"


def test_derive_missing_dimensions_for_time_target() -> None:
    dimensions = derive_missing_dimensions(
        coverage_status="partial",
        support_status="responsive_but_non_substantive",
        primary_target_component="time",
        best_match_excerpt="In 2024 something happened.",
        duplicate_match_excerpt=None,
    )

    assert "time" in dimensions
    assert "direct_response" in dimensions


def test_derive_relation_classification_duplicate_root_support() -> None:
    relation = derive_relation_classification(
        coverage_status="partial",
        support_status="responsive_but_non_substantive",
        conflict_state="disputed",
        support_direction="against",
        best_response_role="dispute",
        primary_target_component="predicate_text",
        best_match_excerpt="Context clause",
        duplicate_match_excerpt="Exact duplicate clause",
        alternate_context_excerpt="Context clause",
    )

    assert relation["relation_root"] == "supports"
    assert relation["relation_leaf"] == "equivalent_support"
    assert relation["explanation"]["matched_response"] == "Exact duplicate clause"
