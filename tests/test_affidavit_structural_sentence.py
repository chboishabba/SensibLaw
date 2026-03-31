from __future__ import annotations

from src.policy.affidavit_structural_sentence import analyze_structural_sentence


class _Token:
    def __init__(self, text: str, lemma: str | None = None) -> None:
        self.text = text
        self.lemma = lemma or text


class _Sentence:
    def __init__(self, candidates: dict[str, list[_Token]]) -> None:
        self.candidates = candidates


def test_analyze_structural_sentence_extracts_subject_verb_and_negation() -> None:
    result = analyze_structural_sentence(
        "I do not feel I did such.",
        dependencies_getter=lambda _: [
            _Sentence(
                {
                    "nsubj": [_Token("I")],
                    "verb": [_Token("feel", "feel")],
                    "neg": [_Token("not")],
                }
            )
        ],
    )

    assert result["subject_texts"] == ["I"]
    assert result["verb_lemmas"] == ["feel"]
    assert result["has_negation"] is True
    assert result["has_first_person_subject"] is True
    assert result["has_hedge_verb"] is True


def test_analyze_structural_sentence_returns_empty_on_missing_parser() -> None:
    assert analyze_structural_sentence("test", dependencies_getter=None) == {}


def test_analyze_structural_sentence_returns_empty_on_parser_error() -> None:
    def _boom(_: str) -> list[object]:
        raise RuntimeError("boom")

    assert analyze_structural_sentence("test", dependencies_getter=_boom) == {}
