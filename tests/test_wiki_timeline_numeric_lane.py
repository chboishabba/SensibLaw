from __future__ import annotations

import pytest

from scripts import wiki_timeline_aoo_extract as ext


def test_numeric_object_detects_percent_phrase() -> None:
    assert ext._is_numeric_object("89 percent", None) is True
    assert ext._is_numeric_object("7.2%", None) is True


def test_numeric_object_rejects_person_and_year() -> None:
    assert ext._is_numeric_object("George W. Bush", None) is False
    assert ext._is_numeric_object("2001", None) is False


def test_extract_numeric_mentions_pulls_sentence_numbers() -> None:
    text = (
        "Gallup had earlier noted favorability ratings rose from 40 percent "
        "in January 2009 and 35 percent in March 2009 to 45 percent in July 2010."
    )
    nums = ext._extract_numeric_mentions(text)
    assert "40 percent" in nums
    assert "35 percent" in nums
    assert "45 percent" in nums


def test_extract_numeric_mentions_keeps_grouped_number_intact() -> None:
    text = "Bush launched a surge of 21,500 more troops for Iraq."
    nums = ext._extract_numeric_mentions(text)
    assert "21,500" in nums
    assert "21" not in nums


def test_extract_numeric_mentions_keeps_currency_signal() -> None:
    text = "Bush's budget estimated that there would be a $5.6trillion surplus over the next ten years."
    nums = ext._extract_numeric_mentions(text)
    assert "5.6 trillion usd" in nums


def test_numeric_key_rejects_unit_only_noise() -> None:
    assert ext._numeric_key("billion") == ""


def test_numeric_key_schema_and_equivalence() -> None:
    assert ext._numeric_key("21") == "21|"
    assert ext._numeric_key("021") == "21|"
    assert ext._numeric_key("21.0") == "21|"
    assert ext._numeric_key("21,500") == "21500|"
    assert ext._numeric_key("68%") == "68|percent"
    assert ext._numeric_key("68 per cent") == "68|percent"
    assert ext._numeric_key("$500,000") == "500000|usd"
    assert ext._numeric_key("$5.6trillion") == "5.6|trillion_usd"


def test_numeric_key_does_not_silently_expand_scaled_values() -> None:
    assert ext._numeric_key("1.2 billion") == "1.2|billion"
    assert ext._numeric_key("1200000000") == "1200000000|"
    assert ext._numeric_key("1.2 billion") != ext._numeric_key("1200000000")


def test_infer_numeric_role_transaction_price_vs_investment() -> None:
    assert ext._infer_numeric_role("arrange", "89|million_usd", "for $89 million to purchase the team") == "transaction_price"
    assert ext._infer_numeric_role("invest", "500000|usd", "invested $500,000 himself") == "personal_investment"


def test_extract_step_numeric_claims_aligns_multi_verb_sentence_when_parser_available() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    text = (
        "In April 1989, Bush arranged for a group of investors to purchase a controlling "
        "interest of Major League Baseball's Texas Rangers for $89million and invested $500,000 himself to start."
    )
    doc = nlp(text)
    steps = [
        {"action": "arrange", "subjects": ["George W. Bush"], "objects": ["Texas Rangers"]},
        {"action": "invest", "subjects": ["George W. Bush"], "objects": []},
    ]
    claims_by_step = ext._extract_step_numeric_claims(doc, text, steps)

    step0_roles = {c.get("role") for c in claims_by_step.get(0, [])}
    step1_roles = {c.get("role") for c in claims_by_step.get(1, [])}
    assert "transaction_price" in step0_roles
    assert "personal_investment" in step1_roles
