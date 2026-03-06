from __future__ import annotations

import pytest

from scripts import wiki_timeline_aoo_extract as ext


def _nlp():
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    return nlp


@pytest.mark.xfail(
    reason="Conjoined subjects currently collapse to the root actor; "
    "should emit distinct subjects when parser evidence allows."
)
def test_subjects_for_action_splits_conjoined_subjects() -> None:
    nlp = _nlp()
    doc = nlp("George W. Bush and Laura Bush visited Texas.")
    subjects = ext._subjects_for_action(doc, "visit", [], "George W. Bush", "Bush")
    assert "George W. Bush" in subjects
    assert "Laura Bush" in subjects
    assert all(s != "George W. Bush and Laura Bush" for s in subjects)


def test_extract_capitalized_surname_names_ignores_titles_only() -> None:
    text = "President Bush met with Congress."
    out = ext._extract_capitalized_surname_names(text, "Bush", root_actor="George W. Bush")
    assert out == []


def test_extract_actor_tokens_captures_capitalized_words() -> None:
    text = "George W. Bush met Laura Bush in Dallas."
    toks = ext._extract_actor_tokens(text)
    assert "George" in toks
    assert "Bush" in toks
    assert "Laura" in toks


def test_person_name_regex_accepts_multi_token_names() -> None:
    assert ext.PERSON_NAME_RE.fullmatch("George W. Bush")
    assert ext.PERSON_NAME_RE.fullmatch("Barbara Pierce Bush")
    assert not ext.PERSON_NAME_RE.fullmatch("george bush")


def test_honorific_regex_accepts_titles() -> None:
    assert ext.HONORIFIC_RE.fullmatch("Justice Leeming")
    assert ext.HONORIFIC_RE.fullmatch("Dr. King")
    assert not ext.HONORIFIC_RE.fullmatch("Leeming JA")


def test_citation_tail_and_footnote_trim() -> None:
    s = "He testified. CAB"
    assert ext.CITATION_TOKEN_RE.search(s)
    cleaned = ext._strip_parenthetical_citation_noise("He testified (CAB)")
    assert cleaned == "He testified"


@pytest.mark.xfail(
    reason="Possessive subject normalization does not yet handle multi-token possessives "
    "like \"President Obama's\" consistently."
)
def test_normalize_requester_surface_possessive_multi_token() -> None:
    assert ext._normalize_requester_surface("President Obama's") == "President Obama"


@pytest.mark.xfail(
    reason="Numeric normalization currently preserves commas and compact suffixes "
    "without expansion; desired behavior is normalized magnitude + scale."
)
def test_normalize_numeric_mentions_basic_and_compact_suffix() -> None:
    assert ext._normalize_numeric_mention("1,200") == "1200"
    assert ext._normalize_numeric_mention("3.5m") == "3.5 million"
    assert ext._normalize_numeric_mention("2bn") == "2 billion"


@pytest.mark.xfail(
    reason="Currency normalization currently retains compact suffix; "
    "desired behavior is expanded scale + currency code."
)
def test_normalize_numeric_mentions_currency_prefix() -> None:
    assert ext._normalize_numeric_mention("US$ 2.5m") == "2.5 million usd"
    assert ext._normalize_numeric_mention("€10") == "10 eur"


def test_numeric_value_regex_accepts_simple_values() -> None:
    assert ext._NUMERIC_VALUE_RE.fullmatch("1200")
    assert ext._NUMERIC_VALUE_RE.fullmatch("1,200")
    assert ext._NUMERIC_VALUE_RE.fullmatch("3.5")
    assert ext._NUMERIC_VALUE_RE.fullmatch("12%")


@pytest.mark.xfail(
    reason="Numeric role inference is currently conservative (defaults to count) "
    "and should be upgraded to action-aware roles."
)
def test_infer_numeric_role_for_action_context() -> None:
    assert ext._infer_numeric_role("pay", "100 usd", "paid 100 usd") == "transaction_price"
    assert ext._infer_numeric_role("invest", "2 million", "invested 2 million") == "investment_amount"
    assert ext._infer_numeric_role("cost", "5 billion", "cost 5 billion") == "cost_amount"


@pytest.mark.xfail(
    reason="Compact suffix parsing may over-normalize ambiguous tokens like '1m' (meter vs million)."
)
def test_numeric_compact_suffix_ambiguity_negative_case() -> None:
    assert ext._normalize_numeric_mention("1m") == "1 meter"


@pytest.mark.xfail(
    reason="Object extraction currently returns a single span for conjoined objects; "
    "should split into distinct objects when parser evidence allows."
)
def test_objects_for_action_splits_conjoined_objects() -> None:
    nlp = _nlp()
    doc = nlp("The policy targeted Iraq and Afghanistan.")
    verb = next(t for t in doc if t.lemma_ == "target")
    objs = ext._objects_for_verb_token(doc, verb)
    assert "Iraq" in objs
    assert "Afghanistan" in objs
    assert all(o != "Iraq and Afghanistan" for o in objs)


@pytest.mark.xfail(
    reason="Middle-initial names are not captured by surname regex; "
    "should be resolved via entity resolver rather than regex."
)
def test_extract_capitalized_surname_names_handles_middle_initials() -> None:
    text = "George W. Bush spoke to reporters."
    out = ext._extract_capitalized_surname_names(
        text,
        "Bush",
        blocked_first_tokens={"george"},
        root_actor="George W. Bush",
    )
    assert "George W. Bush" in out
