from __future__ import annotations

from scripts import build_affidavit_coverage_review as builder
from src.policy.affidavit_extraction_hints import (
    build_candidate_anchors,
    build_provisional_anchor_bundles,
    build_provisional_structured_anchors,
    classify_workload_with_hints,
    extract_extraction_hints,
    recommend_next_action,
)


def test_extract_extraction_hints_collects_temporal_and_event_cues() -> None:
    hints = extract_extraction_hints(
        "On 13 November 2024 [00:01:05 -> 00:02:10] the appeal was dismissed.",
        tokenize=lambda text: text.lower()
        .replace("[", " ")
        .replace("]", " ")
        .replace("->", " ")
        .replace(".", " ")
        .split(),
    )

    assert hints["has_transcript_timestamp_hint"] is True
    assert hints["transcript_timestamp_windows"] == [{"start": "00:01:05", "end": "00:02:10"}]
    assert hints["has_calendar_reference_hint"] is True
    assert "13 November 2024" in hints["calendar_reference_mentions"]
    assert hints["has_procedural_event_cue"] is True
    assert hints["procedural_event_keywords"] == ["appeal", "dismissed"]


def test_build_candidate_anchors_preserves_anchor_packets() -> None:
    anchors = build_candidate_anchors(
        {
            "transcript_timestamp_windows": [{"start": "00:01:05", "end": "00:02:10"}],
            "calendar_reference_mentions": ["13 November 2024"],
            "procedural_event_keywords": ["appeal", "dismissed"],
        }
    )

    assert [anchor["anchor_kind"] for anchor in anchors] == [
        "transcript_timestamp_window",
        "calendar_reference",
        "procedural_event_keywords",
    ]
    assert anchors[2]["anchor_value"] == ["appeal", "dismissed"]


def test_classify_workload_with_hints_promotes_event_date_action() -> None:
    profile = classify_workload_with_hints(
        ["chronology_undated"],
        "missing_review",
        {
            "has_transcript_timestamp_hint": True,
            "has_calendar_reference_hint": False,
            "has_procedural_event_cue": True,
        },
    )

    assert profile["workload_classes"] == ["chronology_gap"]
    assert profile["primary_workload_class"] == "chronology_gap"
    assert profile["recommended_next_action"] == "promote existing event/date cues into structured anchors"


def test_build_provisional_structured_anchors_dedupes_and_ranks() -> None:
    provisional_rows = build_provisional_structured_anchors(
        [
            {
                "source_row_id": "fact:f4",
                "review_status": "missing_review",
                "best_affidavit_proposition_id": "aff-prop:p1-s1",
                "primary_workload_class": "chronology_gap",
                "recommended_next_action": "promote existing temporal cues into structured anchors",
                "best_match_score": 0.62,
                "candidate_anchors": [
                    {"anchor_kind": "calendar_reference", "label": "November 2024", "anchor_value": "November 2024"},
                    {"anchor_kind": "calendar_reference", "label": "November 2024", "anchor_value": "November 2024"},
                    {"anchor_kind": "procedural_event_keywords", "label": "dismissed", "anchor_value": ["dismissed"]},
                ],
            }
        ]
    )

    assert len(provisional_rows) == 2
    assert provisional_rows[0]["anchor_kind"] == "calendar_reference"
    assert provisional_rows[0]["priority_rank"] == 1
    assert provisional_rows[1]["anchor_kind"] == "procedural_event_keywords"


def test_build_provisional_structured_anchors_can_preserve_duplicate_rows() -> None:
    provisional_rows = build_provisional_structured_anchors(
        [
            {
                "source_row_id": "fact:f4",
                "review_status": "missing_review",
                "best_match_score": 0.62,
                "candidate_anchors": [
                    {"anchor_kind": "calendar_reference", "label": "November 2024", "anchor_value": "November 2024"},
                    {"anchor_kind": "calendar_reference", "label": "November 2024", "anchor_value": "November 2024"},
                ],
            }
        ],
        dedupe=False,
    )

    assert len(provisional_rows) == 2
    assert provisional_rows[0]["priority_rank"] == 1
    assert provisional_rows[1]["priority_rank"] == 2


def test_build_provisional_anchor_bundles_groups_ranked_rows() -> None:
    bundles = build_provisional_anchor_bundles(
        [
            {
                "provisional_anchor_id": "fact:f4#anchor:1",
                "source_row_id": "fact:f4",
                "best_affidavit_proposition_id": "aff-prop:p1-s1",
                "primary_workload_class": "chronology_gap",
                "recommended_next_action": "promote existing event/date cues into structured anchors",
                "anchor_kind": "calendar_reference",
                "anchor_label": "November 2024",
                "anchor_value": "November 2024",
                "priority_score": 97,
                "priority_rank": 1,
            },
            {
                "provisional_anchor_id": "fact:f4#anchor:2",
                "source_row_id": "fact:f4",
                "best_affidavit_proposition_id": "aff-prop:p1-s1",
                "primary_workload_class": "chronology_gap",
                "recommended_next_action": "promote existing event/date cues into structured anchors",
                "anchor_kind": "procedural_event_keywords",
                "anchor_label": "dismissed",
                "anchor_value": ["dismissed"],
                "priority_score": 71,
                "priority_rank": 2,
            },
        ]
    )

    assert len(bundles) == 1
    assert bundles[0]["bundle_rank"] == 1
    assert bundles[0]["anchor_count"] == 2
    assert bundles[0]["top_priority_score"] == 97


def test_builder_wrappers_delegate_to_shared_extraction_hint_policy() -> None:
    text = "On 13 November 2024 [00:01:05 -> 00:02:10] the appeal was dismissed."

    assert builder._extract_extraction_hints(text) == extract_extraction_hints(
        text,
        tokenize=builder._tokenize,
        month_pattern=builder._MONTH_PATTERN,
        procedural_event_keywords=frozenset(builder._PROCEDURAL_EVENT_KEYWORDS),
    )
    assert builder._build_candidate_anchors(
        {"calendar_reference_mentions": ["13 November 2024"], "procedural_event_keywords": ["dismissed"]}
    ) == build_candidate_anchors(
        {"calendar_reference_mentions": ["13 November 2024"], "procedural_event_keywords": ["dismissed"]}
    )
    assert recommend_next_action(
        "evidence_gap",
        has_temporal_hint=False,
        has_event_hint=False,
    ) == "operator evidentiary review"
