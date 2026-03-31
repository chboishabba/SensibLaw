from __future__ import annotations

from src.policy.affidavit_reconciliation_text import (
    group_contested_response_units,
    is_duplicate_affidavit_unit,
    strip_enumeration_prefix,
)
from src.reporting.structure_report import TextUnit


def test_strip_enumeration_prefix_handles_nested_numbering() -> None:
    assert strip_enumeration_prefix("  2.1) The respondent cut off my internet") == (
        "The respondent cut off my internet"
    )


def test_is_duplicate_affidavit_unit_matches_numbered_heading() -> None:
    affidavit_text = (
        "The respondent cut off my internet in November 2024.\n"
        "The respondent pushed me on the back deck.\n"
    )

    assert is_duplicate_affidavit_unit(
        "1. The respondent cut off my internet in November 2024.",
        affidavit_text,
    )
    assert not is_duplicate_affidavit_unit(
        "1. The respondent later sent a follow-up email.",
        affidavit_text,
    )


def test_group_contested_response_units_blocks_duplicate_headings() -> None:
    affidavit_text = (
        "The respondent cut off my internet in November 2024.\n"
        "The respondent pushed me on the back deck.\n"
    )
    response_units = [
        TextUnit(unit_id="u1", source_id="doc", source_type="google_doc", text="Summary of Response"),
        TextUnit(
            unit_id="u2",
            source_id="doc",
            source_type="google_doc",
            text="1. The respondent cut off my internet in November 2024.",
        ),
        TextUnit(
            unit_id="u3",
            source_id="doc",
            source_type="google_doc",
            text="I cut off the internet because the router outage escalated.",
        ),
        TextUnit(
            unit_id="u4",
            source_id="doc",
            source_type="google_doc",
            text="2. The respondent pushed me on the back deck.",
        ),
        TextUnit(
            unit_id="u5",
            source_id="doc",
            source_type="google_doc",
            text="I dispute the characterization of the deck incident.",
        ),
    ]

    grouped = group_contested_response_units(response_units, affidavit_text)

    assert [unit.unit_id for unit in grouped] == ["u1", "u2:block", "u4:block"]
    assert grouped[1].text == (
        "1. The respondent cut off my internet in November 2024.\n"
        "I cut off the internet because the router outage escalated."
    )
    assert grouped[2].text == (
        "2. The respondent pushed me on the back deck.\n"
        "I dispute the characterization of the deck incident."
    )
