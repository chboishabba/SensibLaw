from __future__ import annotations

from src.text.shared_text_normalization import (
    split_semicolon_clauses,
    split_text_clauses,
    split_text_segments,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)


def test_shared_text_tokenization_normalizes_and_drops_stopwords() -> None:
    tokens = tokenize_canonical_text("The organisation emphasised that I was there.")

    assert "organization" in tokens
    assert "emphasized" in tokens
    assert "the" not in tokens
    assert "i" not in tokens


def test_shared_text_splitting_keeps_pre_semantic_ownership() -> None:
    assert strip_enumeration_prefix("  2.1) The respondent cut off my internet") == (
        "The respondent cut off my internet"
    )
    assert split_text_segments("First sentence. Second sentence!") == [
        "First sentence.",
        "Second sentence!",
    ]
    assert split_text_clauses("I opened the gate, but he stayed outside; I then called.") == [
        "I opened the gate",
        "he stayed outside",
        "I then called.",
    ]
    assert split_semicolon_clauses("one; two ; three") == ["one", "two", "three"]
