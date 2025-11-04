"""Tests for the pipeline tokenisation helpers."""

from __future__ import annotations

from src.pipeline.tokens import Token, spacy_adapter


def test_parse_returns_tokens() -> None:
    text = "Law reform improves justice"
    tokens = spacy_adapter.parse(text)

    assert [token.text for token in tokens] == ["Law", "reform", "improves", "justice"]
    for token in tokens:
        assert isinstance(token, Token)


def test_parse_handles_empty_text() -> None:
    assert spacy_adapter.parse("") == []
