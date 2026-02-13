from __future__ import annotations

from scripts import wiki_timeline_extract as ext


def test_parse_section_anchor_extracts_month_day_year_heading() -> None:
    anchor = ext._parse_section_anchor("September 11, 2001 attacks")
    assert anchor is not None
    assert anchor.year == 2001
    assert anchor.month == 9
    assert anchor.day == 11
    assert anchor.precision == "day"
    assert anchor.kind == "weak"


def test_parse_section_anchor_ignores_year_range_sections() -> None:
    anchor = ext._parse_section_anchor("Presidency (2001-2009)")
    assert anchor is None


def test_media_caption_guard_detects_thumb_lines() -> None:
    assert ext._looks_like_media_caption("thumb|left|President Bush speaking")
    assert not ext._looks_like_media_caption("President Bush addressed the nation.")


def test_parse_inline_anchors_extracts_embedded_month_day_year() -> None:
    anchors = ext._parse_inline_anchors(
        "The 20th anniversary of the September 11, 2001, terrorist attacks was marked in New York."
    )
    assert len(anchors) == 1
    a = anchors[0]
    assert a.year == 2001 and a.month == 9 and a.day == 11
    assert a.kind == "mention"


def test_parse_special_event_anchors_extracts_sept11_without_year() -> None:
    anchors = ext._parse_special_event_anchors(
        "Bush's priorities were significantly altered following the September 11 attacks."
    )
    assert len(anchors) == 1
    a = anchors[0]
    assert a.year == 2001 and a.month == 9 and a.day == 11
    assert a.kind == "mention"


def test_parse_special_event_anchors_extracts_911_token() -> None:
    anchors = ext._parse_special_event_anchors("He described 9/11 as a defining moment.")
    assert len(anchors) == 1
    a = anchors[0]
    assert a.year == 2001 and a.month == 9 and a.day == 11
