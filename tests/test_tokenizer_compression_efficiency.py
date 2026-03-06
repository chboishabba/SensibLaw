from src.text.deterministic_legal_tokenizer import tokenize_with_spans
from src.text.lexeme_index import collect_lexeme_occurrences


def _avg_chars_per_token(text: str) -> float:
    tokens = tokenize_with_spans(text)
    if not tokens:
        return 0.0
    total_chars = sum(end - start for _, start, end in tokens)
    return total_chars / len(tokens)


def test_compression_efficiency_plain_sentence():
    text = "George Bush was considered really great did you know that?"
    tokens = tokenize_with_spans(text)
    avg = _avg_chars_per_token(text)
    # Expect roughly word-level granularity; average token length should stay in a healthy band.
    assert 2.0 <= avg <= 8.0
    assert len(tokens) <= 2 * len(text.split())


def test_compression_efficiency_legal_reference():
    text = "See Civil Liability Act 2002 (NSW) s 5B(2)(a) and [2024] HCA 12."
    tokens = tokenize_with_spans(text)
    avg = _avg_chars_per_token(text)
    # Legal references should stay atomic, yielding a higher avg length than plain words but not swallowing paragraphs.
    assert 3.0 <= avg <= 15.0
    # Ensure token count does not explode relative to whitespace-delimited words.
    assert len(tokens) <= 2 * len(text.split())


def test_deterministic_legal_reference_is_no_more_fragmented_than_legacy():
    text = "Civil Liability Act 2002 (NSW) s 5B(2)(a) Pt 4 Div 2 r 7.32 Sch 1 cl 4"
    deterministic = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
    legacy = collect_lexeme_occurrences(text, canonical_mode="legacy_regex")
    assert len(deterministic) <= len(legacy)
