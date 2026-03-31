from __future__ import annotations

from src.policy.affidavit_candidate_alignment import (
    family_alignment_adjustment,
    is_quote_rebuttal_support_excerpt,
    predicate_alignment_score,
)


def test_predicate_alignment_score_detects_shared_focus() -> None:
    score = predicate_alignment_score(
        "Johl came into my room and pulled out the keyboard so I couldn't type.",
        "I was forced to remove the keyboard to prevent further disagreements.",
    )

    assert score > 0.3


def test_quote_rebuttal_support_excerpt_detects_acknowledgement() -> None:
    assert is_quote_rebuttal_support_excerpt(
        "I acknowledge this likely occurred on many occasions."
    )
    assert not is_quote_rebuttal_support_excerpt(
        "I later wrote an unrelated email."
    )


def test_family_alignment_adjustment_rewards_audio_family_match() -> None:
    score = family_alignment_adjustment(
        "Johl came into my room and would turn off or stop what I was listening to on my computer.",
        "I acknowledge this likely occurred on many occasions.",
        "Johl came into my room and would turn off or stop what I was listening to on my computer. I acknowledge this likely occurred on many occasions.",
    )

    assert score > 0.1


def test_family_alignment_adjustment_penalizes_epoa_mismatch() -> None:
    score = family_alignment_adjustment(
        "Johl revoked the EPOA documents.",
        "I filed an RTA tenancy dispute with the landlord.",
        "I filed an RTA tenancy dispute with the landlord.",
    )

    assert score < 0.0
