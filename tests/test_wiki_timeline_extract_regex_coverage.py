from __future__ import annotations

import pytest

from scripts import wiki_timeline_extract as ext


def test_parse_anchor_on_mdy() -> None:
    line = "On March 19, 2003, the invasion began."
    anchor = ext._parse_anchor(line)
    assert anchor is not None
    assert anchor.year == 2003
    assert anchor.month == 3
    assert anchor.day == 19
    assert anchor.precision == "day"


def test_parse_anchor_in_my_and_in_y() -> None:
    a1 = ext._parse_anchor("In May 2004, he spoke.")
    a2 = ext._parse_anchor("In 2005, he spoke.")
    assert a1 is not None and a1.month == 5 and a1.year == 2004
    assert a2 is not None and a2.year == 2005 and a2.precision == "year"


def test_parse_inline_year_range_anchor() -> None:
    anchors = ext._parse_inline_year_range_anchors("from 2001 to 2009 he served.")
    assert anchors and anchors[0].year == 2001


def test_parse_special_event_sept11_anchor() -> None:
    anchors = ext._parse_special_event_anchors("The September 11 attacks changed policy.")
    assert anchors and anchors[0].year == 2001 and anchors[0].month == 9 and anchors[0].day == 11


def test_split_sentences_protects_abbrevs_and_initials() -> None:
    s = "George W. Bush met with U.S. officials. He spoke."
    parts = ext._split_sentences(s)
    assert len(parts) == 2
    assert parts[0].endswith("officials.")


def test_cleanup_sentence_text_strips_citation_tail() -> None:
    s = "He testified, Smith, John (May 17, 2004)."
    out = ext._cleanup_sentence_text(s)
    assert "Smith, John" not in out


@pytest.mark.xfail(
    reason="Citation tail stripping may over-remove when names are part of the sentence."
)
def test_cleanup_sentence_text_overreach_negative_case() -> None:
    s = "He met Smith, John in May."
    out = ext._cleanup_sentence_text(s)
    assert out == s
