from __future__ import annotations

from src.text.lexeme_normalizer import LexemeFlags, normalize_lexeme


def test_lexeme_normalizer_casefolds_words():
    assert normalize_lexeme("Token").norm_text == "token"
    assert normalize_lexeme("TOKEN").norm_text == "token"
    assert normalize_lexeme("ToKeN").norm_text == "token"


def test_lexeme_normalizer_flags_surface_case():
    upper = normalize_lexeme("TOKEN")
    title = normalize_lexeme("Token")
    mixed = normalize_lexeme("ToKeN")

    assert upper.flags & int(LexemeFlags.SURF_ALL_UPPER)
    assert title.flags & int(LexemeFlags.SURF_TITLE)
    assert mixed.flags & int(LexemeFlags.SURF_MIXED_CASE)
