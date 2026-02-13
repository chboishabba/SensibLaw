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


def test_extract_numeric_mentions_keeps_currency_signal_with_doc_scan() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    text = "Bush's budget estimated that there would be a $5.6trillion surplus over the next ten years."
    nums = ext._extract_numeric_mentions(text, doc=nlp(text))
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
    assert ext._numeric_key("$5.6trillion") == "5.6e12|usd"
    assert ext._numeric_key("1.2 billion usd") == "1.2e9|usd"


def test_numeric_key_does_not_silently_expand_scaled_values() -> None:
    assert ext._numeric_key("1.2 billion") == "1.2|billion"
    assert ext._numeric_key("1200000000") == "1200000000|"
    assert ext._numeric_key("1.2 billion") != ext._numeric_key("1200000000")


def test_infer_numeric_role_transaction_price_vs_investment() -> None:
    assert ext._infer_numeric_role("arrange", "8.9e7|usd", "for $89 million to purchase the team") == "transaction_price"
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


def test_numeric_normalized_payload_includes_parts_and_magnitude_id() -> None:
    payload = ext._numeric_normalized_payload("5.6e12|usd", raw="$5.6trillion")
    assert payload["value"] == "5.6e12"
    assert payload["unit"] == "usd"
    assert payload["scale"] is None
    assert payload["currency"] == "usd"
    assert payload["expression"]["scale_word"] == "trillion"
    assert payload["expression"]["exponent_from_scale"] == 12
    assert payload["expression"]["coercion_applied"] is True
    assert payload["surface"]["currency_symbol_position"] == "prefix"
    assert payload["surface"]["scale_word_used"] is True
    assert payload["surface"]["spacing_pattern"] == "no_space"
    assert str(payload.get("magnitude_id") or "").startswith("mag:")


def test_extract_step_numeric_claims_attaches_time_anchor_and_years_when_available() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    text = "In 2001, Bush estimated there would be a $5.6trillion surplus over the next ten years."
    doc = nlp(text)
    steps = [{"action": "estimate", "subjects": ["George W. Bush"], "objects": []}]
    claims_by_step = ext._extract_step_numeric_claims(
        doc,
        text,
        steps,
        event_anchor={"year": 2000, "month": 9, "day": 27, "precision": "day", "kind": "mention", "text": "September 27, 2000"},
    )
    claims = claims_by_step.get(0) or []
    assert claims
    c = claims[0]
    assert c.get("time_anchor", {}).get("year") == 2000
    assert 2001 in (c.get("time_years") or [])
    assert isinstance(c.get("normalized"), dict)
    assert c["normalized"]["expression"]["scale_word"] == "trillion"
    assert c["normalized"]["surface"]["currency_symbol_position"] == "prefix"


def test_extract_numeric_span_candidates_ignores_day_number_in_date_entity() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    text = "On September 27, 2000, Bush estimated a $5.6trillion surplus."
    doc = nlp(text)
    cands = ext._extract_numeric_span_candidates(doc)
    keys = {str(c.get("key") or "") for c in cands}
    assert "27|" not in keys
    assert "5.6e12|usd" in keys


def test_extract_numeric_mentions_ignores_day_number_in_date_phrase() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    text = (
        "He received the highest recorded approval ratings in the wake of the "
        "September 11 attacks, and one of the lowest ratings during the 2008 financial crisis."
    )
    nums = ext._extract_numeric_mentions(text, doc=nlp(text))
    keys = {ext._numeric_key(x) for x in nums}
    assert "11|" not in keys
    assert "2008|" not in keys


def test_dedupe_numeric_objects_prefers_currency_variant() -> None:
    vals = ["5.6 trillion", "5.6 trillion usd", "500000 usd"]
    out = ext._dedupe_numeric_objects_prefer_currency(vals)
    assert "5.6 trillion usd" in out
    assert "5.6 trillion" not in out
    assert "500000 usd" in out
