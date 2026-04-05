from __future__ import annotations

from src.policy.affidavit_text_normalization import (
    build_affidavit_duplicate_candidates,
    find_numbered_rebuttal_start,
    is_duplicate_affidavit_unit,
    is_duplicate_response_excerpt,
    predicate_focus_tokens,
    split_affidavit_text,
    split_source_segment_clauses,
    strip_enumeration_prefix,
    token_overlap_similarity,
    tokenize_duplicate_filter_text,
    tokenize_affidavit_text,
)


def test_tokenize_affidavit_text_normalizes_and_drops_stopwords() -> None:
    tokens = tokenize_affidavit_text("The organisation emphasised that I was there.")

    assert "organization" in tokens
    assert "emphasized" in tokens
    assert "the" not in tokens
    assert "i" not in tokens


def test_predicate_focus_tokens_drop_months_and_keep_short_domain_token() -> None:
    tokens = predicate_focus_tokens("In November 2024 I revoked the EPOA authority.")

    assert "november" not in tokens
    assert "2024" not in tokens
    assert "epoa" in tokens
    assert "revoked" in tokens


def test_split_source_segment_clauses_breaks_on_semicolon_and_conjunctions() -> None:
    clauses = split_source_segment_clauses(
        "I opened the gate, but he stayed outside; I then called the support worker."
    )

    assert clauses == [
        "I opened the gate",
        "he stayed outside",
        "I then called the support worker.",
    ]


def test_find_numbered_rebuttal_start_finds_inline_rebuttal_packet() -> None:
    assert find_numbered_rebuttal_start("Overview text 1. First rebuttal point") == 14
    assert find_numbered_rebuttal_start("No numbered rebuttal here") is None


def test_split_affidavit_text_decomposes_semicolon_clause() -> None:
    propositions = split_affidavit_text(
        "In mid-November 2024, there was an incident where I was waiting for my support worker to arrive; as I came down the side of the house, I could hear Johl was on the phone."
    )

    assert [row["proposition_id"] for row in propositions] == ["aff-prop:p1-s1", "aff-prop:p1-s2"]
    assert propositions[0]["tokens"]
    assert propositions[1]["tokens"]


def test_duplicate_filter_helpers_live_under_text_normalization() -> None:
    assert strip_enumeration_prefix("  2.1) The respondent cut off my internet") == (
        "The respondent cut off my internet"
    )

    tokens = tokenize_duplicate_filter_text("1. The organisation emphasised privacy.")
    assert "organization" in tokens
    assert "privacy" in tokens

    assert token_overlap_similarity({"internet", "cut"}, {"internet", "cut"}) == 1.0

    affidavit_text = (
        "The respondent cut off my internet in November 2024.\n"
        "The respondent pushed me on the back deck.\n"
    )
    candidates = build_affidavit_duplicate_candidates(affidavit_text)
    assert len(candidates) == 2
    assert is_duplicate_affidavit_unit(
        "1. The respondent cut off my internet in November 2024.",
        affidavit_candidates=candidates,
    )


def test_duplicate_response_excerpt_detection_lives_under_text_surface() -> None:
    assert is_duplicate_response_excerpt(
        "The respondent cut off my internet in November 2024.",
        "The respondent cut off my internet in November 2024.",
    )
    assert not is_duplicate_response_excerpt(
        "The respondent cut off my internet in November 2024.",
        "I later sent an email about the outage.",
    )
