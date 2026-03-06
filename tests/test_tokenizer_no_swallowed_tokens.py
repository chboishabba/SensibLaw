from src.text.deterministic_legal_tokenizer import (
    TokenType,
    tokenize_detailed,
)


ALLOWED_SPACEY_TYPES = {
    TokenType.ACT_REFERENCE,
    TokenType.CASE_REFERENCE,
    TokenType.SECTION_REFERENCE,
    TokenType.SUBSECTION_REFERENCE,
    TokenType.PARAGRAPH_REFERENCE,
    TokenType.PART_REFERENCE,
    TokenType.DIVISION_REFERENCE,
    TokenType.RULE_REFERENCE,
    TokenType.SCHEDULE_REFERENCE,
    TokenType.CLAUSE_REFERENCE,
}


def test_plain_sentence_has_no_spacey_tokens():
    text = "George Bush was considered really great did you know that?"
    tokens = tokenize_detailed(text)
    word_tokens = [t for t in tokens if t.token_type == TokenType.WORD]
    # Expect one WORD token per whitespace-delimited word (punct handled separately).
    assert len(word_tokens) == 10
    # Ensure no token (other than allowed structural types) contains whitespace.
    for tok in tokens:
        if " " in tok.text:
            assert tok.token_type in ALLOWED_SPACEY_TYPES, f"Whitespace token swallowed words: {tok}"


def test_structural_tokens_can_contain_spaces_only_when_expected():
    text = "See Civil Liability Act 2002 (NSW) s 5B(2)(a) and [2024] HCA 12."
    tokens = tokenize_detailed(text)
    for tok in tokens:
        if " " in tok.text:
            assert tok.token_type in ALLOWED_SPACEY_TYPES, f"Unexpected spaced token: {tok}"
        # Guard against overlong word tokens that might swallow multiple words.
        if tok.token_type == TokenType.WORD:
            assert " " not in tok.text
            assert len(tok.text) <= 40
