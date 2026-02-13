from __future__ import annotations

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
