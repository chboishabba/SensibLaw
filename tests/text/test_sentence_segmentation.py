from __future__ import annotations

import pytest

from src.text.sentences import get_nlp, iter_sentence_spans, make_doc, segment_sentences


def test_get_nlp_configures_sentencizer() -> None:
    nlp = get_nlp()
    assert "sentencizer" in nlp.pipe_names


@pytest.mark.parametrize(
    "text,expected",
    [
        ("First sentence. Second sentence.", ["First sentence.", "Second sentence."]),
        ("Heading\n\nBody continues? Indeed!", ["Heading", "Body continues?", "Indeed!"]),
    ],
)
def test_make_doc_exposes_sentence_iterator(text: str, expected: list[str]) -> None:
    doc = make_doc(text)
    assert [span.text.strip() for span in iter_sentence_spans(doc)] == expected


def test_segment_sentences_returns_models_with_offsets() -> None:
    text = " A short clause. And another one!  Final bit?"
    sentences = segment_sentences(text)
    assert [sentence.text for sentence in sentences] == [
        "A short clause.",
        "And another one!",
        "Final bit?",
    ]
    assert sentences[0].index == 0
    assert sentences[1].start_char > sentences[0].end_char
    assert sentences[2].end_char <= len(text)
