from __future__ import annotations

from sensiblaw.interfaces.shared_reducer import (
    collect_canonical_lexeme_occurrences,
    collect_canonical_lexeme_occurrences_with_profile,
    collect_canonical_structure_occurrences,
    get_canonical_tokenizer_profile,
    tokenize_canonical_detailed,
    tokenize_canonical_with_spans,
)
from src.text.deterministic_legal_tokenizer import tokenize_detailed, tokenize_with_spans
from src.text.lexeme_index import (
    collect_lexeme_occurrences,
    collect_lexeme_occurrences_with_profile,
    get_tokenizer_profile,
)
from src.text.structure_index import collect_structure_occurrences


def test_shared_reducer_profile_matches_internal_contract() -> None:
    assert get_canonical_tokenizer_profile() == get_tokenizer_profile()
    assert get_canonical_tokenizer_profile()["canonical_mode"] == "deterministic_legal"


def test_shared_reducer_lexeme_occurrences_match_internal_function() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B and run pytest in ./SensibLaw/tests/test_lexeme_layer.py"
    assert collect_canonical_lexeme_occurrences(text) == collect_lexeme_occurrences(text)


def test_shared_reducer_lexeme_occurrences_with_profile_match_internal_function() -> None:
    text = "The United States Department of Defense cited Article 51."
    assert collect_canonical_lexeme_occurrences_with_profile(text) == collect_lexeme_occurrences_with_profile(text)


def test_shared_reducer_structure_occurrences_match_internal_function() -> None:
    text = "User: cite Civil Liability Act 2002 (NSW) s 5B.\n$ pytest SensibLaw/tests/test_lexeme_layer.py -q\n"
    assert collect_canonical_structure_occurrences(text) == collect_structure_occurrences(text)


def test_shared_reducer_span_tokenization_matches_internal_function() -> None:
    text = "Civil Liability Act 2002 (NSW) Pt 4 Div 2 r 7.32 Sch 1 cl 4"
    assert tokenize_canonical_with_spans(text) == tokenize_with_spans(text)
    assert tokenize_canonical_detailed(text) == tokenize_detailed(text)
