from __future__ import annotations

import pytest

from src.nlp.spacy_adapter import parse


@pytest.fixture(scope="module")
def sample_text() -> str:
    return "This is a test. Here's another sentence!"


def test_sentences_respect_text_boundaries(sample_text: str) -> None:
    result = parse(sample_text)
    assert result["text"] == sample_text
    assert len(result["sents"]) == 2

    for sentence in result["sents"]:
        start, end = sentence["start"], sentence["end"]
        assert sample_text[start:end] == sentence["text"]
        for token in sentence["tokens"]:
            token_start, token_end = token["start"], token["end"]
            assert sample_text[token_start:token_end] == token["text"]
            assert token["lemma"]


def test_parse_is_deterministic(sample_text: str) -> None:
    first = parse(sample_text)
    second = parse(sample_text)
    assert first == second
