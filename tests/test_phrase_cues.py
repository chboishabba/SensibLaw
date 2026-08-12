from __future__ import annotations

import pytest

from src.text.phrase_cues import (
    compile_numeric_cues,
    extract_numeric_cues,
    extract_text_cues,
)


def test_literal_boundary_cues_match_without_regex() -> None:
    cues = extract_text_cues(
        "Why is BTC up today?",
        ("today", "current price"),
    )
    assert cues == {
        "has_text_cue": True,
        "matched_cues": ("today",),
        "matched_count": 1,
    }


def test_regex_like_semantic_cues_are_sin_binned() -> None:
    with pytest.raises(ValueError, match="regex-like semantic cues"):
        extract_text_cues("Why is BTC up today?", ("why is .+ up",))


def test_numeric_cues_match_over_symbol_ids_with_linear_plus_matches_receipt() -> None:
    # 10 20 30 = "why is up" in an already-tokenised numeric vocabulary.
    automaton = compile_numeric_cues({1: (10, 20), 2: (20, 30), 3: (10, 20, 30)})
    result = extract_numeric_cues((10, 20, 30), automaton)
    assert [(match.pattern_id, match.end_ordinal) for match in result.matches] == [
        (1, 1),
        (3, 2),
        (2, 2),
    ]
    assert result.receipt.input_symbols == 3
    assert result.receipt.match_count == 3
    assert result.receipt.work_units == 6
    result.receipt.assert_within_contract()


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
