from __future__ import annotations

from src.text.sentences import build_canonical_sentence_units


def test_build_canonical_sentence_units_marks_cross_page_continuation() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Facts",
            "text": "The Court held that",
        },
        {
            "page": 2,
            "heading": "Facts",
            "text": "the appellant succeeded on the first ground.",
        },
    ]

    units = build_canonical_sentence_units(pages)

    assert len(units) == 2
    assert units[0].boundary_state.page == 1
    assert units[0].boundary_state.continues_to_next_page is True
    assert units[0].boundary_state.continues_from_previous_page is False
    assert units[1].boundary_state.page == 2
    assert units[1].boundary_state.continues_from_previous_page is True
    assert units[1].boundary_state.continues_to_next_page is False


def test_build_canonical_sentence_units_tracks_repeated_heading_state() -> None:
    pages = [
        {"page": 1, "heading": "Findings", "text": "The Court accepted the evidence."},
        {"page": 2, "heading": "Findings", "text": "The respondent admitted the loss."},
        {"page": 3, "heading": "Orders", "text": "Appeal allowed."},
    ]

    units = build_canonical_sentence_units(pages)

    assert units[0].boundary_state.repeated_heading_with_next is True
    assert units[1].boundary_state.repeated_heading_with_previous is True
    assert units[1].boundary_state.repeated_heading_with_next is False
    assert units[2].boundary_state.repeated_heading_with_previous is False


def test_build_canonical_sentence_units_uses_sentence_local_spans() -> None:
    pages = [
        {
            "page": 7,
            "heading": "Reasons",
            "text": "First sentence. Second sentence.",
        }
    ]

    units = build_canonical_sentence_units(pages)

    assert [unit.sentence.text for unit in units] == [
        "First sentence.",
        "Second sentence.",
    ]
    assert units[0].sentence.start_char == 0
    assert units[0].sentence.end_char <= units[1].sentence.start_char
    assert all(unit.boundary_state.page == 7 for unit in units)


def test_build_canonical_sentence_units_does_not_mark_closed_page_boundary_as_continuation() -> None:
    pages = [
        {
            "page": 1,
            "heading": "Facts",
            "text": "The Court held that the first ground failed.",
        },
        {
            "page": 2,
            "heading": "Facts",
            "text": "The appellant then raised a second ground.",
        },
    ]

    units = build_canonical_sentence_units(pages)

    assert len(units) == 2
    assert units[0].boundary_state.continues_to_next_page is False
    assert units[1].boundary_state.continues_from_previous_page is False
    assert units[0].boundary_state.repeated_heading_with_next is True
    assert units[1].boundary_state.repeated_heading_with_previous is True


def test_canonical_sentence_unit_payload_is_native_and_fragment_free() -> None:
    pages = [
        {
            "page": 5,
            "heading": "Reasons",
            "text": "The Court held that",
        },
        {
            "page": 6,
            "heading": "Reasons",
            "text": "the appeal should be dismissed.",
        },
    ]

    unit = build_canonical_sentence_units(pages)[0]
    payload = unit.to_dict()

    assert payload == {
        "sentence": {
            "text": "The Court held that",
            "start_char": 0,
            "end_char": len("The Court held that"),
            "index": 0,
        },
        "boundary_state": {
            "page": 5,
            "continues_from_previous_page": False,
            "continues_to_next_page": True,
            "repeated_heading_with_previous": False,
            "repeated_heading_with_next": True,
        },
    }
