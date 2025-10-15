from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.text.reading_fatigue import (
    DuplicateDetector,
    Paragraph,
    build_pin_cite_navigator,
    focus_lane,
)


def _paragraph(pid: str, text: str, *, issues=(), factors=(), deadlines=()):
    return Paragraph(
        pid=pid,
        text=text,
        issues=tuple(issues),
        factors=tuple(factors),
        deadlines=tuple(deadlines),
    )


def test_build_pin_cite_navigator_orders_issues_then_factors():
    paragraphs = [
        _paragraph("p1", "Text A", issues=("jurisdiction",)),
        _paragraph("p2", "Text B", issues=("liability",)),
        _paragraph("p3", "Text C", factors=("balance",)),
        _paragraph("p4", "Text D", issues=("jurisdiction",)),
    ]

    entries = build_pin_cite_navigator(paragraphs)

    labels = [entry.label for entry in entries]
    shortcuts = [entry.shortcut for entry in entries]
    assert labels == ["Issue: jurisdiction", "Issue: liability", "Factor: balance"]
    assert shortcuts == ["alt+1", "alt+2", "alt+3"]
    assert entries[0].paragraph_ids == ("p1", "p4")


def test_duplicate_detector_groups_across_drafts():
    draft_one = [
        _paragraph("p1", "The claimant seeks relief under section 12."),
        _paragraph("p2", "Irrelevant aside."),
    ]
    draft_two = [
        _paragraph("p3", "The claimant seeks relief under section 12."),
        _paragraph("p4", "Another point."),
    ]

    detector = DuplicateDetector(threshold=1)
    groups = detector.find_duplicates([draft_one, draft_two])

    assert len(groups) == 1
    group = groups[0]
    assert {hit.paragraph.pid for hit in group.hits} == {"p1", "p3"}


def test_focus_lane_defaults_to_metadata_paragraphs():
    paragraphs = [
        _paragraph("p1", "Intro."),
        _paragraph("p2", "Issue text", issues=("discovery",)),
        _paragraph("p3", "Deadline note", deadlines=("hearing",)),
    ]

    focused = focus_lane(paragraphs)
    assert [p.pid for p in focused] == ["p2", "p3"]


def test_focus_lane_filters_by_explicit_targets():
    paragraphs = [
        _paragraph("p1", "Issue A", issues=("jurisdiction",)),
        _paragraph("p2", "Issue B", issues=("liability",)),
        _paragraph("p3", "Deadline", deadlines=("lodgement",)),
    ]

    focused = focus_lane(paragraphs, focus_issues=["liability"], focus_deadlines=["lodgement"])
    assert [p.pid for p in focused] == ["p2", "p3"]

