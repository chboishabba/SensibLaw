"""Shared affidavit extraction-hint and provisional-anchor helpers."""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping


MONTH_PATTERN = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"

PROCEDURAL_EVENT_KEYWORDS = {
    "adjourn",
    "adjourned",
    "appeal",
    "argued",
    "commenced",
    "consider",
    "decision",
    "dismissed",
    "duty",
    "filed",
    "hearing",
    "judgment",
    "lodged",
    "notice",
    "ordered",
    "proceedings",
    "submissions",
}

DEFAULT_WORKLOAD_CLASS_PRIORITY = [
    "normalization_gap",
    "chronology_gap",
    "event_extraction_gap",
    "review_queue_only",
    "evidence_gap",
]

DEFAULT_ANCHOR_KIND_WEIGHT = {
    "calendar_reference": 30,
    "transcript_timestamp_window": 20,
    "procedural_event_keywords": 10,
}


def extract_extraction_hints(
    text: str,
    *,
    tokenize: Callable[[str], set[str] | frozenset[str] | list[str] | tuple[str, ...]],
    month_pattern: str = MONTH_PATTERN,
    procedural_event_keywords: set[str] | frozenset[str] = frozenset(PROCEDURAL_EVENT_KEYWORDS),
) -> dict[str, Any]:
    transcript_timestamps = re.findall(
        r"\[(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*->\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]",
        text,
    )
    calendar_mentions = re.findall(
        rf"\b(?:\d{{1,2}}\s+{month_pattern}(?:\s+\d{{4}})?|{month_pattern}\s+\d{{4}}|\d{{4}})\b",
        text,
    )
    keyword_hits = sorted({token for token in tokenize(text) if token in procedural_event_keywords})
    return {
        "has_transcript_timestamp_hint": bool(transcript_timestamps),
        "transcript_timestamp_windows": [{"start": start, "end": end} for start, end in transcript_timestamps],
        "has_calendar_reference_hint": bool(calendar_mentions),
        "calendar_reference_mentions": calendar_mentions,
        "has_procedural_event_cue": bool(keyword_hits),
        "procedural_event_keywords": keyword_hits,
    }


def build_candidate_anchors(extraction_hints: Mapping[str, Any]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    transcript_windows = extraction_hints.get("transcript_timestamp_windows", [])
    if isinstance(transcript_windows, list):
        for window in transcript_windows:
            if not isinstance(window, Mapping):
                continue
            start = str(window.get("start") or "").strip()
            end = str(window.get("end") or "").strip()
            if start and end:
                anchors.append(
                    {
                        "anchor_kind": "transcript_timestamp_window",
                        "label": f"{start} -> {end}",
                        "anchor_value": {"start": start, "end": end},
                    }
                )
    calendar_mentions = extraction_hints.get("calendar_reference_mentions", [])
    if isinstance(calendar_mentions, list):
        for mention in calendar_mentions:
            value = str(mention).strip()
            if value:
                anchors.append(
                    {
                        "anchor_kind": "calendar_reference",
                        "label": value,
                        "anchor_value": value,
                    }
                )
    event_keywords = extraction_hints.get("procedural_event_keywords", [])
    if isinstance(event_keywords, list) and event_keywords:
        cleaned_keywords = [str(keyword).strip() for keyword in event_keywords if str(keyword).strip()]
        anchors.append(
            {
                "anchor_kind": "procedural_event_keywords",
                "label": ", ".join(cleaned_keywords),
                "anchor_value": cleaned_keywords,
            }
        )
    return anchors


def recommend_next_action(
    primary_workload_class: str | None,
    *,
    has_temporal_hint: bool,
    has_event_hint: bool,
) -> str | None:
    if primary_workload_class == "chronology_gap" and has_temporal_hint and has_event_hint:
        return "promote existing event/date cues into structured anchors"
    if primary_workload_class == "chronology_gap" and has_temporal_hint:
        return "promote existing temporal cues into structured anchors"
    if primary_workload_class == "chronology_gap":
        return "extract structured event/date support"
    if primary_workload_class == "event_extraction_gap" and has_event_hint:
        return "promote existing event cues into structured events"
    if primary_workload_class == "event_extraction_gap":
        return "extract structured event/date support"
    if primary_workload_class == "normalization_gap":
        return "normalize transcript/source wording"
    if primary_workload_class == "review_queue_only":
        return "advance review queue triage"
    if primary_workload_class == "evidence_gap":
        return "operator evidentiary review"
    return None


def classify_workload_with_hints(
    reason_codes: list[str],
    review_status: str,
    extraction_hints: Mapping[str, Any],
    *,
    workload_class_priority: list[str] | tuple[str, ...] = tuple(DEFAULT_WORKLOAD_CLASS_PRIORITY),
) -> dict[str, Any]:
    normalized_codes = {str(code).strip() for code in reason_codes if str(code).strip()}
    workload_classes: set[str] = set()

    if "review_queue" in normalized_codes and len(normalized_codes) == 1:
        workload_classes.add("review_queue_only")
    if "unreviewed" in normalized_codes and normalized_codes <= {"unreviewed"}:
        workload_classes.add("review_queue_only")
    if normalized_codes & {"chronology_undated", "missing_date", "contradictory_chronology"}:
        workload_classes.add("chronology_gap")
    if normalized_codes & {"event_missing"}:
        workload_classes.add("event_extraction_gap")
    if normalized_codes & {"statement_only_fact", "source_conflict"}:
        workload_classes.add("evidence_gap")

    if review_status == "missing_review" and not workload_classes:
        workload_classes.add("review_queue_only")

    ordered_classes = [name for name in workload_class_priority if name in workload_classes]
    primary_class = ordered_classes[0] if ordered_classes else None
    has_temporal_hint = bool(extraction_hints.get("has_transcript_timestamp_hint")) or bool(
        extraction_hints.get("has_calendar_reference_hint")
    )
    has_event_hint = bool(extraction_hints.get("has_procedural_event_cue"))
    return {
        "workload_classes": ordered_classes,
        "primary_workload_class": primary_class,
        "recommended_next_action": recommend_next_action(
            primary_class,
            has_temporal_hint=has_temporal_hint,
            has_event_hint=has_event_hint,
        ),
    }


def build_provisional_structured_anchors(
    source_review_rows: list[dict[str, Any]],
    *,
    anchor_kind_weight: Mapping[str, int] = DEFAULT_ANCHOR_KIND_WEIGHT,
    dedupe: bool = True,
) -> list[dict[str, Any]]:
    provisional_rows: list[dict[str, Any]] = []
    for row in source_review_rows:
        if row.get("review_status") != "missing_review":
            continue
        candidate_anchors = row.get("candidate_anchors", [])
        if not isinstance(candidate_anchors, list):
            continue
        for anchor_index, anchor in enumerate(candidate_anchors, start=1):
            if not isinstance(anchor, Mapping):
                continue
            anchor_kind = str(anchor.get("anchor_kind") or "").strip()
            if not anchor_kind:
                continue
            anchor_label = str(anchor.get("label") or "").strip()
            dedupe_key = f"{row['source_row_id']}::{anchor_kind}::{anchor_label}"
            priority_score = anchor_kind_weight.get(anchor_kind, 0) + int(
                round(float(row.get("best_match_score") or 0.0) * 100)
            )
            if row.get("best_affidavit_proposition_id"):
                priority_score += 5
            provisional_rows.append(
                {
                    "provisional_anchor_id": f"{row['source_row_id']}#anchor:{anchor_index}",
                    "source_row_id": row["source_row_id"],
                    "best_affidavit_proposition_id": row.get("best_affidavit_proposition_id"),
                    "primary_workload_class": row.get("primary_workload_class"),
                    "recommended_next_action": row.get("recommended_next_action"),
                    "anchor_kind": anchor_kind,
                    "anchor_label": anchor.get("label"),
                    "anchor_value": anchor.get("anchor_value"),
                    "dedupe_key": dedupe_key,
                    "priority_score": priority_score,
                    "review_disposition": "provisional_anchor_candidate",
                }
            )
    if dedupe:
        deduped_rows: dict[str, dict[str, Any]] = {}
        for row in provisional_rows:
            existing = deduped_rows.get(row["dedupe_key"])
            if existing is None or int(row["priority_score"]) > int(existing["priority_score"]):
                deduped_rows[row["dedupe_key"]] = row
        ranked_rows = list(deduped_rows.values())
    else:
        ranked_rows = list(provisional_rows)
    ranked_rows.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            str(row.get("source_row_id") or ""),
            str(row.get("provisional_anchor_id") or ""),
        )
    )
    for rank, row in enumerate(ranked_rows, start=1):
        row["priority_rank"] = rank
    return ranked_rows


def build_provisional_anchor_bundles(provisional_structured_anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bundles_by_source_row: dict[str, dict[str, Any]] = {}
    for row in provisional_structured_anchors:
        source_row_id = str(row.get("source_row_id") or "").strip()
        if not source_row_id:
            continue
        bundle = bundles_by_source_row.setdefault(
            source_row_id,
            {
                "source_row_id": source_row_id,
                "best_affidavit_proposition_id": row.get("best_affidavit_proposition_id"),
                "primary_workload_class": row.get("primary_workload_class"),
                "recommended_next_action": row.get("recommended_next_action"),
                "top_priority_score": int(row.get("priority_score") or 0),
                "top_priority_rank": int(row.get("priority_rank") or 0),
                "anchor_rows": [],
            },
        )
        bundle["anchor_rows"].append(row)
        if int(row.get("priority_score") or 0) > int(bundle["top_priority_score"]):
            bundle["top_priority_score"] = int(row.get("priority_score") or 0)
            bundle["top_priority_rank"] = int(row.get("priority_rank") or 0)
            bundle["best_affidavit_proposition_id"] = row.get("best_affidavit_proposition_id")
            bundle["primary_workload_class"] = row.get("primary_workload_class")
            bundle["recommended_next_action"] = row.get("recommended_next_action")
    bundles = list(bundles_by_source_row.values())
    for bundle in bundles:
        bundle["anchor_rows"].sort(
            key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("provisional_anchor_id") or ""))
        )
        bundle["anchor_count"] = len(bundle["anchor_rows"])
    bundles.sort(key=lambda bundle: (-int(bundle.get("top_priority_score") or 0), str(bundle.get("source_row_id") or "")))
    for rank, bundle in enumerate(bundles, start=1):
        bundle["bundle_rank"] = rank
    return bundles


__all__ = [
    "DEFAULT_ANCHOR_KIND_WEIGHT",
    "DEFAULT_WORKLOAD_CLASS_PRIORITY",
    "MONTH_PATTERN",
    "PROCEDURAL_EVENT_KEYWORDS",
    "build_candidate_anchors",
    "build_provisional_anchor_bundles",
    "build_provisional_structured_anchors",
    "classify_workload_with_hints",
    "extract_extraction_hints",
    "recommend_next_action",
]
