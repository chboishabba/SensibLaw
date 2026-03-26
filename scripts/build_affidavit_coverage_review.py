#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.review_geometry_profiles import get_normalized_profile
    from scripts.review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )
except (ModuleNotFoundError, ImportError):
    from review_geometry_profiles import get_normalized_profile
    from review_geometry_normalization import (
        compute_normalized_metrics_from_profile,
        render_normalized_metrics_markdown,
    )

try:
    from src.rules.dependencies import get_dependencies as _get_dependencies
except Exception:  # pragma: no cover - optional structural parser path
    _get_dependencies = None

try:
    from src.policy.semantic_promotion import build_contested_claim_candidate, promote_contested_claim
except Exception:  # pragma: no cover - import path fallback for direct script use
    from policy.semantic_promotion import build_contested_claim_candidate, promote_contested_claim


ARTIFACT_VERSION = "affidavit_coverage_review_v1"
_PARTIAL_MATCH_THRESHOLD = 0.3
_COVERED_MATCH_THRESHOLD = 0.6

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
}

_TOKEN_NORMALIZATION = {
    "emphasise": "emphasize",
    "emphasised": "emphasized",
    "emphasises": "emphasizes",
    "emphasising": "emphasizing",
    "organisation": "organization",
    "organisations": "organizations",
}

_WORKLOAD_CLASS_PRIORITY = [
    "normalization_gap",
    "chronology_gap",
    "event_extraction_gap",
    "review_queue_only",
    "evidence_gap",
]

_MONTH_PATTERN = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_PROCEDURAL_EVENT_KEYWORDS = {
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

_CHARACTERIZATION_TERMS = {
    "abusive",
    "coercive",
    "controlling",
    "intimidating",
    "unsafe",
    "privacy",
    "distressing",
    "undermine",
    "improper",
}

_LEXICAL_HEURISTIC_HINT_RULES: dict[str, tuple[dict[str, Any], ...]] = {
    "justification": (
        {
            "rule_id": "justification.consent",
            "label": "consent",
            "patterns": (
                r"\bconsent\b",
                r"\bwith consent\b",
                r"\bknowledge and consent\b",
                r"\bpermission\b",
            ),
        },
        {
            "rule_id": "justification.authority_or_necessity",
            "label": "authority_or_necessity",
            "patterns": (
                r"\bepoa\b",
                r"\bduty\b",
                r"\bduties\b",
                r"\bauthority\b",
                r"\blegal matters\b",
                r"\bcare\b",
            ),
        },
        {
            "rule_id": "justification.scope_limitation",
            "label": "scope_limitation",
            "patterns": (
                r"\bspecific purposes\b",
                r"\bonly to\b",
                r"\blimited\b",
                r"\bminimally\b",
                r"\bno further than necessary\b",
            ),
        },
    ),
}

def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _tokenize(text: str) -> set[str]:
    tokens = {
        _TOKEN_NORMALIZATION.get(token, token)
        for token in re.findall(r"[A-Za-z0-9']+", text.casefold())
        if len(token) >= 2 and token not in _STOPWORDS
    }
    return tokens


def _apply_lexical_heuristic_group(text: str, group: str) -> dict[str, list[dict[str, Any]]]:
    matches: dict[str, list[dict[str, Any]]] = {}
    for rule in _LEXICAL_HEURISTIC_HINT_RULES.get(group, ()):
        label = str(rule.get("label") or "").strip()
        rule_id = str(rule.get("rule_id") or "").strip()
        if not label or not rule_id:
            continue
        rule_matches: list[dict[str, Any]] = []
        for pattern in rule.get("patterns", ()):
            compiled = re.compile(str(pattern), re.IGNORECASE)
            for match in compiled.finditer(text):
                rule_matches.append(
                    {
                        "rule_id": rule_id,
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        if rule_matches:
            matches[label] = rule_matches
    return matches


_HEDGE_VERBS = {"feel", "believe", "think", "recall"}


def _analyze_structural_sentence(text: str) -> dict[str, Any]:
    if _get_dependencies is None:
        return {}
    try:
        sentences = _get_dependencies(text)
    except Exception:
        return {}
    if not sentences:
        return {}
    first = sentences[0]
    candidates = getattr(first, "candidates", {}) or {}
    subjects = list(candidates.get("nsubj", [])) + list(candidates.get("nsubjpass", []))
    verbs = list(candidates.get("verb", []))
    negations = list(candidates.get("neg", []))
    subject_texts = [str(getattr(item, "text", "") or "").strip() for item in subjects if str(getattr(item, "text", "") or "").strip()]
    verb_lemmas = [str(getattr(item, "lemma", "") or getattr(item, "text", "") or "").strip().lower() for item in verbs]
    return {
        "subject_texts": subject_texts,
        "verb_lemmas": verb_lemmas,
        "has_negation": bool(negations),
        "has_first_person_subject": any(text.casefold() == "i" for text in subject_texts),
        "has_hedge_verb": any(lemma in _HEDGE_VERBS for lemma in verb_lemmas),
    }


def _split_source_text_segments(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
    return parts or [compact]


def _split_affidavit_text(text: str) -> list[dict[str, Any]]:
    propositions: list[dict[str, Any]] = []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        sentence_parts = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
            if sentence.strip()
        ]
        if not sentence_parts:
            sentence_parts = [paragraph]
        for sentence_index, sentence in enumerate(sentence_parts, start=1):
            proposition_id = f"aff-prop:p{paragraph_index}-s{sentence_index}"
            propositions.append(
                {
                    "proposition_id": proposition_id,
                    "paragraph_id": f"p{paragraph_index}",
                    "paragraph_order": paragraph_index,
                    "sentence_order": sentence_index,
                    "text": sentence,
                    "tokens": sorted(_tokenize(sentence)),
                }
            )
    return propositions


def _reason_codes(review_row: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(review_row, Mapping):
        return []
    raw = review_row.get("reason_codes", [])
    if not isinstance(raw, list):
        return []
    return [str(value) for value in raw if str(value).strip()]


def _is_contested(review_row: Mapping[str, Any] | None, candidate_status: str) -> bool:
    if candidate_status == "contested":
        return True
    if not isinstance(review_row, Mapping):
        return False
    if int(review_row.get("contestation_count") or 0) > 0:
        return True
    return any(code in {"source_conflict", "contradictory_chronology"} for code in _reason_codes(review_row))


def _is_abstained(review_row: Mapping[str, Any] | None, candidate_status: str) -> bool:
    if candidate_status == "abstained":
        return True
    if not isinstance(review_row, Mapping):
        return False
    if str(review_row.get("latest_review_status") or "").strip() == "abstained":
        return True
    return False


def _classify_workload(reason_codes: list[str], review_status: str) -> dict[str, Any]:
    return _classify_workload_with_hints(reason_codes, review_status, {})


def _extract_extraction_hints(text: str) -> dict[str, Any]:
    transcript_timestamps = re.findall(
        r"\[(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*->\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]",
        text,
    )
    calendar_mentions = re.findall(
        rf"\b(?:\d{{1,2}}\s+{_MONTH_PATTERN}(?:\s+\d{{4}})?|{_MONTH_PATTERN}\s+\d{{4}}|\d{{4}})\b",
        text,
    )
    keyword_hits = sorted({token for token in _tokenize(text) if token in _PROCEDURAL_EVENT_KEYWORDS})
    return {
        "has_transcript_timestamp_hint": bool(transcript_timestamps),
        "transcript_timestamp_windows": [
            {"start": start, "end": end}
            for start, end in transcript_timestamps
        ],
        "has_calendar_reference_hint": bool(calendar_mentions),
        "calendar_reference_mentions": calendar_mentions,
        "has_procedural_event_cue": bool(keyword_hits),
        "procedural_event_keywords": keyword_hits,
    }


def _build_candidate_anchors(extraction_hints: Mapping[str, Any]) -> list[dict[str, Any]]:
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
        anchors.append(
            {
                "anchor_kind": "procedural_event_keywords",
                "label": ", ".join(str(keyword).strip() for keyword in event_keywords if str(keyword).strip()),
                "anchor_value": [str(keyword).strip() for keyword in event_keywords if str(keyword).strip()],
            }
        )
    return anchors


def _build_provisional_structured_anchors(source_review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provisional_rows: list[dict[str, Any]] = []
    anchor_kind_weight = {
        "calendar_reference": 30,
        "transcript_timestamp_window": 20,
        "procedural_event_keywords": 10,
    }
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
            priority_score = (
                anchor_kind_weight.get(anchor_kind, 0)
                + int(round(float(row.get("best_match_score") or 0.0) * 100))
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
    deduped_rows: dict[str, dict[str, Any]] = {}
    for row in provisional_rows:
        existing = deduped_rows.get(row["dedupe_key"])
        if existing is None or int(row["priority_score"]) > int(existing["priority_score"]):
            deduped_rows[row["dedupe_key"]] = row
    ranked_rows = list(deduped_rows.values())
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


def _build_provisional_anchor_bundles(provisional_structured_anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            key=lambda row: (
                -int(row.get("priority_score") or 0),
                str(row.get("provisional_anchor_id") or ""),
            )
        )
        bundle["anchor_count"] = len(bundle["anchor_rows"])
    bundles.sort(
        key=lambda bundle: (
            -int(bundle.get("top_priority_score") or 0),
            str(bundle.get("source_row_id") or ""),
        )
    )
    for rank, bundle in enumerate(bundles, start=1):
        bundle["bundle_rank"] = rank
    return bundles


def _classify_workload_with_hints(reason_codes: list[str], review_status: str, extraction_hints: Mapping[str, Any]) -> dict[str, Any]:
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

    ordered_classes = [name for name in _WORKLOAD_CLASS_PRIORITY if name in workload_classes]
    primary_class = ordered_classes[0] if ordered_classes else None
    has_temporal_hint = bool(extraction_hints.get("has_transcript_timestamp_hint")) or bool(extraction_hints.get("has_calendar_reference_hint"))
    has_event_hint = bool(extraction_hints.get("has_procedural_event_cue"))
    if primary_class == "chronology_gap" and has_temporal_hint and has_event_hint:
        recommended_action = "promote existing event/date cues into structured anchors"
    elif primary_class == "chronology_gap" and has_temporal_hint:
        recommended_action = "promote existing temporal cues into structured anchors"
    elif primary_class == "chronology_gap":
        recommended_action = "extract structured event/date support"
    elif primary_class == "event_extraction_gap" and has_event_hint:
        recommended_action = "promote existing event cues into structured events"
    elif primary_class == "event_extraction_gap":
        recommended_action = "extract structured event/date support"
    elif primary_class == "normalization_gap":
        recommended_action = "normalize transcript/source wording"
    elif primary_class == "review_queue_only":
        recommended_action = "advance review queue triage"
    elif primary_class == "evidence_gap":
        recommended_action = "operator evidentiary review"
    else:
        recommended_action = None

    return {
        "workload_classes": ordered_classes,
        "primary_workload_class": primary_class,
        "recommended_next_action": recommended_action,
    }


def _extract_source_rows(source_payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    version = str(source_payload.get("version") or "").strip()
    if not version and isinstance(source_payload.get("run"), Mapping):
        version = str((source_payload.get("run") or {}).get("contract_version") or "").strip()
    fixture_kind = str(source_payload.get("fixture_kind") or "").strip()
    comparison_mode = str((source_payload.get("run") or {}).get("comparison_mode") or "").strip() if isinstance(source_payload.get("run"), Mapping) else ""

    if version == "fact.intake.bundle.v1":
        source_lookup = {
            str(row.get("source_id") or "").strip(): row
            for row in source_payload.get("sources", [])
            if isinstance(row, Mapping) and str(row.get("source_id") or "").strip()
        }
        excerpt_lookup = {
            str(row.get("excerpt_id") or "").strip(): row
            for row in source_payload.get("excerpts", [])
            if isinstance(row, Mapping) and str(row.get("excerpt_id") or "").strip()
        }
        statement_lookup = {
            str(row.get("statement_id") or "").strip(): row
            for row in source_payload.get("statements", [])
            if isinstance(row, Mapping) and str(row.get("statement_id") or "").strip()
        }
        rows: list[dict[str, Any]] = []
        for fact in source_payload.get("fact_candidates", []):
            if not isinstance(fact, Mapping):
                continue
            fact_id = str(fact.get("fact_id") or "").strip()
            fact_text = str(fact.get("fact_text") or "").strip()
            if not fact_id or not fact_text:
                continue
            statement_ids = list(fact.get("statement_ids", [])) if isinstance(fact.get("statement_ids"), list) else []
            excerpt_ids = sorted(
                {
                    str(statement_lookup.get(statement_id, {}).get("excerpt_id") or "").strip()
                    for statement_id in statement_ids
                    if str(statement_lookup.get(statement_id, {}).get("excerpt_id") or "").strip()
                }
            )
            source_ids = sorted(
                {
                    str(excerpt_lookup.get(excerpt_id, {}).get("source_id") or "").strip()
                    for excerpt_id in excerpt_ids
                    if str(excerpt_lookup.get(excerpt_id, {}).get("source_id") or "").strip()
                }
            )
            rows.append(
                {
                    "source_row_id": fact_id,
                    "source_kind": "fact_intake_fact",
                    "text": fact_text,
                    "tokens": sorted(_tokenize(fact_text)),
                    "candidate_status": str(fact.get("candidate_status") or "candidate").strip() or "candidate",
                    "review_status": None,
                    "reason_codes": [],
                    "is_contested": False,
                    "is_abstained": False,
                    "statement_ids": statement_ids,
                    "excerpt_ids": excerpt_ids,
                    "source_ids": source_ids,
                    "review_row": {},
                    "comparison_mode": comparison_mode,
                }
            )
        return rows, {
            "source_contract": version,
            "source_kind": "fact_intake_bundle",
            "source_label": ((source_payload.get("run") or {}).get("source_label") if isinstance(source_payload.get("run"), Mapping) else None),
            "source_row_count": len(rows),
        }

    if version == "fact.review.bundle.v1":
        review_by_fact_id = {
            str(row.get("fact_id")): row
            for row in source_payload.get("review_queue", [])
            if isinstance(row, Mapping) and str(row.get("fact_id") or "").strip()
        }
        rows: list[dict[str, Any]] = []
        for fact in source_payload.get("facts", []):
            if not isinstance(fact, Mapping):
                continue
            fact_id = str(fact.get("fact_id") or "").strip()
            fact_text = str(fact.get("fact_text") or "").strip()
            if not fact_id or not fact_text:
                continue
            review_row = review_by_fact_id.get(fact_id, {})
            candidate_status = str(fact.get("candidate_status") or "candidate").strip() or "candidate"
            rows.append(
                {
                    "source_row_id": fact_id,
                    "source_kind": "fact_review_fact",
                    "text": fact_text,
                    "tokens": sorted(_tokenize(fact_text)),
                    "candidate_status": candidate_status,
                    "review_status": str(review_row.get("latest_review_status") or "").strip() or None,
                    "reason_codes": _reason_codes(review_row),
                    "is_contested": _is_contested(review_row, candidate_status),
                    "is_abstained": _is_abstained(review_row, candidate_status),
                    "statement_ids": list(fact.get("statement_ids", [])) if isinstance(fact.get("statement_ids"), list) else [],
                    "excerpt_ids": list(fact.get("excerpt_ids", [])) if isinstance(fact.get("excerpt_ids"), list) else [],
                    "source_ids": list(fact.get("source_ids", [])) if isinstance(fact.get("source_ids"), list) else [],
                    "review_row": dict(review_row) if isinstance(review_row, Mapping) else {},
                    "comparison_mode": comparison_mode,
                }
            )
        return rows, {
            "source_contract": version,
            "source_kind": "fact_review_bundle",
            "source_label": ((source_payload.get("run") or {}).get("source_label") if isinstance(source_payload.get("run"), Mapping) else None),
            "source_row_count": len(rows),
        }

    if fixture_kind == "au_public_handoff" or version == "au_public_handoff_v1":
        rows = []
        for fact in source_payload.get("selected_facts", []):
            if not isinstance(fact, Mapping):
                continue
            fact_id = str(fact.get("fact_id") or "").strip()
            fact_text = str(fact.get("fact_text") or "").strip()
            if not fact_id or not fact_text:
                continue
            review_status = str(fact.get("review_status") or "").strip() or None
            rows.append(
                {
                    "source_row_id": fact_id,
                    "source_kind": "au_checked_handoff_fact",
                    "text": fact_text,
                    "tokens": sorted(_tokenize(fact_text)),
                    "candidate_status": "candidate",
                    "review_status": review_status,
                    "reason_codes": ["review_queue"] if review_status == "review_queue" else [],
                    "is_contested": False,
                    "is_abstained": False,
                    "statement_ids": [],
                    "excerpt_ids": [],
                    "source_ids": [],
                    "review_row": {},
                    "comparison_mode": comparison_mode,
                }
            )
        return rows, {
            "source_contract": version or fixture_kind,
            "source_kind": "au_checked_handoff_slice",
            "source_label": ((source_payload.get("run") or {}).get("source_label") if isinstance(source_payload.get("run"), Mapping) else None),
            "source_row_count": len(rows),
        }

    if fixture_kind == "au_real_transcript_dense_substrate":
        overlay = source_payload.get("overlay_projection") if isinstance(source_payload.get("overlay_projection"), Mapping) else {}
        rows = []
        for fact in overlay.get("selected_facts", []):
            if not isinstance(fact, Mapping):
                continue
            fact_id = str(fact.get("fact_id") or "").strip()
            fact_text = str(fact.get("fact_text") or "").strip()
            if not fact_id or not fact_text:
                continue
            review_row = fact.get("review_row") if isinstance(fact.get("review_row"), Mapping) else {}
            candidate_status = str(fact.get("candidate_status") or "candidate").strip() or "candidate"
            rows.append(
                {
                    "source_row_id": fact_id,
                    "source_kind": "au_dense_overlay_fact",
                    "text": fact_text,
                    "tokens": sorted(_tokenize(fact_text)),
                    "candidate_status": candidate_status,
                    "review_status": str(review_row.get("latest_review_status") or "").strip() or None,
                    "reason_codes": _reason_codes(review_row),
                    "is_contested": _is_contested(review_row, candidate_status),
                    "is_abstained": _is_abstained(review_row, candidate_status),
                    "statement_ids": list(fact.get("statement_ids", [])) if isinstance(fact.get("statement_ids"), list) else [],
                    "excerpt_ids": list(fact.get("excerpt_ids", [])) if isinstance(fact.get("excerpt_ids"), list) else [],
                    "source_ids": list(fact.get("source_ids", [])) if isinstance(fact.get("source_ids"), list) else [],
                    "review_row": dict(review_row),
                    "comparison_mode": comparison_mode,
                }
            )
        return rows, {
            "source_contract": version or fixture_kind,
            "source_kind": "au_dense_overlay_slice",
            "source_label": ((source_payload.get("run") or {}).get("source_label") if isinstance(source_payload.get("run"), Mapping) else None),
            "source_row_count": len(rows),
        }

    raise ValueError(
        "Unsupported source payload. Expected fact.intake.bundle.v1, fact.review.bundle.v1, au_public_handoff_v1-style slice, or au_real_transcript_dense_substrate."
    )


def _similarity_score(left_tokens: Iterable[str], right_tokens: Iterable[str]) -> float:
    left = set(left_tokens)
    right = set(right_tokens)
    if not left or not right:
        return 0.0
    shared = left & right
    if not shared:
        return 0.0
    return round((2.0 * len(shared)) / (len(left) + len(right)), 6)


def _classify_argumentative_role(
    proposition_text: str,
    excerpt_text: str,
    row_text: str,
    *,
    use_row_fallback: bool = True,
) -> dict[str, Any]:
    excerpt = excerpt_text.strip()
    structural = _analyze_structural_sentence(excerpt)
    proposition_tokens = _tokenize(proposition_text)
    excerpt_tokens = _tokenize(excerpt)
    shared_ratio = 0.0
    substantive_shared_tokens = proposition_tokens & excerpt_tokens
    if proposition_tokens:
        shared_ratio = len(substantive_shared_tokens) / len(proposition_tokens)
    if structural.get("has_negation") and structural.get("has_hedge_verb"):
        return {
            "response_role": "hedged_denial",
            "response_cues": ["structural:negated_hedge"],
        }
    if structural.get("has_negation"):
        return {
            "response_role": "dispute",
            "response_cues": ["structural:negation"],
        }
    if structural.get("has_first_person_subject") and substantive_shared_tokens and not use_row_fallback:
        return {
            "response_role": "admission",
            "response_cues": ["structural:first_person_subject"],
        }
    if not substantive_shared_tokens:
        return {
            "response_role": "non_response",
            "response_cues": [],
        }
    if shared_ratio >= 0.5:
        role = "restatement_only"
    else:
        role = "procedural_frame"
    return {
        "response_role": role,
        "response_cues": [],
    }


def _is_duplicate_response_excerpt(proposition_text: str, excerpt_text: str) -> bool:
    proposition_tokens = _tokenize(proposition_text)
    excerpt_tokens = _tokenize(excerpt_text)
    if not proposition_tokens or not excerpt_tokens:
        return False
    shared_ratio = len(proposition_tokens & excerpt_tokens) / len(proposition_tokens)
    return shared_ratio >= 0.85


def _infer_response_packet(
    *,
    proposition_text: str,
    best_match_excerpt: str,
    duplicate_match_excerpt: str | None,
    response_role: str | None,
    response_cues: list[str] | None,
    coverage_status: str,
) -> dict[str, Any]:
    role = str(response_role or "").strip()
    excerpt = str(best_match_excerpt or "").strip()
    duplicate_excerpt = str(duplicate_match_excerpt or "").strip() or None
    proposition_lower = proposition_text.casefold()
    excerpt_lower = excerpt.casefold()
    response_acts: list[str] = []
    legal_significance_signals: list[str] = []

    if duplicate_excerpt:
        response_acts.append("repetition_only")
    characterization_overlap = any(term in proposition_lower and term in excerpt_lower for term in _CHARACTERIZATION_TERMS)
    characterization_dispute = characterization_overlap or "characterization" in excerpt_lower
    if role in {"dispute", "hedged_denial"}:
        if characterization_dispute:
            response_acts.append("deny_characterisation")
            legal_significance_signals.append("characterization_dispute")
        else:
            response_acts.append("deny_fact")
            legal_significance_signals.append("factual_denial")
        if role == "hedged_denial":
            response_acts.append("hedged_denial")
            legal_significance_signals.append("hedged_denial_signal")
    elif role == "admission":
        response_acts.append("admit_fact")
        legal_significance_signals.append("factual_admission")
    elif role == "explanation":
        response_acts.append("explain_context")
        legal_significance_signals.append("context_explanation")
    elif role == "support_or_corroboration":
        response_acts.append("corroborate_or_ground")
        legal_significance_signals.append("evidentiary_grounding_signal")
    elif role == "non_response":
        response_acts.append("non_response")
    elif role == "restatement_only":
        response_acts.append("repetition_only")
    elif role == "procedural_frame":
        response_acts.append("procedural_or_nonresponsive_frame")

    justification_matches = _apply_lexical_heuristic_group(excerpt, "justification")
    if justification_matches.get("consent"):
        response_acts.append("justify")
        legal_significance_signals.append("consent_signal")
    if justification_matches.get("authority_or_necessity"):
        legal_significance_signals.append("authority_or_necessity_signal")
    if justification_matches.get("scope_limitation"):
        response_acts.append("scope_limitation")
        legal_significance_signals.append("scope_limitation")

    if coverage_status == "covered" and response_acts and all(act != "repetition_only" for act in response_acts):
        support_status = "substantively_addressed"
    elif coverage_status == "partial" and duplicate_excerpt:
        support_status = "textually_addressed"
    elif coverage_status == "partial" and response_acts:
        support_status = "responsive_but_non_substantive"
    elif coverage_status in {"unsupported_affidavit", "contested_source", "abstained_source"}:
        support_status = "unresolved"
    else:
        support_status = "textually_addressed"

    if "evidentiary_grounding_signal" in legal_significance_signals and support_status in {
        "substantively_addressed",
        "responsive_but_non_substantive",
    }:
        support_status = "evidentially_grounded_response"

    return {
        "response_acts": sorted(dict.fromkeys(response_acts)),
        "legal_significance_signals": sorted(dict.fromkeys(legal_significance_signals)),
        "support_status": support_status,
    }


def _derive_primary_target_component(*, response: Mapping[str, Any], response_acts: list[str]) -> str:
    component_targets = response.get("component_targets") if isinstance(response.get("component_targets"), list) else []
    normalized_targets = [str(target).strip() for target in component_targets if str(target).strip()]
    if "characterization" in normalized_targets and "deny_characterisation" in set(response_acts):
        return "characterization"
    if "time" in normalized_targets:
        return "time"
    if "predicate_text" in normalized_targets:
        return "predicate_text"
    return normalized_targets[0] if normalized_targets else "predicate_text"


def _derive_semantic_basis(
    *,
    response_cues: list[str],
    response: Mapping[str, Any],
    response_component_bindings: list[dict[str, Any]],
    justifications: list[dict[str, Any]],
) -> str:
    if any(str(cue).startswith("structural:") for cue in response_cues):
        return "structural"
    structural_binding_components = {
        str(binding.get("component") or "").strip()
        for binding in response_component_bindings
        if isinstance(binding, Mapping) and str(binding.get("component") or "").strip() in {"characterization", "time"}
    }
    if structural_binding_components and justifications:
        return "mixed"
    if structural_binding_components:
        return "mixed"
    if justifications:
        return "heuristic"
    speech_act = str(response.get("speech_act") or "").strip()
    if speech_act in {"deny", "admit", "explain"}:
        return "heuristic"
    return "heuristic"


def _derive_claim_state(
    *,
    response_acts: list[str],
    legal_significance_signals: list[str],
    support_status: str,
    duplicate_match_excerpt: str | None,
) -> dict[str, str]:
    acts = set(response_acts)
    signals = set(legal_significance_signals)
    has_for = bool(
        {"admit_fact", "corroborate_or_ground"} & acts
        or {"factual_admission", "evidentiary_grounding_signal"} & signals
    )
    has_against = bool(
        {"deny_fact", "deny_characterisation", "hedged_denial"} & acts
        or {"factual_denial", "characterization_dispute", "hedged_denial_signal"} & signals
    )
    if has_for and has_against:
        support_direction = "mixed"
    elif has_for:
        support_direction = "for"
    elif has_against:
        support_direction = "against"
    else:
        support_direction = "none"

    if support_status == "unresolved" and support_direction == "none":
        conflict_state = "unanswered"
    elif support_direction == "mixed":
        conflict_state = "partially_reconciled"
    elif support_direction == "against":
        conflict_state = "disputed"
    elif support_direction == "for":
        conflict_state = "undisputed"
    elif duplicate_match_excerpt:
        conflict_state = "unresolved"
    else:
        conflict_state = "unanswered"

    if support_status == "evidentially_grounded_response":
        evidentiary_state = "supported"
    elif support_status == "substantively_addressed" and support_direction in {"for", "mixed"}:
        evidentiary_state = "weakly_supported"
    elif support_direction == "against":
        evidentiary_state = "unproven"
    elif support_status in {"textually_addressed", "responsive_but_non_substantive", "unresolved"}:
        evidentiary_state = "unproven"
    else:
        evidentiary_state = "unassessed"

    if support_direction == "none" and support_status == "unresolved":
        operational_status = "claim_only"
    elif support_direction == "for" and conflict_state == "undisputed" and evidentiary_state in {"unproven", "weakly_supported"}:
        operational_status = "claim_with_support"
    elif support_direction == "against":
        operational_status = "claim_with_opposition" if conflict_state == "unanswered" else "disputed_claim"
    elif support_direction == "mixed" and conflict_state == "partially_reconciled":
        operational_status = "partially_reconciled_claim"
    elif support_direction == "for" and evidentiary_state in {"supported", "strongly_supported"}:
        operational_status = "resolved_but_unproven"
    else:
        operational_status = "disputed_claim" if conflict_state == "disputed" else "claim_only"

    return {
        "support_direction": support_direction,
        "conflict_state": conflict_state,
        "evidentiary_state": evidentiary_state,
        "operational_status": operational_status,
    }


def _build_zelph_claim_state_fact(
    proposition_id: str,
    best_source_row_id: str | None,
    claim: Mapping[str, Any],
    response: Mapping[str, Any],
    justifications: list[dict[str, Any]],
    claim_state: Mapping[str, Any],
    response_acts: list[str],
    legal_significance_signals: list[str],
    support_status: str,
    coverage_status: str,
    semantic_basis: str,
    promotion: Mapping[str, Any],
) -> dict[str, Any]:
    claim_components = claim.get("components") if isinstance(claim.get("components"), Mapping) else {}
    response_component_targets = response.get("component_targets") if isinstance(response.get("component_targets"), list) else []
    return {
        "fact_id": f"zelph_claim_state:{proposition_id}",
        "fact_kind": "contested_claim_state",
        "proposition_id": proposition_id,
        "best_source_row_id": best_source_row_id,
        "claim_text_span": claim.get("text_span"),
        "claim_actor_span": claim_components.get("actor") if isinstance(claim_components, Mapping) else None,
        "claim_time_spans": claim_components.get("time") if isinstance(claim_components, Mapping) else [],
        "claim_characterization_spans": claim_components.get("characterization") if isinstance(claim_components, Mapping) else [],
        "response_text_span": response.get("text_span"),
        "target_span": response.get("target_span"),
        "duplicate_text_span": response.get("duplicate_text_span"),
        "response_speech_act": response.get("speech_act"),
        "response_polarity": response.get("polarity"),
        "response_modifiers": list(response.get("modifiers") or []),
        "response_component_targets": list(response_component_targets),
        "semantic_basis": semantic_basis,
        "promotion_status": promotion.get("status"),
        "promotion_basis": promotion.get("basis"),
        "promotion_reason": promotion.get("reason"),
        "support_direction": claim_state.get("support_direction"),
        "conflict_state": claim_state.get("conflict_state"),
        "evidentiary_state": claim_state.get("evidentiary_state"),
        "operational_status": claim_state.get("operational_status"),
        "response_acts": list(response_acts),
        "justification_types": sorted(
            {
                str(packet.get("type") or "").strip()
                for packet in justifications
                if isinstance(packet, Mapping) and str(packet.get("type") or "").strip()
            }
        ),
        "justification_bindings": [
            {
                "type": str(packet.get("type") or "").strip(),
                "target_component": str(packet.get("target_component") or "").strip() or "predicate_text",
            }
            for packet in justifications
            if isinstance(packet, Mapping) and str(packet.get("type") or "").strip()
        ],
        "legal_significance_signals": list(legal_significance_signals),
        "support_status": support_status,
        "coverage_status": coverage_status,
    }


def _span_ref(container_text: str, span_text: str) -> dict[str, Any] | None:
    container = str(container_text or "")
    span = str(span_text or "").strip()
    if not span:
        return None
    idx = container.find(span)
    if idx == -1:
        idx = 0
        end = len(span)
    else:
        end = idx + len(span)
    return {
        "text": span,
        "start": idx,
        "end": end,
    }


def _extract_time_spans(text: str) -> list[dict[str, Any]]:
    hints = _extract_extraction_hints(text)
    mentions = hints.get("calendar_reference_mentions", [])
    if not isinstance(mentions, list):
        return []
    spans: list[dict[str, Any]] = []
    for mention in mentions:
        span = _span_ref(text, str(mention))
        if span is not None and span not in spans:
            spans.append(span)
    return spans


def _extract_characterization_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for term in sorted(_CHARACTERIZATION_TERMS):
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            spans.append(
                {
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return spans


def _extract_claim_components(proposition_text: str) -> dict[str, Any]:
    claim_text = str(proposition_text or "").strip()
    predicate_span = _span_ref(claim_text, claim_text)
    actor = None
    structural = _analyze_structural_sentence(claim_text)
    subject_texts = structural.get("subject_texts")
    if isinstance(subject_texts, list):
        for subject_text in subject_texts:
            actor = _span_ref(claim_text, str(subject_text))
            if actor is not None:
                break
    components: dict[str, Any] = {
        "predicate_text": predicate_span,
    }
    if actor is not None:
        components["actor"] = actor
    time_spans = _extract_time_spans(claim_text)
    if time_spans:
        components["time"] = time_spans
    characterization_spans = _extract_characterization_spans(claim_text)
    if characterization_spans:
        components["characterization"] = characterization_spans
    return components


def _build_claim_packet(proposition_text: str) -> dict[str, Any]:
    claim_text = str(proposition_text or "").strip()
    return {
        "text_span": _span_ref(claim_text, claim_text),
        "components": _extract_claim_components(claim_text),
    }


def _build_response_packet(
    *,
    proposition_text: str,
    best_match_excerpt: str,
    duplicate_match_excerpt: str | None,
    response_role: str | None,
    response_acts: list[str],
) -> dict[str, Any]:
    role = str(response_role or "").strip()
    modifiers: list[str] = []
    if role == "dispute":
        speech_act = "deny"
        polarity = "negative"
    elif role == "hedged_denial":
        speech_act = "deny"
        polarity = "negative"
        modifiers.append("hedged")
    elif role == "admission":
        speech_act = "admit"
        polarity = "positive"
    elif role == "explanation":
        speech_act = "explain"
        polarity = "qualified"
    elif role == "support_or_corroboration":
        speech_act = "other"
        polarity = "positive"
    elif role == "non_response":
        speech_act = "other"
        polarity = "neutral"
        modifiers.append("non_responsive")
    elif role == "restatement_only":
        speech_act = "other"
        polarity = "neutral"
        modifiers.append("repetition")
    else:
        speech_act = "other"
        polarity = "neutral"
    if duplicate_match_excerpt:
        modifiers.append("repetition")
    if any(act in {"justify", "scope_limitation"} for act in response_acts):
        modifiers.append("qualified")
    return {
        "speech_act": speech_act,
        "polarity": polarity,
        "target_span": _span_ref(proposition_text, proposition_text),
        "text_span": _span_ref(best_match_excerpt, best_match_excerpt),
        "duplicate_text_span": _span_ref(duplicate_match_excerpt or "", duplicate_match_excerpt or ""),
        "acts": list(response_acts),
        "modifiers": sorted(dict.fromkeys(modifiers)),
    }


def _build_justification_packets(excerpt_text: str) -> list[dict[str, Any]]:
    excerpt = str(excerpt_text or "")
    packets: list[dict[str, Any]] = []
    rule_matches = _apply_lexical_heuristic_group(excerpt, "justification")
    for justification_type, matches in rule_matches.items():
        if not matches:
            continue
        match = matches[0]
        packets.append(
            {
                "type": justification_type,
                "rule_id": match["rule_id"],
                "span": {
                    "text": match["text"],
                    "start": match["start"],
                    "end": match["end"],
                },
                "target_component": "predicate_text",
                "bound_response_span": {
                    "text": match["text"],
                    "start": match["start"],
                    "end": match["end"],
                },
            }
        )
    return packets


def _build_response_component_bindings(
    *,
    claim: Mapping[str, Any],
    response: Mapping[str, Any],
    justifications: list[dict[str, Any]],
    response_acts: list[str],
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    claim_components = claim.get("components") if isinstance(claim.get("components"), Mapping) else {}
    predicate_span = claim_components.get("predicate_text") if isinstance(claim_components, Mapping) else None
    response_span = response.get("text_span") if isinstance(response.get("text_span"), Mapping) else None
    target_span = response.get("target_span") if isinstance(response.get("target_span"), Mapping) else None
    speech_act = str(response.get("speech_act") or "").strip()

    if predicate_span and response_span and speech_act and speech_act not in {"repeat", "frame"}:
        bindings.append(
            {
                "component": "predicate_text",
                "binding_kind": speech_act,
                "claim_span": predicate_span,
                "response_span": response_span,
                "target_span": target_span,
            }
        )

    characterization_spans = claim_components.get("characterization") if isinstance(claim_components, Mapping) else None
    if isinstance(characterization_spans, list) and "deny_characterisation" in response_acts and response_span:
        for span in characterization_spans:
            if isinstance(span, Mapping):
                bindings.append(
                    {
                        "component": "characterization",
                        "binding_kind": "deny_characterisation",
                        "claim_span": span,
                        "response_span": response_span,
                    }
                )

    time_spans = claim_components.get("time") if isinstance(claim_components, Mapping) else None
    if isinstance(time_spans, list) and response_span:
        response_text = str(response_span.get("text") or "")
        response_hints = _extract_extraction_hints(response_text)
        response_times = response_hints.get("calendar_reference_mentions", [])
        if isinstance(response_times, list):
            response_time_set = {str(value).strip() for value in response_times if str(value).strip()}
            for span in time_spans:
                if not isinstance(span, Mapping):
                    continue
                if str(span.get("text") or "").strip() in response_time_set:
                    bindings.append(
                        {
                            "component": "time",
                            "binding_kind": "time_alignment",
                            "claim_span": span,
                            "response_span": _span_ref(response_text, str(span.get("text") or "")),
                        }
                    )

    for packet in justifications:
        if not isinstance(packet, Mapping):
            continue
        justification_type = str(packet.get("type") or "").strip()
        span = packet.get("span")
        if not justification_type or not isinstance(span, Mapping):
            continue
        bindings.append(
            {
                "component": "predicate_text",
                "binding_kind": justification_type,
                "claim_span": predicate_span,
                "response_span": span,
            }
        )

    return bindings


def _score_proposition_against_source_row(proposition: Mapping[str, Any], source_row: Mapping[str, Any]) -> dict[str, Any]:
    proposition_tokens = proposition.get("tokens", [])
    row_text = str(source_row.get("text") or "")
    comparison_mode = str(source_row.get("comparison_mode") or "").strip()
    row_score = _similarity_score(proposition_tokens, source_row.get("tokens", []))
    row_entry = {
        "score": row_score,
        "match_basis": "row",
        "match_excerpt": row_text.strip(),
    }
    segments = []
    for segment in _split_source_text_segments(row_text):
        segment_tokens = sorted(_tokenize(segment))
        score = _similarity_score(proposition_tokens, segment_tokens)
        segments.append(
            {
                "score": score,
                "match_basis": "segment",
                "match_excerpt": segment,
            }
        )
    candidates = segments if comparison_mode == "contested_narrative" else [row_entry, *segments]
    for candidate in candidates:
        role_data = _classify_argumentative_role(
            str(proposition.get("text") or ""),
            str(candidate["match_excerpt"] or ""),
            row_text,
            use_row_fallback=comparison_mode != "contested_narrative",
        )
        candidate["response_role"] = str(role_data["response_role"])
        candidate["response_cues"] = role_data["response_cues"]
        candidate["is_duplicate_excerpt"] = _is_duplicate_response_excerpt(
            str(proposition.get("text") or ""),
            str(candidate["match_excerpt"] or ""),
        )
        adjusted = float(candidate["score"])
        if comparison_mode == "contested_narrative" and (
            candidate["response_role"] == "restatement_only" or candidate["is_duplicate_excerpt"]
        ):
            adjusted = min(adjusted, max(_PARTIAL_MATCH_THRESHOLD, _COVERED_MATCH_THRESHOLD - 0.01))
        elif comparison_mode == "contested_narrative" and candidate["response_role"] in {"dispute", "admission", "explanation", "support_or_corroboration"} and adjusted >= _PARTIAL_MATCH_THRESHOLD:
            adjusted = min(1.0, round(adjusted + 0.05, 6))
        candidate["adjusted_score"] = adjusted

    best_candidate = max(
        candidates,
        key=lambda item: (float(item["adjusted_score"]), float(item["score"]), -len(str(item["match_excerpt"] or ""))),
    )
    duplicate_match_excerpt = None
    if comparison_mode == "contested_narrative" and (
        best_candidate["response_role"] == "restatement_only" or best_candidate["is_duplicate_excerpt"]
    ):
        substantive_candidates = [
            candidate
            for candidate in candidates
            if candidate["response_role"] in {"dispute", "admission", "explanation", "support_or_corroboration"}
            and not candidate["is_duplicate_excerpt"]
        ]
        if substantive_candidates:
            alternate_candidate = max(
                substantive_candidates,
                key=lambda item: (float(item["adjusted_score"]), float(item["score"]), -len(str(item["match_excerpt"] or ""))),
            )
            duplicate_match_excerpt = str(best_candidate["match_excerpt"] or "").strip()
            best_candidate = alternate_candidate

    best_score = float(best_candidate["score"])
    adjusted_score = float(best_candidate["adjusted_score"])
    best_basis = str(best_candidate["match_basis"])
    best_excerpt = str(best_candidate["match_excerpt"] or "").strip()
    response_role = str(best_candidate["response_role"])
    response_cues = best_candidate["response_cues"]

    return {
        "score": best_score,
        "adjusted_score": adjusted_score,
        "match_basis": best_basis,
        "match_excerpt": best_excerpt,
        "duplicate_match_excerpt": duplicate_match_excerpt,
        "response_role": response_role,
        "response_cues": response_cues,
    }


def _classify_affidavit_match(score: float, source_row: Mapping[str, Any] | None, response_role: str | None = None) -> str:
    if not isinstance(source_row, Mapping) or score < _PARTIAL_MATCH_THRESHOLD:
        return "unsupported_affidavit"
    if bool(source_row.get("is_abstained")):
        return "abstained_source"
    if bool(source_row.get("is_contested")):
        return "contested_source"
    comparison_mode = str(source_row.get("comparison_mode") or "").strip()
    if score >= _COVERED_MATCH_THRESHOLD and not (
        comparison_mode == "contested_narrative" and response_role == "restatement_only"
    ):
        return "covered"
    return "partial"


def _build_related_review_clusters(
    affidavit_rows: list[dict[str, Any]],
    source_review_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    affidavit_by_id = {
        str(row.get("proposition_id")): row
        for row in affidavit_rows
        if str(row.get("proposition_id") or "").strip()
    }
    related_rows_by_proposition: dict[str, list[dict[str, Any]]] = {}
    for row in source_review_rows:
        if row.get("review_status") != "missing_review":
            continue
        related_ids = row.get("related_affidavit_proposition_ids", [])
        if not isinstance(related_ids, list):
            continue
        for proposition_id in related_ids:
            proposition_key = str(proposition_id).strip()
            if not proposition_key:
                continue
            related_rows_by_proposition.setdefault(proposition_key, []).append(row)

    clusters: list[dict[str, Any]] = []
    for proposition_id, rows in sorted(related_rows_by_proposition.items()):
        affidavit_row = affidavit_by_id.get(proposition_id)
        if not affidavit_row:
            continue
        ranked_rows = sorted(
            rows,
            key=lambda row: (-float(row.get("best_match_score") or 0.0), str(row.get("source_row_id") or "")),
        )
        reason_counter: Counter[str] = Counter()
        workload_counter: Counter[str] = Counter()
        extraction_hint_counter: Counter[str] = Counter()
        candidate_anchor_counter: Counter[str] = Counter()
        for row in ranked_rows:
            raw_reason_codes = row.get("reason_codes", [])
            if not isinstance(raw_reason_codes, list):
                continue
            reason_counter.update(str(code).strip() for code in raw_reason_codes if str(code).strip())
            raw_workload_classes = row.get("workload_classes", [])
            if isinstance(raw_workload_classes, list):
                workload_counter.update(str(name).strip() for name in raw_workload_classes if str(name).strip())
            if row.get("has_transcript_timestamp_hint"):
                extraction_hint_counter["transcript_timestamp_hint"] += 1
            if row.get("has_calendar_reference_hint"):
                extraction_hint_counter["calendar_reference_hint"] += 1
            if row.get("has_procedural_event_cue"):
                extraction_hint_counter["procedural_event_cue"] += 1
            raw_candidate_anchors = row.get("candidate_anchors", [])
            if isinstance(raw_candidate_anchors, list):
                candidate_anchor_counter.update(
                    str(anchor.get("anchor_kind")).strip()
                    for anchor in raw_candidate_anchors
                    if isinstance(anchor, Mapping) and str(anchor.get("anchor_kind") or "").strip()
                )
        dominant_workload_class = None
        if workload_counter:
            dominant_workload_class = sorted(workload_counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
        has_temporal_hint_cluster = extraction_hint_counter["transcript_timestamp_hint"] > 0 or extraction_hint_counter["calendar_reference_hint"] > 0
        has_event_hint_cluster = extraction_hint_counter["procedural_event_cue"] > 0
        if dominant_workload_class == "chronology_gap" and has_temporal_hint_cluster and has_event_hint_cluster:
            recommended_next_action = "promote existing event/date cues into structured anchors"
        elif dominant_workload_class == "chronology_gap" and has_temporal_hint_cluster:
            recommended_next_action = "promote existing temporal cues into structured anchors"
        elif dominant_workload_class in {"chronology_gap", "event_extraction_gap"}:
            recommended_next_action = "extract structured event/date support"
        elif dominant_workload_class == "normalization_gap":
            recommended_next_action = "normalize transcript/source wording"
        elif dominant_workload_class == "review_queue_only":
            recommended_next_action = "advance review queue triage"
        elif dominant_workload_class == "evidence_gap":
            recommended_next_action = "operator evidentiary review"
        else:
            recommended_next_action = None
        clusters.append(
            {
                "proposition_id": proposition_id,
                "coverage_status": affidavit_row.get("coverage_status"),
                "text": affidavit_row.get("text"),
                "candidate_source_count": len(ranked_rows),
                "dominant_workload_class": dominant_workload_class,
                "recommended_next_action": recommended_next_action,
                "extraction_hint_rollup": [
                    {"hint_kind": hint_kind, "count": count}
                    for hint_kind, count in sorted(extraction_hint_counter.items(), key=lambda item: (-item[1], item[0]))
                ],
                "candidate_anchor_rollup": [
                    {"anchor_kind": anchor_kind, "count": count}
                    for anchor_kind, count in sorted(candidate_anchor_counter.items(), key=lambda item: (-item[1], item[0]))
                ],
                "reason_code_rollup": [
                    {"reason_code": reason_code, "count": count}
                    for reason_code, count in sorted(reason_counter.items(), key=lambda item: (-item[1], item[0]))
                ],
                "workload_class_rollup": [
                    {"workload_class": workload_class, "count": count}
                    for workload_class, count in sorted(workload_counter.items(), key=lambda item: (-item[1], item[0]))
                ],
                "candidate_source_rows": [
                    {
                        "source_row_id": row.get("source_row_id"),
                        "source_kind": row.get("source_kind"),
                        "best_match_score": row.get("best_match_score"),
                        "best_match_basis": row.get("best_match_basis"),
                        "best_match_excerpt": row.get("best_match_excerpt"),
                        "reason_codes": row.get("reason_codes", []),
                        "workload_classes": row.get("workload_classes", []),
                        "primary_workload_class": row.get("primary_workload_class"),
                        "recommended_next_action": row.get("recommended_next_action"),
                        "has_transcript_timestamp_hint": row.get("has_transcript_timestamp_hint", False),
                        "transcript_timestamp_windows": row.get("transcript_timestamp_windows", []),
                        "has_calendar_reference_hint": row.get("has_calendar_reference_hint", False),
                        "calendar_reference_mentions": row.get("calendar_reference_mentions", []),
                        "has_procedural_event_cue": row.get("has_procedural_event_cue", False),
                        "procedural_event_keywords": row.get("procedural_event_keywords", []),
                        "candidate_anchors": row.get("candidate_anchors", []),
                        "statement_ids": row.get("statement_ids", []),
                        "excerpt_ids": row.get("excerpt_ids", []),
                        "source_ids": row.get("source_ids", []),
                    }
                    for row in ranked_rows
                ],
            }
        )
    return clusters


def build_affidavit_coverage_review(
    *,
    source_payload: Mapping[str, Any],
    affidavit_text: str,
    source_path: str | None = None,
    affidavit_path: str | None = None,
) -> dict[str, Any]:
    source_rows, source_meta = _extract_source_rows(source_payload)
    propositions = _split_affidavit_text(affidavit_text)
    source_rows_by_id = {row["source_row_id"]: dict(row) for row in source_rows}

    affidavit_rows: list[dict[str, Any]] = []
    zelph_claim_state_facts: list[dict[str, Any]] = []
    for proposition in propositions:
        scored_rows = []
        for row in source_rows:
            score_row = _score_proposition_against_source_row(proposition, row)
            raw_score = float(score_row["score"])
            adjusted_score = float(score_row.get("adjusted_score") or raw_score)
            if raw_score <= 0:
                continue
            scored_rows.append((adjusted_score, raw_score, row, score_row))
        scored_rows.sort(key=lambda item: (-item[0], -item[1], item[2]["source_row_id"]))
        best_adjusted_score, best_score, best_row, best_score_row = scored_rows[0] if scored_rows else (0.0, 0.0, None, {})
        status = _classify_affidavit_match(
            best_adjusted_score,
            best_row,
            str(best_score_row.get("response_role") or ""),
        )
        matched_rows = [
            {
                "source_row_id": row["source_row_id"],
                "score": raw_score,
                "adjusted_score": adjusted_score,
                "candidate_status": row["candidate_status"],
                "review_status": row["review_status"],
                "match_basis": score_row["match_basis"],
                "match_excerpt": score_row["match_excerpt"],
                "duplicate_match_excerpt": score_row.get("duplicate_match_excerpt"),
                "response_role": score_row.get("response_role"),
                "response_cues": score_row.get("response_cues", []),
            }
            for adjusted_score, raw_score, row, score_row in scored_rows[:3]
        ]
        response_packet = _infer_response_packet(
            proposition_text=str(proposition["text"]),
            best_match_excerpt=str(best_score_row.get("match_excerpt") or ""),
            duplicate_match_excerpt=best_score_row.get("duplicate_match_excerpt"),
            response_role=best_score_row.get("response_role"),
            response_cues=list(best_score_row.get("response_cues", [])),
            coverage_status=status,
        )
        claim_packet = _build_claim_packet(str(proposition["text"]))
        response_object = _build_response_packet(
            proposition_text=str(proposition["text"]),
            best_match_excerpt=str(best_score_row.get("match_excerpt") or ""),
            duplicate_match_excerpt=best_score_row.get("duplicate_match_excerpt"),
            response_role=best_score_row.get("response_role"),
            response_acts=response_packet["response_acts"],
        )
        justification_packets = _build_justification_packets(str(best_score_row.get("match_excerpt") or ""))
        response_component_bindings = _build_response_component_bindings(
            claim=claim_packet,
            response=response_object,
            justifications=justification_packets,
            response_acts=response_packet["response_acts"],
        )
        response_object["component_bindings"] = response_component_bindings
        response_object["component_targets"] = sorted(
            {
                str(binding.get("component") or "").strip()
                for binding in response_component_bindings
                if isinstance(binding, Mapping) and str(binding.get("component") or "").strip()
            }
        )
        claim_state = _derive_claim_state(
            response_acts=response_packet["response_acts"],
            legal_significance_signals=response_packet["legal_significance_signals"],
            support_status=response_packet["support_status"],
            duplicate_match_excerpt=best_score_row.get("duplicate_match_excerpt"),
        )
        primary_target_component = _derive_primary_target_component(
            response=response_object,
            response_acts=response_packet["response_acts"],
        )
        semantic_basis = _derive_semantic_basis(
            response_cues=list(best_score_row.get("response_cues", [])),
            response=response_object,
            response_component_bindings=response_component_bindings,
            justifications=justification_packets,
        )
        semantic_candidate = build_contested_claim_candidate(
            basis=semantic_basis,
            claim_span=claim_packet.get("text_span") if isinstance(claim_packet, Mapping) else None,
            response_span=response_object.get("text_span") if isinstance(response_object, Mapping) else None,
            speech_act=str(response_object.get("speech_act") or ""),
            polarity=str(response_object.get("polarity") or ""),
            target_component=primary_target_component,
            support_direction=claim_state["support_direction"],
            conflict_state=claim_state["conflict_state"],
            evidentiary_state=claim_state["evidentiary_state"],
            modifiers=list(response_object.get("modifiers") or []),
            justifications=justification_packets,
            evidence_spans=[
                span
                for span in [
                    response_object.get("text_span"),
                    response_object.get("duplicate_text_span"),
                ]
                if isinstance(span, Mapping)
            ],
            rule_ids=list(best_score_row.get("response_cues", [])),
        )
        promotion = promote_contested_claim(semantic_candidate)
        affidavit_rows.append(
            {
                "proposition_id": proposition["proposition_id"],
                "paragraph_id": proposition["paragraph_id"],
                "paragraph_order": proposition["paragraph_order"],
                "sentence_order": proposition["sentence_order"],
                "text": proposition["text"],
                "tokens": proposition["tokens"],
                "coverage_status": status,
                "best_match_score": best_score,
                "best_adjusted_match_score": best_adjusted_score,
                "best_source_row_id": best_row["source_row_id"] if isinstance(best_row, Mapping) else None,
                "best_match_basis": best_score_row.get("match_basis"),
                "best_match_excerpt": best_score_row.get("match_excerpt"),
                "duplicate_match_excerpt": best_score_row.get("duplicate_match_excerpt"),
                "best_response_role": best_score_row.get("response_role"),
                "best_response_cues": best_score_row.get("response_cues", []),
                "response_acts": response_packet["response_acts"],
                "legal_significance_signals": response_packet["legal_significance_signals"],
                "support_status": response_packet["support_status"],
                "semantic_candidate": semantic_candidate,
                "semantic_basis": semantic_basis,
                "promotion_status": promotion["status"],
                "promotion_basis": promotion["basis"],
                "promotion_reason": promotion["reason"],
                "support_direction": claim_state["support_direction"],
                "conflict_state": claim_state["conflict_state"],
                "evidentiary_state": claim_state["evidentiary_state"],
                "operational_status": claim_state["operational_status"],
                "claim": claim_packet,
                "response": response_object,
                "justifications": justification_packets,
                "matched_source_rows": matched_rows,
            }
        )
        zelph_claim_state_facts.append(
            _build_zelph_claim_state_fact(
                proposition_id=str(proposition["proposition_id"]),
                best_source_row_id=(best_row["source_row_id"] if isinstance(best_row, Mapping) else None),
                claim=claim_packet,
                response=response_object,
                justifications=justification_packets,
                claim_state=claim_state,
                response_acts=response_packet["response_acts"],
                legal_significance_signals=response_packet["legal_significance_signals"],
                support_status=response_packet["support_status"],
                coverage_status=status,
                semantic_basis=semantic_basis,
                promotion=promotion,
            )
        )
        for adjusted_score, raw_score, row, score_row in scored_rows:
            source_row = source_rows_by_id[row["source_row_id"]]
            if adjusted_score > float(source_row.get("best_adjusted_match_score") or 0.0):
                source_row["best_adjusted_match_score"] = adjusted_score
                source_row["best_match_score"] = raw_score
                source_row["best_affidavit_proposition_id"] = proposition["proposition_id"]
                source_row["best_match_basis"] = score_row["match_basis"]
                source_row["best_match_excerpt"] = score_row["match_excerpt"]
                source_row["duplicate_match_excerpt"] = score_row.get("duplicate_match_excerpt")
                source_row["best_response_role"] = score_row.get("response_role")
                source_row["best_response_cues"] = list(score_row.get("response_cues", []))
            is_contested_narrative = str(row.get("comparison_mode") or "").strip() == "contested_narrative"
            if adjusted_score >= _COVERED_MATCH_THRESHOLD and not (
                is_contested_narrative and score_row.get("response_role") == "restatement_only"
            ):
                source_row.setdefault("matched_affidavit_proposition_ids", []).append(proposition["proposition_id"])
            elif adjusted_score >= _PARTIAL_MATCH_THRESHOLD:
                source_row.setdefault("related_affidavit_proposition_ids", []).append(proposition["proposition_id"])

    source_review_rows: list[dict[str, Any]] = []
    for row in source_rows_by_id.values():
        matched_ids = list(row.get("matched_affidavit_proposition_ids", []))
        related_ids = [
            proposition_id
            for proposition_id in list(row.get("related_affidavit_proposition_ids", []))
            if proposition_id not in matched_ids
        ]
        if matched_ids:
            review_status = "covered" if not row["is_contested"] and not row["is_abstained"] else (
                "contested_source" if row["is_contested"] else "abstained_source"
            )
        elif row["is_abstained"]:
            review_status = "abstained_source"
        elif row["is_contested"]:
            review_status = "contested_source"
        else:
            review_status = "missing_review"
        extraction_hints = _extract_extraction_hints(row["text"])
        candidate_anchors = _build_candidate_anchors(extraction_hints)
        workload_profile = _classify_workload_with_hints(row["reason_codes"], review_status, extraction_hints)
        source_review_rows.append(
            {
                "source_row_id": row["source_row_id"],
                "source_kind": row["source_kind"],
                "text": row["text"],
                "candidate_status": row["candidate_status"],
                "review_status": review_status,
                "matched_affidavit_proposition_ids": matched_ids,
                "related_affidavit_proposition_ids": related_ids,
                "best_affidavit_proposition_id": row.get("best_affidavit_proposition_id"),
                "best_match_score": round(float(row.get("best_match_score") or 0.0), 6),
                "best_adjusted_match_score": round(float(row.get("best_adjusted_match_score") or 0.0), 6),
                "best_match_basis": row.get("best_match_basis"),
                "best_match_excerpt": row.get("best_match_excerpt"),
                "duplicate_match_excerpt": row.get("duplicate_match_excerpt"),
                "best_response_role": row.get("best_response_role"),
                "best_response_cues": row.get("best_response_cues", []),
                "reason_codes": row["reason_codes"],
                "workload_classes": workload_profile["workload_classes"],
                "primary_workload_class": workload_profile["primary_workload_class"],
                "recommended_next_action": workload_profile["recommended_next_action"],
                "has_transcript_timestamp_hint": extraction_hints["has_transcript_timestamp_hint"],
                "transcript_timestamp_windows": extraction_hints["transcript_timestamp_windows"],
                "has_calendar_reference_hint": extraction_hints["has_calendar_reference_hint"],
                "calendar_reference_mentions": extraction_hints["calendar_reference_mentions"],
                "has_procedural_event_cue": extraction_hints["has_procedural_event_cue"],
                "procedural_event_keywords": extraction_hints["procedural_event_keywords"],
                "candidate_anchors": candidate_anchors,
                "statement_ids": row["statement_ids"],
                "excerpt_ids": row["excerpt_ids"],
                "source_ids": row["source_ids"],
            }
        )

    summary = {
        "affidavit_proposition_count": len(affidavit_rows),
        "source_row_count": len(source_review_rows),
        "covered_count": sum(1 for row in affidavit_rows if row["coverage_status"] == "covered"),
        "partial_count": sum(1 for row in affidavit_rows if row["coverage_status"] == "partial"),
        "contested_affidavit_count": sum(1 for row in affidavit_rows if row["coverage_status"] == "contested_source"),
        "abstained_affidavit_count": sum(1 for row in affidavit_rows if row["coverage_status"] == "abstained_source"),
        "unsupported_affidavit_count": sum(1 for row in affidavit_rows if row["coverage_status"] == "unsupported_affidavit"),
        "missing_review_count": sum(1 for row in source_review_rows if row["review_status"] == "missing_review"),
        "related_source_count": sum(
            1
            for row in source_review_rows
            if row["review_status"] == "missing_review" and row["related_affidavit_proposition_ids"]
        ),
        "contested_source_count": sum(1 for row in source_review_rows if row["review_status"] == "contested_source"),
        "abstained_source_count": sum(1 for row in source_review_rows if row["review_status"] == "abstained_source"),
    }
    for workload_class in _WORKLOAD_CLASS_PRIORITY:
        summary[f"{workload_class}_count"] = sum(
            1
            for row in source_review_rows
            if row["review_status"] == "missing_review" and workload_class in row["workload_classes"]
        )
    summary["transcript_timestamp_hint_count"] = sum(
        1 for row in source_review_rows if row["review_status"] == "missing_review" and row["has_transcript_timestamp_hint"]
    )
    summary["calendar_reference_hint_count"] = sum(
        1 for row in source_review_rows if row["review_status"] == "missing_review" and row["has_calendar_reference_hint"]
    )
    summary["procedural_event_cue_count"] = sum(
        1 for row in source_review_rows if row["review_status"] == "missing_review" and row["has_procedural_event_cue"]
    )
    summary["candidate_anchor_count"] = sum(
        len(row["candidate_anchors"]) for row in source_review_rows if row["review_status"] == "missing_review"
    )
    related_review_clusters = _build_related_review_clusters(affidavit_rows, source_review_rows)
    provisional_structured_anchors = _build_provisional_structured_anchors(source_review_rows)
    provisional_anchor_bundles = _build_provisional_anchor_bundles(provisional_structured_anchors)
    summary["related_review_cluster_count"] = len(related_review_clusters)
    summary["provisional_structured_anchor_count"] = len(provisional_structured_anchors)
    summary["provisional_anchor_bundle_count"] = len(provisional_anchor_bundles)
    coveredish = summary["covered_count"] + summary["partial_count"] + summary["contested_affidavit_count"] + summary["abstained_affidavit_count"]
    summary["affidavit_supported_ratio"] = round(
        coveredish / summary["affidavit_proposition_count"], 6
    ) if summary["affidavit_proposition_count"] else 0.0
    response_role_counter: Counter[str] = Counter(
        str(row.get("best_response_role") or "unknown").strip() or "unknown"
        for row in affidavit_rows
    )
    substantive_roles = {"dispute", "admission", "explanation", "support_or_corroboration"}
    substantive_response_count = sum(
        1
        for row in affidavit_rows
        if str(row.get("best_response_role") or "").strip() in substantive_roles
    )
    summary["best_response_role_counts"] = {
        role: count
        for role, count in sorted(response_role_counter.items(), key=lambda item: item[0])
    }
    summary["substantive_response_count"] = substantive_response_count
    summary["substantive_response_ratio"] = round(
        substantive_response_count / summary["affidavit_proposition_count"], 6
    ) if summary["affidavit_proposition_count"] else 0.0
    support_status_counter: Counter[str] = Counter(
        str(row.get("support_status") or "unknown").strip() or "unknown"
        for row in affidavit_rows
    )
    summary["support_status_counts"] = {
        status: count
        for status, count in sorted(support_status_counter.items(), key=lambda item: item[0])
    }
    for field in ("support_direction", "conflict_state", "evidentiary_state", "operational_status"):
        counter: Counter[str] = Counter(
            str(row.get(field) or "unknown").strip() or "unknown"
            for row in affidavit_rows
        )
        summary[f"{field}_counts"] = {
            key: count
            for key, count in sorted(counter.items(), key=lambda item: item[0])
        }

    source_kind = str(source_meta.get("source_kind") or "").strip()
    lane_variant = "review"
    artifact_id = f"au_review_{ARTIFACT_VERSION}"
    if source_kind == "au_checked_handoff_slice":
        lane_variant = "narrow"
        artifact_id = f"au_narrow_{ARTIFACT_VERSION}"
    elif source_kind == "au_dense_overlay_slice":
        lane_variant = "dense"
        artifact_id = f"au_dense_{ARTIFACT_VERSION}"

    normalized_metrics_v1 = compute_normalized_metrics_from_profile(
        profile=get_normalized_profile("au"),
        artifact_id=artifact_id,
        lane_family="au",
        lane_variant=lane_variant,
        review_item_rows=affidavit_rows,
        source_review_rows=source_review_rows,
        candidate_signal_count=sum(
            len(row["candidate_anchors"])
            for row in source_review_rows
            if row["review_status"] == "missing_review"
        ),
        provisional_queue_row_count=len(provisional_structured_anchors),
        provisional_bundle_count=len(provisional_anchor_bundles),
    )

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "affidavit_coverage_review",
        "source_input": {
            "path": source_path,
            **source_meta,
        },
        "affidavit_input": {
            "path": affidavit_path,
            "character_count": len(affidavit_text),
        },
        "summary": summary,
        "affidavit_rows": affidavit_rows,
        "source_review_rows": source_review_rows,
        "related_review_clusters": related_review_clusters,
        "provisional_structured_anchors": provisional_structured_anchors,
        "provisional_anchor_bundles": provisional_anchor_bundles,
        "zelph_claim_state_facts": zelph_claim_state_facts,
        "normalized_metrics_v1": normalized_metrics_v1,
    }


def build_summary_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), Mapping) else {}
    source_input = payload.get("source_input", {}) if isinstance(payload.get("source_input"), Mapping) else {}
    lines = [
        "# Affidavit Coverage Review",
        "",
        f"- Version: `{payload.get('version')}`",
        f"- Source kind: `{source_input.get('source_kind')}`",
        f"- Source rows: `{summary.get('source_row_count', 0)}`",
        f"- Affidavit propositions: `{summary.get('affidavit_proposition_count', 0)}`",
        f"- Covered: `{summary.get('covered_count', 0)}`",
        f"- Partial: `{summary.get('partial_count', 0)}`",
        f"- Unsupported affidavit propositions: `{summary.get('unsupported_affidavit_count', 0)}`",
        f"- Missing-review source rows: `{summary.get('missing_review_count', 0)}`",
        f"- Related-but-uncovered source rows: `{summary.get('related_source_count', 0)}`",
        f"- Related review clusters: `{summary.get('related_review_cluster_count', 0)}`",
        f"- Normalization-gap source rows: `{summary.get('normalization_gap_count', 0)}`",
        f"- Chronology-gap source rows: `{summary.get('chronology_gap_count', 0)}`",
        f"- Event-extraction-gap source rows: `{summary.get('event_extraction_gap_count', 0)}`",
        f"- Review-queue-only source rows: `{summary.get('review_queue_only_count', 0)}`",
        f"- Evidence-gap source rows: `{summary.get('evidence_gap_count', 0)}`",
        f"- Transcript-timestamp hints: `{summary.get('transcript_timestamp_hint_count', 0)}`",
        f"- Calendar-reference hints: `{summary.get('calendar_reference_hint_count', 0)}`",
        f"- Procedural-event cues: `{summary.get('procedural_event_cue_count', 0)}`",
        f"- Candidate anchors: `{summary.get('candidate_anchor_count', 0)}`",
        f"- Provisional structured anchors: `{summary.get('provisional_structured_anchor_count', 0)}`",
        f"- Provisional anchor bundles: `{summary.get('provisional_anchor_bundle_count', 0)}`",
        f"- Contested source rows: `{summary.get('contested_source_count', 0)}`",
        f"- Abstained source rows: `{summary.get('abstained_source_count', 0)}`",
        f"- Textually-addressed ratio: `{summary.get('affidavit_supported_ratio', 0.0)}`",
        f"- Substantive-response ratio: `{summary.get('substantive_response_ratio', 0.0)}`",
        "",
        "## Reading",
        "",
        "- This is a provenance-first comparison surface, not a legal sufficiency verdict.",
        "- `covered` means strong segment-aware alignment that is not pure allegation restatement in contested-narrative mode.",
        "- `partial` often means either weaker alignment or allegation restatement without a clear reply move.",
        "- `missing_review`, `contested_source`, and `abstained_source` remain operator-review statuses rather than automatic filing conclusions.",
    ]
    response_role_counts = summary.get("best_response_role_counts", {})
    if isinstance(response_role_counts, Mapping) and response_role_counts:
        lines.extend(["", "## Argumentative Read", ""])
        for role, count in sorted(response_role_counts.items()):
            lines.append(f"- `{role}`: `{count}`")
    support_status_counts = summary.get("support_status_counts", {})
    if isinstance(support_status_counts, Mapping) and support_status_counts:
        lines.extend(["", "## Support Status", ""])
        for status, count in sorted(support_status_counts.items()):
            lines.append(f"- `{status}`: `{count}`")
    for field, title in (
        ("support_direction_counts", "Support Direction"),
        ("conflict_state_counts", "Conflict State"),
        ("evidentiary_state_counts", "Evidentiary State"),
        ("operational_status_counts", "Operational Status"),
    ):
        counts = summary.get(field, {})
        if isinstance(counts, Mapping) and counts:
            lines.extend(["", f"## {title}", ""])
            for key, count in sorted(counts.items()):
                lines.append(f"- `{key}`: `{count}`")
    normalized_metrics = (
        payload.get("normalized_metrics_v1", {})
        if isinstance(payload.get("normalized_metrics_v1"), Mapping)
        else {}
    )
    if normalized_metrics:
        lines.extend(["", *render_normalized_metrics_markdown(normalized_metrics)])
    clusters = payload.get("related_review_clusters", [])
    if isinstance(clusters, list) and clusters:
        lines.extend(
            [
                "",
                "## Related Review Clusters",
                "",
            ]
        )
        for cluster in clusters:
            if not isinstance(cluster, Mapping):
                continue
            proposition_id = cluster.get("proposition_id")
            text = str(cluster.get("text") or "").strip()
            candidate_count = int(cluster.get("candidate_source_count") or 0)
            lines.append(f"- `{proposition_id}`: {candidate_count} related source rows")
            if text:
                lines.append(f"  Proposition: {text}")
            dominant_workload_class = cluster.get("dominant_workload_class")
            if dominant_workload_class:
                lines.append(f"  Dominant workload: {dominant_workload_class}")
            recommended_next_action = str(cluster.get("recommended_next_action") or "").strip()
            if recommended_next_action:
                lines.append(f"  Recommended next action: {recommended_next_action}")
            extraction_rollup = cluster.get("extraction_hint_rollup", [])
            if isinstance(extraction_rollup, list) and extraction_rollup:
                top_hints = ", ".join(
                    f"{entry.get('hint_kind')} ({entry.get('count')})"
                    for entry in extraction_rollup[:3]
                    if isinstance(entry, Mapping)
                )
                if top_hints:
                    lines.append(f"  Extraction hints: {top_hints}")
            candidate_anchor_rollup = cluster.get("candidate_anchor_rollup", [])
            if isinstance(candidate_anchor_rollup, list) and candidate_anchor_rollup:
                top_anchor_kinds = ", ".join(
                    f"{entry.get('anchor_kind')} ({entry.get('count')})"
                    for entry in candidate_anchor_rollup[:3]
                    if isinstance(entry, Mapping)
                )
                if top_anchor_kinds:
                    lines.append(f"  Candidate anchors: {top_anchor_kinds}")
            workload_rollup = cluster.get("workload_class_rollup", [])
            if isinstance(workload_rollup, list) and workload_rollup:
                top_workloads = ", ".join(
                    f"{entry.get('workload_class')} ({entry.get('count')})"
                    for entry in workload_rollup[:3]
                    if isinstance(entry, Mapping)
                )
                if top_workloads:
                    lines.append(f"  Top workload classes: {top_workloads}")
            reason_rollup = cluster.get("reason_code_rollup", [])
            if isinstance(reason_rollup, list) and reason_rollup:
                top_reasons = ", ".join(
                    f"{entry.get('reason_code')} ({entry.get('count')})"
                    for entry in reason_rollup[:3]
                    if isinstance(entry, Mapping)
                )
                if top_reasons:
                    lines.append(f"  Top reasons: {top_reasons}")
            candidate_rows = cluster.get("candidate_source_rows", [])
            if isinstance(candidate_rows, list):
                for candidate_row in candidate_rows[:3]:
                    if not isinstance(candidate_row, Mapping):
                        continue
                    source_row_id = candidate_row.get("source_row_id")
                    score = candidate_row.get("best_match_score")
                    excerpt = str(candidate_row.get("best_match_excerpt") or "").strip()
                    lines.append(f"  Candidate `{source_row_id}` score `{score}`")
                    if excerpt:
                        lines.append(f"  Excerpt: {excerpt}")
    provisional_rows = payload.get("provisional_structured_anchors", [])
    if isinstance(provisional_rows, list) and provisional_rows:
        lines.extend(
            [
                "",
                "## Provisional Structured Anchors",
                "",
            ]
        )
        for row in provisional_rows[:5]:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                f"- `#{row.get('priority_rank')}` `{row.get('provisional_anchor_id')}` {row.get('anchor_kind')} -> {row.get('anchor_label')} (score `{row.get('priority_score')}`)"
            )
    provisional_bundles = payload.get("provisional_anchor_bundles", [])
    if isinstance(provisional_bundles, list) and provisional_bundles:
        lines.extend(
            [
                "",
                "## Provisional Anchor Bundles",
                "",
            ]
        )
        for bundle in provisional_bundles[:5]:
            if not isinstance(bundle, Mapping):
                continue
            lines.append(
                f"- `#{bundle.get('bundle_rank')}` `{bundle.get('source_row_id')}` anchors `{bundle.get('anchor_count')}` top-score `{bundle.get('top_priority_score')}`"
            )
    return "\n".join(lines) + "\n"


def write_affidavit_coverage_review(
    *,
    output_dir: Path,
    source_payload: Mapping[str, Any],
    affidavit_text: str,
    source_path: str | None = None,
    affidavit_path: str | None = None,
) -> dict[str, str]:
    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path=source_path,
        affidavit_path=affidavit_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{ARTIFACT_VERSION}.json"
    summary_path = output_dir / f"{ARTIFACT_VERSION}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    return {"artifact_path": str(artifact_path), "summary_path": str(summary_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a bounded affidavit-coverage review artifact from a source bundle and affidavit draft.")
    parser.add_argument("--source-json", required=True, help="Path to a fact.review.bundle.v1 JSON or AU checked handoff slice JSON.")
    parser.add_argument("--affidavit-text", required=True, help="Path to the affidavit/declaration draft text file.")
    parser.add_argument("--output-dir", required=True, help="Directory where JSON and summary outputs will be written.")
    args = parser.parse_args()

    source_path = Path(args.source_json)
    affidavit_path = Path(args.affidavit_text)
    source_payload = _load_json(source_path)
    affidavit_text = affidavit_path.read_text(encoding="utf-8")
    result = write_affidavit_coverage_review(
        output_dir=Path(args.output_dir),
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path=str(source_path),
        affidavit_path=str(affidavit_path),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
