from __future__ import annotations

from src.fact_intake.wiki_lexical import (
    build_revision_comment_zelph_facts,
    classify_revision_comment,
    parse_revision_statement,
)


def test_parse_revision_statement_extracts_author_and_comment() -> None:
    parsed = parse_revision_statement("Revision by BD2412: Reverted unsourced claim pending attribution.")
    assert parsed == {
        "author": "BD2412",
        "comment": "Reverted unsourced claim pending attribution.",
    }


def test_classify_revision_comment_marks_volatility_signal() -> None:
    tags = classify_revision_comment("Reverted unsourced change and removed defamatory wording.")
    assert "reversion_edit" in tags
    assert "volatility_signal" in tags


def test_build_revision_comment_zelph_facts_emits_comment_lexemes_and_structure() -> None:
    facts = build_revision_comment_zelph_facts(
        revision_id="demo-1",
        author="BD2412",
        comment_text="Reverted unsourced change.",
    )
    assert any('"rev_demo_1" "by user" "BD2412".' == fact for fact in facts)
    assert any('"rev_demo_1" "has comment" <' in fact for fact in facts)
    assert any('"rev_demo_1" "has comment lexeme" "reverted".' == fact for fact in facts)
    assert any('"lex_' in fact and '"has text" "Reverted".' in fact for fact in facts)
