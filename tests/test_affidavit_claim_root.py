from __future__ import annotations

from src.policy.affidavit_claim_root import (
    derive_claim_root_fields,
    is_duplicate_response_excerpt,
    stable_claim_root_id,
)


def test_is_duplicate_response_excerpt_detects_near_duplicate() -> None:
    assert is_duplicate_response_excerpt(
        "The respondent cut off my internet in November 2024.",
        "The respondent cut off my internet in November 2024.",
    )
    assert not is_duplicate_response_excerpt(
        "The respondent cut off my internet in November 2024.",
        "I later sent an email about the outage.",
    )


def test_derive_claim_root_fields_prefers_duplicate_excerpt_and_context() -> None:
    result = derive_claim_root_fields(
        proposition_text="The respondent cut off my internet in November 2024.",
        duplicate_match_excerpt="The respondent cut off my internet in November 2024.",
        best_match_excerpt="I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
    )

    assert result["claim_root_basis"] == "duplicate_excerpt"
    assert result["claim_root_text"] == "The respondent cut off my internet in November 2024."
    assert result["alternate_context_excerpt"] == (
        "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation."
    )


def test_stable_claim_root_id_is_deterministic() -> None:
    left = stable_claim_root_id("The respondent cut off my internet in November 2024.")
    right = stable_claim_root_id("the respondent cut off my internet in november 2024.")

    assert left == right
    assert left.startswith("claim_root:")
