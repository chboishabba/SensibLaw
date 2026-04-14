from __future__ import annotations

from src.policy.affidavit_normalized_surface import (
    matching,
    review_hints,
    semantics,
    structural,
    text,
)


def test_affidavit_normalized_surface_groups_existing_helpers() -> None:
    proposition_rows = text.split_affidavit_text("The respondent cut off my internet.")
    assert proposition_rows[0]["proposition_id"] == "aff-prop:p1-s1"

    claim_root = matching.derive_claim_root_fields(
        proposition_text="The respondent cut off my internet.",
        duplicate_match_excerpt=None,
        best_match_excerpt="I cut off the internet.",
    )
    assert claim_root["claim_root_text"] == "The respondent cut off my internet."

    hints = review_hints.extract_extraction_hints(
        "Hearing on 6 March 2025 at [00:01:00 -> 00:02:00].",
        tokenize=text.tokenize_affidavit_text,
    )
    assert hints["has_transcript_timestamp_hint"] is True

    packets = semantics.build_justification_packets("I acted with consent.")
    assert packets[0]["type"] == "consent"

    structural_result = structural.analyze_structural_sentence(
        "I think he left.",
        dependencies_getter=None,
    )
    assert structural_result == {}
