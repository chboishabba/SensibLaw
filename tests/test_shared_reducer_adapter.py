from __future__ import annotations

from sensiblaw.interfaces.shared_reducer import (
    collect_canonical_lexeme_refs,
    collect_canonical_lexeme_occurrences,
    collect_canonical_lexeme_occurrences_with_profile,
    collect_canonical_relational_bundle,
    collect_canonical_structure_occurrences,
    get_canonical_tokenizer_profile,
    get_canonical_tokenizer_profile_receipt,
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


def test_shared_reducer_profile_receipt_is_bounded_and_stable() -> None:
    receipt = get_canonical_tokenizer_profile_receipt()
    assert set(receipt) == {
        "profile_id",
        "canonical_tokenizer_id",
        "canonical_tokenizer_version",
        "canonical_mode",
    }
    assert receipt["canonical_mode"] == "deterministic_legal"
    assert receipt == get_canonical_tokenizer_profile_receipt()


def test_shared_reducer_lexeme_occurrences_match_internal_function() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B and run pytest in ./SensibLaw/tests/test_lexeme_layer.py"
    assert collect_canonical_lexeme_occurrences(text) == collect_lexeme_occurrences(text)


def test_shared_reducer_lexeme_occurrences_with_profile_match_internal_function() -> None:
    text = "The United States Department of Defense cited Article 51."
    assert collect_canonical_lexeme_occurrences_with_profile(text) == collect_lexeme_occurrences_with_profile(text)


def test_shared_reducer_lexeme_refs_are_bounded_and_span_anchored() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B applies here."
    refs = collect_canonical_lexeme_refs(text)
    occurrences = collect_lexeme_occurrences(text)
    assert len(refs) == len(occurrences)
    assert refs[0].keys() == {"occurrence_id", "kind", "span_start", "span_end"}
    assert refs[0]["kind"] == occurrences[0].kind
    assert refs[0]["span_start"] == occurrences[0].start_char
    assert refs[0]["span_end"] == occurrences[0].end_char


def test_shared_reducer_structure_occurrences_match_internal_function() -> None:
    text = "User: cite Civil Liability Act 2002 (NSW) s 5B.\n$ pytest SensibLaw/tests/test_lexeme_layer.py -q\n"
    assert collect_canonical_structure_occurrences(text) == collect_structure_occurrences(text)


def test_shared_reducer_span_tokenization_matches_internal_function() -> None:
    text = "Civil Liability Act 2002 (NSW) Pt 4 Div 2 r 7.32 Sch 1 cl 4"
    assert tokenize_canonical_with_spans(text) == tokenize_with_spans(text)
    assert tokenize_canonical_detailed(text) == tokenize_detailed(text)


def test_shared_reducer_relational_bundle_is_span_anchored_and_question_shaped() -> None:
    text = "alice:\nQ: how does crypto promise to hedge asset volatility and uncertainty in 2026"

    bundle = collect_canonical_relational_bundle(text)

    assert bundle["version"] == "relational_bundle_v1"
    assert bundle["canonical_text"] == text
    assert bundle["atoms"]
    assert bundle["relations"]
    for atom in bundle["atoms"]:
        start, end = atom["span"]
        assert text[start:end] == atom["text"]

    relation_types = {relation["type"] for relation in bundle["relations"]}
    assert {"predicate", "modifier", "conjunction", "temporal", "composition"} <= relation_types
    composition_relation = next(
        relation for relation in bundle["relations"] if relation["type"] == "composition"
    )
    composition_role = composition_relation["roles"][0]
    assert composition_role["value"] == "question"
    assert text[composition_role["span_start"]:composition_role["span_end"]]
