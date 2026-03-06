from __future__ import annotations

from src.text.deterministic_legal_tokenizer import TokenType, tokenize_with_spans


def test_deterministic_legal_tokenizer_is_repeatable() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B(2)(a)"
    first = tokenize_with_spans(text)
    second = tokenize_with_spans(text)

    assert first == second


def test_deterministic_legal_tokenizer_preserves_span_text() -> None:
    text = "Civil Liability Act 2002 (NSW) s 5B(2)(a)"
    tokens = tokenize_with_spans(text)

    assert tokens == [
        ("Civil Liability Act 2002 (NSW)", 0, 30),
        ("s 5B", 31, 35),
        ("(2)", 35, 38),
        ("(a)", 38, 41),
    ]


def test_deterministic_legal_tokenizer_atomizes_section_reference() -> None:
    from src.text.deterministic_legal_tokenizer import tokenize_detailed

    tokens = tokenize_detailed("s 5B(2)(a)")
    token_types = [token.token_type for token in tokens]

    assert token_types == [
        TokenType.SECTION_REFERENCE,
        TokenType.SUBSECTION_REFERENCE,
        TokenType.PARAGRAPH_REFERENCE,
    ]


def test_deterministic_legal_tokenizer_atomizes_act_and_rule_chain() -> None:
    from src.text.deterministic_legal_tokenizer import tokenize_detailed

    tokens = tokenize_detailed("Civil Liability Act 2002 (NSW) Pt 4 Div 2 r 7.32 Sch 1 cl 4")
    assert [token.token_type for token in tokens] == [
        TokenType.ACT_REFERENCE,
        TokenType.PART_REFERENCE,
        TokenType.DIVISION_REFERENCE,
        TokenType.RULE_REFERENCE,
        TokenType.SCHEDULE_REFERENCE,
        TokenType.CLAUSE_REFERENCE,
    ]


def test_deterministic_legal_tokenizer_atomizes_gwb_style_act_and_court_refs() -> None:
    from src.text.deterministic_legal_tokenizer import tokenize_detailed

    tokens = tokenize_detailed(
        "Bush signed the Military Commissions Act of 2006 and the ruling was vacated by the United States Court of Appeals for the Sixth Circuit before reaching the U.S. Supreme Court."
    )
    token_types = [token.token_type for token in tokens]
    assert TokenType.ACT_REFERENCE in token_types
    assert TokenType.COURT_REFERENCE in token_types


def test_deterministic_legal_tokenizer_atomizes_article_and_instrument_refs() -> None:
    from src.text.deterministic_legal_tokenizer import tokenize_detailed

    tokens = tokenize_detailed(
        "Plaintiff S157/2002 v Commonwealth [2003] HCA 2 considered s 75(v) and Art 5 of the instrument before the India–United States Civil Nuclear Agreement and the U.S.–DPRK Agreed Framework."
    )
    token_types = [token.token_type for token in tokens]
    assert TokenType.ARTICLE_REFERENCE in token_types
    assert TokenType.INSTRUMENT_REFERENCE in token_types


def test_deterministic_legal_tokenizer_does_not_treat_artful_or_ambiguous_art_as_article_ref() -> None:
    from src.text.deterministic_legal_tokenizer import tokenize_detailed

    samples = [
        "Artful prose was a strength of GWB.",
        "The Art 5 gallery opened downtown.",
        "The label Art 5 was printed on the canvas.",
    ]
    for text in samples:
        token_types = [token.token_type for token in tokenize_detailed(text)]
        assert TokenType.ARTICLE_REFERENCE not in token_types
