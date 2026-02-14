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


def test_template_residue_guard_detects_infobox_like_lines() -> None:
    assert ext._looks_like_template_residue(
        "<!--See WP:EDN--> | term_start1 = January 17, 1995 | term_end1 = December 21, 2000 | predecessor1 = Ann Richards"
    )
    assert not ext._looks_like_template_residue("George Walker Bush was born on July 6, 1946, in New Haven.")


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


def test_parse_inline_year_range_anchor_extracts_start_year() -> None:
    anchors = ext._parse_inline_year_range_anchors(
        "He served as president of the United States from 2001 to 2009."
    )
    assert len(anchors) == 1
    a = anchors[0]
    assert a.year == 2001
    assert a.month is None and a.day is None
    assert a.precision == "year"
    assert a.kind == "mention"


def test_lead_anchor_preference_drops_birth_day_when_service_range_present() -> None:
    sentence = (
        "George Walker Bush (born July 6, 1946) is an American politician "
        "who served as the 43rd president of the United States from 2001 to 2009."
    )
    anchors = [
        ext.DateAnchor(year=1946, month=7, day=6, precision="day", text="July 6, 1946", kind="mention"),
        ext.DateAnchor(year=2001, month=None, day=None, precision="year", text="from 2001 to 2009", kind="mention"),
    ]
    out = ext._apply_lead_anchor_preference("(lead)", sentence, anchors)
    assert any(a.year == 2001 and a.precision == "year" for a in out)
    assert not any(a.year == 1946 and a.precision == "day" for a in out)
