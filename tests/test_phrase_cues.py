from __future__ import annotations

from src.text.phrase_cues import extract_text_cues


def test_extract_text_cues_matches_literals_and_regex_like_terms() -> None:
    cues = extract_text_cues(
        "Why is BTC up today?",
        ("today", "why is .+ up", "current price"),
    )

    assert cues["has_text_cue"] is True
    assert cues["matched_cues"] == ("today", "why is .+ up")
    assert cues["matched_count"] == 2


def test_extract_text_cues_ignores_blank_input_and_no_matches() -> None:
    assert extract_text_cues("", ("today", "latest")) == {
        "has_text_cue": False,
        "matched_cues": (),
        "matched_count": 0,
    }
    assert extract_text_cues("plain conversation", ("today", "current price")) == {
        "has_text_cue": False,
        "matched_cues": (),
        "matched_count": 0,
    }
