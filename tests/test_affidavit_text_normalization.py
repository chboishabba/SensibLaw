from __future__ import annotations

from src.policy.affidavit_text_normalization import (
    find_numbered_rebuttal_start,
    predicate_focus_tokens,
    split_affidavit_text,
    split_source_segment_clauses,
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
