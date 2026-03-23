#!/usr/bin/env python3
"""Score stored Wikipedia snapshot manifests for article-wide ingest coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts.report_wiki_random_lexer_coverage import score_snapshot_payload as score_reducer_payload  # noqa: E402
from scripts.report_wiki_random_timeline_readiness import score_snapshot_payload as score_timeline_payload  # noqa: E402
from src.wiki_timeline.article_state import build_article_sentence_surface, build_wiki_article_state  # noqa: E402


SCHEMA_VERSION = "wiki_random_article_ingest_coverage_report_v0_4"

_NO_SPACE_SENTENCE_JOIN_RE = re.compile(r"[.!?][A-Z][a-z]")
_CAMEL_GLUE_RE = re.compile(r"\b[a-z]{4,}[A-Z][a-z]{2,}\b")
_CITATION_TAIL_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]\s*$")
_METADATA_TAIL_RE = re.compile(r"(?:\s+[|;]\s*[A-Za-z0-9_()/-]+){1,}\s*$")
_TEMPLATE_RESIDUE_MARKERS = ("{{", "}}", "[[", "]]", "thumb|", "File:", "Image:", "px|")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_BIOGRAPHY_CATEGORY_TERMS = (" births", " deaths", "people", "biography")
_PLACE_TERMS = ("city", "town", "village", "county", "district", "province", "state", "metropolitan area")
_FACILITY_TERMS = ("complex", "stadium", "hotel", "airport", "museum", "building", "arena", "bridge")
_PROJECT_TERMS = ("project", "repository", "organization", "organisation", "authority", "company", "institution")
_SPECIES_CATEGORY_TERMS = ("species", "moths", "birds", "plants", "taxa", "genera", "fauna")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / float(len(values)), 6)


def _mean_optional(values: list[float | None]) -> float | None:
    kept = [float(value) for value in values if value is not None]
    if not kept:
        return None
    return round(sum(kept) / float(len(kept)), 6)


def _linear_descending_score(value: float, *, good: float, bad: float) -> float:
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    if bad <= good:
        return 0.0
    return round(1.0 - ((value - good) / (bad - good)), 6)


def _extract_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("resolved", "title", "text", "label"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
        return ""
    return str(value or "").strip()


def _lane_has_value(items: Any) -> bool:
    return isinstance(items, list) and any(_extract_text(item) for item in items)


def _normalized_surface(value: Any) -> str:
    text = _extract_text(value).lower().replace("_", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def _surface_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 5 and left in right:
        return True
    if len(right) >= 5 and right in left:
        return True
    return False


def _event_has_action(event: Mapping[str, Any]) -> bool:
    if str(event.get("action") or "").strip():
        return True
    for step in event.get("steps") or []:
        if isinstance(step, Mapping) and str(step.get("action") or "").strip():
            return True
    return False


def _event_has_actor(event: Mapping[str, Any]) -> bool:
    if _lane_has_value(event.get("actors")):
        return True
    for step in event.get("steps") or []:
        if isinstance(step, Mapping) and _lane_has_value(step.get("subjects")):
            return True
    return False


def _event_has_object(event: Mapping[str, Any]) -> bool:
    object_lanes = (
        event.get("entity_objects"),
        event.get("numeric_objects"),
        event.get("modifier_objects"),
        event.get("objects"),
    )
    for lane in object_lanes:
        if _lane_has_value(lane):
            return True
    for step in event.get("steps") or []:
        if not isinstance(step, Mapping):
            continue
        for lane_name in ("entity_objects", "numeric_objects", "modifier_objects", "objects"):
            if _lane_has_value(step.get(lane_name)):
                return True
    return False


def _step_has_actor_binding(step: Mapping[str, Any]) -> bool:
    return bool(str(step.get("action") or "").strip()) and _lane_has_value(step.get("subjects"))


def _step_has_object_binding(step: Mapping[str, Any]) -> bool:
    if not str(step.get("action") or "").strip():
        return False
    for lane_name in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
        if _lane_has_value(step.get(lane_name)):
            return True
    return False


def _score_observation_explosion(
    *,
    observation_count: int,
    article_sentence_count: int,
    article_aao_event_count: int,
) -> tuple[float, dict[str, float], list[str]]:
    observations_per_sentence = _ratio(observation_count, article_sentence_count)
    observations_per_event = _ratio(observation_count, article_aao_event_count)
    pressure_ratio = max(observations_per_sentence, observations_per_event)
    score = _linear_descending_score(pressure_ratio, good=8.0, bad=16.0)
    issues: list[str] = []
    if pressure_ratio >= 12.0:
        issues.append("observation_explosion_high")
    elif pressure_ratio > 8.0:
        issues.append("observation_explosion_medium")
    return (
        score,
        {
            "observations_per_sentence": observations_per_sentence,
            "observations_per_event": observations_per_event,
            "pressure_ratio": round(pressure_ratio, 6),
        },
        issues,
    )


def _detect_text_hygiene(
    article_aao_rows: list[Mapping[str, Any]],
) -> tuple[float, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    flagged_count = 0
    for row in article_aao_rows:
        text = str(row.get("text") or "").strip()
        reason: str | None = None
        if not text:
            reason = "empty_text"
        elif _CITATION_TAIL_RE.search(text):
            reason = "citation_tail_residue"
        elif any(marker in text for marker in _TEMPLATE_RESIDUE_MARKERS):
            reason = "template_or_media_residue"
        elif _NO_SPACE_SENTENCE_JOIN_RE.search(text):
            reason = "smashed_sentence_join"
        elif _CAMEL_GLUE_RE.search(text):
            reason = "suspicious_no_space_token"
        elif _METADATA_TAIL_RE.search(text):
            reason = "malformed_metadata_tail"
        if reason is None:
            continue
        flagged_count += 1
        if len(warnings) < 5:
            warnings.append(
                {
                    "event_id": str(row.get("event_id") or ""),
                    "reason": reason,
                    "example": text[:140],
                }
            )
    if not article_aao_rows:
        return 0.0, warnings
    return round(max(0.0, 1.0 - (flagged_count / float(len(article_aao_rows)))), 6), warnings


def _score_actor_action_binding(article_aao_rows: list[Mapping[str, Any]]) -> tuple[float, int, int, list[str]]:
    action_events = 0
    bound_events = 0
    for row in article_aao_rows:
        if not _event_has_action(row):
            continue
        action_events += 1
        steps = [step for step in row.get("steps") or [] if isinstance(step, Mapping)]
        if steps:
            if any(_step_has_actor_binding(step) for step in steps):
                bound_events += 1
        elif bool(str(row.get("action") or "").strip()) and _lane_has_value(row.get("actors")):
            bound_events += 1
    score = _ratio(bound_events, action_events) if action_events else 0.0
    issues = ["weak_actor_action_binding"] if action_events and bound_events < action_events else []
    return score, bound_events, action_events, issues


def _score_object_binding(article_aao_rows: list[Mapping[str, Any]]) -> tuple[float, int, int, list[str]]:
    action_events = 0
    bound_events = 0
    for row in article_aao_rows:
        if not _event_has_action(row):
            continue
        action_events += 1
        steps = [step for step in row.get("steps") or [] if isinstance(step, Mapping)]
        if steps:
            if any(_step_has_object_binding(step) for step in steps):
                bound_events += 1
        elif bool(str(row.get("action") or "").strip()) and _event_has_object(row):
            bound_events += 1
    score = _ratio(bound_events, action_events) if action_events else 0.0
    issues = ["weak_object_binding"] if action_events and bound_events < action_events else []
    return score, bound_events, action_events, issues


def _timeline_honesty(
    timeline_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    if not timeline_rows:
        return (
            {
                "timeline_row_count": 0,
                "explicit_anchor_ratio": 0.0,
                "weak_anchor_ratio": 0.0,
                "none_anchor_ratio": 0.0,
                "timeline_honesty_score": None,
                "abstained": True,
            },
            [],
        )

    explicit_count = sum(1 for row in timeline_rows if str(row.get("anchor_status") or "none") == "explicit")
    weak_count = sum(1 for row in timeline_rows if str(row.get("anchor_status") or "none") == "weak")
    none_count = sum(1 for row in timeline_rows if str(row.get("anchor_status") or "none") == "none")
    explicit_anchor_ratio = _ratio(explicit_count, len(timeline_rows))
    weak_anchor_ratio = _ratio(weak_count, len(timeline_rows))
    none_anchor_ratio = _ratio(none_count, len(timeline_rows))
    timeline_honesty_score = round((explicit_count + (0.5 * weak_count)) / float(len(timeline_rows)), 6)
    issues: list[str] = []
    if none_anchor_ratio >= 0.8:
        issues.append("timeline_mostly_undated")
    if explicit_anchor_ratio == 0.0 and weak_anchor_ratio > 0.0:
        issues.append("timeline_only_weakly_anchored")
    return (
        {
            "timeline_row_count": len(timeline_rows),
            "explicit_anchor_ratio": explicit_anchor_ratio,
            "weak_anchor_ratio": weak_anchor_ratio,
            "none_anchor_ratio": none_anchor_ratio,
            "timeline_honesty_score": timeline_honesty_score,
            "abstained": False,
        },
        issues,
    )


def _classify_page_family(
    payload: Mapping[str, Any],
    article_sentences: list[Mapping[str, Any]],
) -> dict[str, Any]:
    categories = [str(item).lower() for item in (payload.get("categories") or []) if str(item).strip()]
    lead_text = str(article_sentences[0].get("text") or "").lower() if article_sentences else ""
    title = str(payload.get("title") or "")
    title_lc = title.lower()
    candidates: list[tuple[str, float, str]] = []

    if any(any(term in category for term in _SPECIES_CATEGORY_TERMS) for category in categories) or any(
        term in lead_text for term in ("species of", "family geometr", "family of moth", "species of moth")
    ):
        candidates.append(("species_taxonomy", 0.95 if categories else 0.82, "species/taxonomy signal"))
    if any(any(term in category for term in _BIOGRAPHY_CATEGORY_TERMS) for category in categories) or (
        re.search(r"\(\d{4}[–-]\d{4}\)", lead_text) and " was " in lead_text
    ):
        candidates.append(("biography", 0.97 if categories else 0.84, "biography signal"))
    if any(any(term in category for term in _PLACE_TERMS) for category in categories) or any(
        term in lead_text for term in _PLACE_TERMS
    ):
        candidates.append(("place", 0.92 if categories else 0.8, "place/geography signal"))
    if any(any(term in category for term in _FACILITY_TERMS) for category in categories) or any(
        term in lead_text or term in title_lc for term in _FACILITY_TERMS
    ):
        candidates.append(("facility", 0.9 if categories else 0.78, "facility signal"))
    if any(any(term in category for term in _PROJECT_TERMS) for category in categories) or any(
        term in lead_text or term in title_lc for term in _PROJECT_TERMS
    ):
        candidates.append(("project_institution", 0.9 if categories else 0.78, "project/institution signal"))

    if not candidates:
        return {"family": "general", "confidence": 0.55, "signals": ["fallback_general"]}
    family, confidence, signal = max(candidates, key=lambda item: item[1])
    return {"family": family, "confidence": round(confidence, 6), "signals": [signal]}


def _sentence_structural_reasons(text: str, *, page_family: str) -> list[str]:
    lower = text.lower()
    reasons: list[str] = []
    if ":" in text or text.count(",") >= 5 or ";" in text:
        reasons.append("list_like")
    if page_family == "species_taxonomy" and any(term in lower for term in ("species of", "wingspan", "larvae feed", "recorded from", "found in")):
        reasons.append("taxonomy_like")
    if re.search(r"\b\d+\s*(mm|cm|km|m|kg|%)\b", lower):
        reasons.append("measurement_like")
    if re.match(r"^(the|it|[A-Z][A-Za-z0-9' -]+)\s+(is|was)\s+(a|an|the)\b", text):
        reasons.append("descriptive_identity")
    return reasons


def _collect_surface_terms(event: Mapping[str, Any]) -> set[str]:
    terms: set[str] = set()
    for actor in event.get("actors") or []:
        norm = _normalized_surface(actor)
        if norm:
            terms.add(norm)
    for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
        for obj in event.get(field) or []:
            norm = _normalized_surface(obj)
            if norm:
                terms.add(norm)
    for step in event.get("steps") or []:
        if not isinstance(step, Mapping):
            continue
        for subject in step.get("subjects") or []:
            norm = _normalized_surface(subject)
            if norm:
                terms.add(norm)
        for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            for obj in step.get(field) or []:
                norm = _normalized_surface(obj)
                if norm:
                    terms.add(norm)
    for attr in event.get("attributions") or []:
        if not isinstance(attr, Mapping):
            continue
        for key in ("attributed_actor_id", "attribution_type"):
            norm = _normalized_surface(attr.get(key))
            if norm:
                terms.add(norm)
    return terms


def _score_abstention_calibration(
    article_sentences: list[Mapping[str, Any]],
    article_aao_rows: list[Mapping[str, Any]],
    *,
    page_family: str,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    event_by_id = {str(row.get("event_id") or ""): row for row in article_aao_rows}
    structural_sentence_count = 0
    forced_structural_event_count = 0
    abstained_structural_sentence_count = 0
    warnings: list[dict[str, Any]] = []
    for sentence in article_sentences:
        text = str(sentence.get("text") or "")
        reasons = _sentence_structural_reasons(text, page_family=page_family)
        if not reasons:
            continue
        structural_sentence_count += 1
        event = event_by_id.get(str(sentence.get("event_id") or ""))
        forced = bool(event) and _event_has_action(event)
        if forced:
            forced_structural_event_count += 1
            if len(warnings) < 5:
                warnings.append(
                    {
                        "event_id": str(sentence.get("event_id") or ""),
                        "reasons": reasons,
                        "text": text[:140],
                    }
                )
        else:
            abstained_structural_sentence_count += 1
    score = (
        _ratio(abstained_structural_sentence_count, structural_sentence_count)
        if structural_sentence_count
        else None
    )
    issues = ["forced_structural_extraction"] if forced_structural_event_count else []
    return (
        {
            "structural_sentence_count": structural_sentence_count,
            "abstained_structural_sentence_count": abstained_structural_sentence_count,
            "forced_structural_event_count": forced_structural_event_count,
            "abstention_calibration_score": score,
        },
        issues,
        warnings,
    )


def _score_link_relevance(
    article_sentences: list[Mapping[str, Any]],
    article_aao_rows: list[Mapping[str, Any]],
    *,
    follow_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    event_by_id = {str(row.get("event_id") or ""): row for row in article_aao_rows}
    total_sentence_link_count = 0
    relevant_sentence_link_count = 0
    relevant_link_titles: set[str] = set()
    for sentence in article_sentences:
        links = [str(link) for link in (sentence.get("links") or []) if str(link).strip()]
        if not links:
            continue
        total_sentence_link_count += len(links)
        event = event_by_id.get(str(sentence.get("event_id") or ""))
        if not isinstance(event, Mapping):
            continue
        terms = _collect_surface_terms(event)
        if not terms:
            continue
        for link in links:
            normalized_link = _normalized_surface(link)
            if any(_surface_match(normalized_link, term) for term in terms):
                relevant_sentence_link_count += 1
                relevant_link_titles.add(link)
    root_link_relevance_score = (
        _ratio(relevant_sentence_link_count, total_sentence_link_count)
        if total_sentence_link_count
        else None
    )
    followed_titles = [str(row.get("title") or "") for row in follow_rows if str(row.get("title") or "").strip()]
    followed_relevant_count = sum(
        1
        for title in followed_titles
        if any(_surface_match(_normalized_surface(title), _normalized_surface(link)) for link in relevant_link_titles)
    )
    followed_link_relevance_score = _ratio(followed_relevant_count, len(followed_titles)) if followed_titles else None
    issues: list[str] = []
    if total_sentence_link_count >= 3 and (root_link_relevance_score or 0.0) < 0.15:
        issues.append("low_link_relevance")
    return (
        {
            "sentence_link_count": total_sentence_link_count,
            "relevant_sentence_link_count": relevant_sentence_link_count,
            "root_link_relevance_score": root_link_relevance_score,
            "followed_link_count": len(followed_titles),
            "followed_relevant_count": followed_relevant_count,
            "followed_link_relevance_score": followed_link_relevance_score,
        },
        issues,
    )


def _score_claim_attribution_grounding(
    article_aao_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    claim_event_count = 0
    grounded_claim_event_count = 0
    attribution_event_count = 0
    grounded_attribution_event_count = 0
    for row in article_aao_rows:
        if bool(row.get("claim_bearing")):
            claim_event_count += 1
            if str(row.get("text") or "").strip() and (
                _event_has_action(row) or _event_has_actor(row) or bool(row.get("attributions"))
            ):
                grounded_claim_event_count += 1
        attributions = row.get("attributions") or []
        if isinstance(attributions, list) and attributions:
            attribution_event_count += 1
            attribution_grounded = str(row.get("text") or "").strip() != ""
            for attr in attributions:
                if not isinstance(attr, Mapping):
                    attribution_grounded = False
                    continue
                if not str(attr.get("attribution_type") or "").strip() and not str(
                    attr.get("attributed_actor_id") or ""
                ).strip():
                    attribution_grounded = False
            if attribution_grounded:
                grounded_attribution_event_count += 1
    denominator = claim_event_count + attribution_event_count
    score = (
        _ratio(grounded_claim_event_count + grounded_attribution_event_count, denominator)
        if denominator
        else None
    )
    issues = ["weak_claim_attribution_grounding"] if denominator and score != 1.0 else []
    return (
        {
            "claim_event_count": claim_event_count,
            "grounded_claim_event_count": grounded_claim_event_count,
            "attribution_event_count": attribution_event_count,
            "grounded_attribution_event_count": grounded_attribution_event_count,
            "claim_attribution_grounding_score": score,
        },
        issues,
    )


def _page_row_from_outputs(
    payload: Mapping[str, Any],
    article_state: Mapping[str, Any],
    timeline_row: Mapping[str, Any],
    reducer_row: Mapping[str, Any],
    *,
    follow_rows: list[Mapping[str, Any]] | None,
    max_follow_links_per_page: int,
) -> dict[str, Any]:
    sentence_rows = article_state.get("sentence_units")
    article_events = article_state.get("event_candidates")
    observation_rows = article_state.get("observations")
    timeline_projection = article_state.get("timeline_projection")
    article_sentences = [row for row in sentence_rows if isinstance(row, Mapping)] if isinstance(sentence_rows, list) else []
    article_aao_rows = [row for row in article_events if isinstance(row, Mapping)] if isinstance(article_events, list) else []
    observations = [row for row in observation_rows if isinstance(row, Mapping)] if isinstance(observation_rows, list) else []
    timeline_rows = [row for row in timeline_projection if isinstance(row, Mapping)] if isinstance(timeline_projection, list) else []
    follow_rows = [row for row in (follow_rows or []) if isinstance(row, Mapping)]
    page_profile = _classify_page_family(payload, article_sentences)
    page_family = str(page_profile["family"])

    article_sentence_count = len(article_sentences)
    article_aao_event_count = len(article_aao_rows)
    observation_count = len(observations)
    actor_event_count = sum(1 for row in article_aao_rows if _event_has_actor(row))
    action_event_count = sum(1 for row in article_aao_rows if _event_has_action(row))
    object_event_count = sum(1 for row in article_aao_rows if _event_has_object(row))
    step_count = sum(len(row.get("steps") or []) for row in article_aao_rows if isinstance(row.get("steps"), list))
    zero_step_event_count = sum(
        1 for row in article_aao_rows if not (isinstance(row.get("steps"), list) and len(row.get("steps") or []) > 0)
    )
    multi_step_event_count = sum(
        1 for row in article_aao_rows if isinstance(row.get("steps"), list) and len(row.get("steps") or []) > 1
    )
    claim_event_count = sum(1 for row in article_aao_rows if bool(row.get("claim_bearing")))
    attribution_event_count = sum(
        1 for row in article_aao_rows if isinstance(row.get("attributions"), list) and bool(row.get("attributions"))
    )
    unresolved_sentence_count = max(0, article_sentence_count - article_aao_event_count)
    sentence_retention_score = _ratio(article_aao_event_count, article_sentence_count)
    observation_density_score = _ratio(observation_count, article_sentence_count)
    actor_surface_score = _ratio(actor_event_count, article_aao_event_count)
    action_surface_score = _ratio(action_event_count, article_aao_event_count)
    object_surface_score = _ratio(object_event_count, article_aao_event_count)
    article_ingest_score = round(
        (sentence_retention_score + actor_surface_score + action_surface_score + object_surface_score) / 4.0,
        6,
    )
    explosion_score, explosion_metrics, explosion_issues = _score_observation_explosion(
        observation_count=observation_count,
        article_sentence_count=article_sentence_count,
        article_aao_event_count=article_aao_event_count,
    )
    text_hygiene_score, text_hygiene_warnings = _detect_text_hygiene(article_aao_rows)
    actor_action_binding_score, actor_action_bound_event_count, actor_action_action_event_count, actor_binding_issues = (
        _score_actor_action_binding(article_aao_rows)
    )
    object_binding_score, object_bound_event_count, object_action_event_count, object_binding_issues = (
        _score_object_binding(article_aao_rows)
    )
    honesty_multiplier = _mean(
        [
            explosion_score,
            text_hygiene_score,
            actor_action_binding_score,
            object_binding_score,
        ]
    )
    article_ingest_honest_score = round(article_ingest_score * honesty_multiplier, 6)
    density_metrics = {
        "observations_per_sentence": explosion_metrics["observations_per_sentence"],
        "observations_per_event": explosion_metrics["observations_per_event"],
        "steps_per_event": _ratio(step_count, article_aao_event_count),
        "multi_step_event_ratio": _ratio(multi_step_event_count, article_aao_event_count),
        "zero_step_event_ratio": _ratio(zero_step_event_count, article_aao_event_count),
    }

    anchor_status_counts: dict[str, int] = {}
    for row in timeline_rows:
        key = str(row.get("anchor_status") or "none")
        anchor_status_counts[key] = anchor_status_counts.get(key, 0) + 1
    timeline_honesty, timeline_honesty_issues = _timeline_honesty(timeline_rows)
    abstention_metrics, abstention_issues, abstention_warnings = _score_abstention_calibration(
        article_sentences,
        article_aao_rows,
        page_family=page_family,
    )
    link_metrics, link_relevance_issues = _score_link_relevance(
        article_sentences,
        article_aao_rows,
        follow_rows=follow_rows,
    )
    claim_attribution_metrics, claim_attr_issues = _score_claim_attribution_grounding(article_aao_rows)

    link_count = int(payload.get("links") and len(payload.get("links") or []) or 0)
    followed_snapshot_count = len(follow_rows)
    follow_budget_used_ratio = _ratio(followed_snapshot_count, max_follow_links_per_page) if max_follow_links_per_page else 0.0

    issues: list[str] = []
    if article_sentence_count == 0:
        issues.append("no_article_sentences")
    if article_sentence_count > 0 and article_aao_event_count == 0:
        issues.append("article_sentences_without_aao_events")
    if article_aao_event_count > 0 and actor_event_count == 0:
        issues.append("no_actor_surface")
    if article_aao_event_count > 0 and action_event_count == 0:
        issues.append("no_action_surface")
    if article_aao_event_count > 0 and object_event_count == 0:
        issues.append("no_object_surface")
    if max_follow_links_per_page > 0 and link_count > 0 and followed_snapshot_count == 0:
        issues.append("follow_budget_unused")
    honesty_issues = explosion_issues + actor_binding_issues + object_binding_issues + timeline_honesty_issues
    if text_hygiene_warnings:
        honesty_issues.append("text_hygiene_warning")
    calibration_scores = {
        "abstention_calibration_score": abstention_metrics["abstention_calibration_score"],
        "link_relevance_score": link_metrics["root_link_relevance_score"],
        "claim_attribution_grounding_score": claim_attribution_metrics["claim_attribution_grounding_score"],
    }
    calibration_multiplier = _mean_optional(
        [
            calibration_scores["abstention_calibration_score"],
            calibration_scores["link_relevance_score"],
            calibration_scores["claim_attribution_grounding_score"],
        ]
    )
    if calibration_multiplier is None:
        calibration_multiplier = 1.0
    calibration_multiplier = round(calibration_multiplier, 6)
    article_ingest_calibrated_score = round(article_ingest_honest_score * calibration_multiplier, 6)
    calibration_issues = abstention_issues + link_relevance_issues + claim_attr_issues

    return {
        "title": str(payload.get("title") or ""),
        "pageid": payload.get("pageid"),
        "revid": payload.get("revid"),
        "source_url": payload.get("source_url"),
        "article_sentence_count": article_sentence_count,
        "observation_count": observation_count,
        "article_aao_event_count": article_aao_event_count,
        "actor_event_count": actor_event_count,
        "action_event_count": action_event_count,
        "object_event_count": object_event_count,
        "step_count": step_count,
        "claim_event_count": claim_event_count,
        "attribution_event_count": attribution_event_count,
        "unresolved_sentence_count": unresolved_sentence_count,
        "link_count": link_count,
        "followed_snapshot_count": followed_snapshot_count,
        "followed_titles": [str(row.get("title") or "") for row in follow_rows[:10]],
        "scores": {
            "sentence_retention_score": sentence_retention_score,
            "observation_density_score": observation_density_score,
            "actor_surface_score": actor_surface_score,
            "action_surface_score": action_surface_score,
            "object_surface_score": object_surface_score,
            "article_ingest_score": article_ingest_score,
            "follow_budget_used_ratio": follow_budget_used_ratio,
        },
        "honesty_scores": {
            "observation_explosion_score": explosion_score,
            "text_hygiene_score": text_hygiene_score,
            "actor_action_binding_score": actor_action_binding_score,
            "object_binding_score": object_binding_score,
            "honesty_multiplier": honesty_multiplier,
            "article_ingest_honest_score": article_ingest_honest_score,
        },
        "calibration_scores": {
            **calibration_scores,
            "calibration_multiplier": calibration_multiplier,
            "article_ingest_calibrated_score": article_ingest_calibrated_score,
        },
        "density_metrics": density_metrics,
        "timeline_honesty": timeline_honesty,
        "page_profile": page_profile,
        "abstention_metrics": abstention_metrics,
        "abstention_warnings": abstention_warnings,
        "link_metrics": link_metrics,
        "claim_attribution_metrics": claim_attribution_metrics,
        "text_hygiene_warnings": text_hygiene_warnings,
        "article_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "order_index": int(row.get("order_index") or 0),
                "section": str(row.get("section") or ""),
                "text": str(row.get("text") or "")[:180],
                "links": list(row.get("links") or [])[:5],
                "anchor_status": str(row.get("anchor_status") or "none"),
            }
            for row in article_sentences[:3]
        ],
        "aao_preview": [
            {
                "event_id": str(row.get("event_id") or ""),
                "action": str(row.get("action") or ""),
                "actor_count": len(row.get("actors") or []) if isinstance(row.get("actors"), list) else 0,
                "step_count": len(row.get("steps") or []) if isinstance(row.get("steps"), list) else 0,
                "anchor_status": str(row.get("anchor_status") or "none"),
                "text": str(row.get("text") or "")[:180],
            }
            for row in article_aao_rows[:3]
        ],
        "canonical_state": {
            "sentence_unit_count": article_sentence_count,
            "observation_count": observation_count,
            "event_candidate_count": article_aao_event_count,
            "anchor_status_counts": anchor_status_counts,
        },
        "timeline_projection": {
            "event_count": len(timeline_rows),
            "anchor_status_counts": anchor_status_counts,
            "preview": [
                {
                    "event_id": str(row.get("event_id") or ""),
                    "order_index": int(row.get("order_index") or 0),
                    "anchor_status": str(row.get("anchor_status") or "none"),
                    "ordering_basis": str(row.get("ordering_basis") or "source_text_order"),
                    "text": str(row.get("text") or "")[:180],
                }
                for row in timeline_rows[:5]
            ],
        },
        "timeline_readiness": {
            "timeline_candidate_count": int(timeline_row.get("timeline_candidate_count") or 0),
            "dated_timeline_candidate_count": int(timeline_row.get("dated_timeline_candidate_count") or 0),
            "aao_event_count": int(timeline_row.get("aao_event_count") or 0),
            "scores": dict(timeline_row.get("scores") or {}),
            "issues": list(timeline_row.get("issues") or []),
        },
        "shared_reducer": {
            "structural_token_count": int(reducer_row.get("structural_token_count") or 0),
            "meaningful_lexeme_count": int(reducer_row.get("meaningful_lexeme_count") or 0),
            "meaningful_structure_count": int(reducer_row.get("meaningful_structure_count") or 0),
            "scores": dict(reducer_row.get("scores") or {}),
            "issues": list(reducer_row.get("issues") or []),
        },
        "issues": issues,
        "honesty_issues": honesty_issues,
        "calibration_issues": calibration_issues,
        "parser": article_state.get("parser"),
        "extraction_profile": article_state.get("extraction_profile"),
        "binding_counts": {
            "actor_action_bound_event_count": actor_action_bound_event_count,
            "actor_action_action_event_count": actor_action_action_event_count,
            "object_bound_event_count": object_bound_event_count,
            "object_action_event_count": object_action_event_count,
        },
    }


def score_snapshot_payload(
    payload: Mapping[str, Any],
    *,
    follow_rows: list[Mapping[str, Any]] | None = None,
    max_sentences: int = 400,
    max_events: int = 64,
    max_follow_links_per_page: int = 0,
    no_spacy: bool = False,
) -> dict[str, Any]:
    article_state = build_wiki_article_state(
        payload,
        max_sentences=max_sentences,
        max_events=max_events,
        no_spacy=no_spacy,
    )
    timeline_row = score_timeline_payload(payload, max_events=max_events, no_spacy=no_spacy)
    reducer_row = score_reducer_payload(payload)
    return _page_row_from_outputs(
        payload,
        article_state,
        timeline_row,
        reducer_row,
        follow_rows=follow_rows,
        max_follow_links_per_page=max_follow_links_per_page,
    )


def build_article_ingest_report(
    manifest: Mapping[str, Any],
    *,
    sample_limit: int | None = None,
    emit_page_rows: bool = True,
    max_sentences: int = 400,
    max_events: int = 64,
    no_spacy: bool = False,
) -> dict[str, Any]:
    sample_rows = manifest.get("samples")
    if not isinstance(sample_rows, list):
        raise ValueError("manifest samples must be a list")
    if sample_limit is not None:
        sample_rows = sample_rows[: max(0, int(sample_limit))]

    page_rows: list[dict[str, Any]] = []
    issue_counts: dict[str, int] = {}
    honesty_issue_counts: dict[str, int] = {}
    calibration_issue_counts: dict[str, int] = {}
    total_counts: dict[str, int] = {}
    score_sums = {
        "sentence_retention_score": 0.0,
        "observation_density_score": 0.0,
        "actor_surface_score": 0.0,
        "action_surface_score": 0.0,
        "object_surface_score": 0.0,
        "article_ingest_score": 0.0,
        "follow_budget_used_ratio": 0.0,
    }
    honesty_score_sums = {
        "observation_explosion_score": 0.0,
        "text_hygiene_score": 0.0,
        "actor_action_binding_score": 0.0,
        "object_binding_score": 0.0,
        "honesty_multiplier": 0.0,
        "article_ingest_honest_score": 0.0,
    }
    calibration_score_sums: dict[str, float] = defaultdict(float)
    calibration_score_counts: dict[str, int] = defaultdict(int)
    density_metric_sums = {
        "observations_per_sentence": 0.0,
        "observations_per_event": 0.0,
        "steps_per_event": 0.0,
        "multi_step_event_ratio": 0.0,
        "zero_step_event_ratio": 0.0,
    }
    timeline_honesty_sums = {
        "explicit_anchor_ratio": 0.0,
        "weak_anchor_ratio": 0.0,
        "none_anchor_ratio": 0.0,
        "timeline_honesty_score": 0.0,
    }
    timeline_honesty_page_count = 0
    page_family_counts: Counter[str] = Counter()
    page_family_score_sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    page_family_page_counts: Counter[str] = Counter()
    page_family_timeline_counts: Counter[str] = Counter()
    page_family_honesty_issue_counts: dict[str, Counter[str]] = defaultdict(Counter)
    page_family_calibration_issue_counts: dict[str, Counter[str]] = defaultdict(Counter)
    max_follow_links_per_page = int(manifest.get("max_follow_links_per_page") or 0)

    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        snapshot_path = row.get("snapshot_path")
        if not isinstance(snapshot_path, str):
            continue
        payload = _load_json(Path(snapshot_path))
        page_row = score_snapshot_payload(
            payload,
            follow_rows=list(row.get("followed_samples") or []),
            max_sentences=max_sentences,
            max_events=max_events,
            max_follow_links_per_page=max_follow_links_per_page,
            no_spacy=no_spacy,
        )
        page_rows.append(page_row)
        for issue in page_row["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for issue in page_row["honesty_issues"]:
            honesty_issue_counts[issue] = honesty_issue_counts.get(issue, 0) + 1
        for issue in page_row["calibration_issues"]:
            calibration_issue_counts[issue] = calibration_issue_counts.get(issue, 0) + 1
        family = str(page_row["page_profile"]["family"])
        for issue in page_row["honesty_issues"]:
            page_family_honesty_issue_counts[family][issue] += 1
        for issue in page_row["calibration_issues"]:
            page_family_calibration_issue_counts[family][issue] += 1
        for key in (
            "article_sentence_count",
            "observation_count",
            "article_aao_event_count",
            "actor_event_count",
            "action_event_count",
            "object_event_count",
            "step_count",
            "claim_event_count",
            "attribution_event_count",
            "followed_snapshot_count",
        ):
            total_counts[key] = total_counts.get(key, 0) + int(page_row[key])
        for key in score_sums:
            score_sums[key] += float(page_row["scores"][key])
        for key in honesty_score_sums:
            honesty_score_sums[key] += float(page_row["honesty_scores"][key])
        for key, value in page_row["calibration_scores"].items():
            if value is None:
                continue
            calibration_score_sums[key] += float(value)
            calibration_score_counts[key] += 1
        for key in density_metric_sums:
            density_metric_sums[key] += float(page_row["density_metrics"][key])
        timeline_honesty_row = page_row["timeline_honesty"]
        if timeline_honesty_row["timeline_honesty_score"] is not None:
            timeline_honesty_page_count += 1
            for key in timeline_honesty_sums:
                timeline_honesty_sums[key] += float(timeline_honesty_row[key])
        page_family_counts[family] += 1
        page_family_page_counts[family] += 1
        page_family_score_sums[family]["article_ingest_score"] += float(page_row["scores"]["article_ingest_score"])
        page_family_score_sums[family]["article_ingest_honest_score"] += float(
            page_row["honesty_scores"]["article_ingest_honest_score"]
        )
        page_family_score_sums[family]["article_ingest_calibrated_score"] += float(
            page_row["calibration_scores"]["article_ingest_calibrated_score"]
        )
        if timeline_honesty_row["timeline_honesty_score"] is not None:
            page_family_timeline_counts[family] += 1
            page_family_score_sums[family]["timeline_honesty_score"] += float(timeline_honesty_row["timeline_honesty_score"])

    page_count = len(page_rows)
    summary = {
        "page_count": page_count,
        "issue_counts": dict(sorted(issue_counts.items())),
        "honesty_issue_counts": dict(sorted(honesty_issue_counts.items())),
        "calibration_issue_counts": dict(sorted(calibration_issue_counts.items())),
        "total_counts": dict(sorted(total_counts.items())),
        "pages_with_article_sentences": sum(1 for row in page_rows if row["article_sentence_count"] > 0),
        "pages_with_article_aao_events": sum(1 for row in page_rows if row["article_aao_event_count"] > 0),
        "pages_with_actor_surface": sum(1 for row in page_rows if row["actor_event_count"] > 0),
        "pages_with_action_surface": sum(1 for row in page_rows if row["action_event_count"] > 0),
        "pages_with_followed_snapshots": sum(1 for row in page_rows if row["followed_snapshot_count"] > 0),
        "average_scores": {key: round((value / page_count), 6) if page_count else 0.0 for key, value in score_sums.items()},
        "average_honesty_scores": {
            key: round((value / page_count), 6) if page_count else 0.0 for key, value in honesty_score_sums.items()
        },
        "average_calibration_scores": {
            key: round((calibration_score_sums[key] / calibration_score_counts[key]), 6)
            if calibration_score_counts[key]
            else None
            for key in sorted(calibration_score_sums.keys() | calibration_score_counts.keys())
        },
        "pages_with_calibration_metric": dict(sorted(calibration_score_counts.items())),
        "average_density_metrics": {
            key: round((value / page_count), 6) if page_count else 0.0 for key, value in density_metric_sums.items()
        },
        "pages_with_timeline_honesty": timeline_honesty_page_count,
        "average_timeline_honesty": {
            key: round((value / timeline_honesty_page_count), 6) if timeline_honesty_page_count else 0.0
            for key, value in timeline_honesty_sums.items()
        },
        "page_family_counts": dict(sorted(page_family_counts.items())),
        "page_family_average_scores": {
            family: {
                "page_count": page_family_page_counts[family],
                "pages_with_timeline_honesty": page_family_timeline_counts[family],
                "article_ingest_score": round(
                    page_family_score_sums[family]["article_ingest_score"] / page_family_page_counts[family],
                    6,
                ),
                "article_ingest_honest_score": round(
                    page_family_score_sums[family]["article_ingest_honest_score"] / page_family_page_counts[family],
                    6,
                ),
                "article_ingest_calibrated_score": round(
                    page_family_score_sums[family]["article_ingest_calibrated_score"] / page_family_page_counts[family],
                    6,
                ),
                "timeline_honesty_score": round(
                    page_family_score_sums[family]["timeline_honesty_score"] / page_family_timeline_counts[family],
                    6,
                )
                if page_family_timeline_counts[family]
                else None,
            }
            for family in sorted(page_family_page_counts)
        },
        "page_family_honesty_issue_counts": {
            family: dict(sorted(counter.items()))
            for family, counter in sorted(page_family_honesty_issue_counts.items())
        },
        "page_family_calibration_issue_counts": {
            family: dict(sorted(counter.items()))
            for family, counter in sorted(page_family_calibration_issue_counts.items())
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest.get("generated_at"),
        "manifest": {
            "wiki": manifest.get("wiki"),
            "requested_count": manifest.get("requested_count"),
            "sampled_count": manifest.get("sampled_count"),
            "namespace": manifest.get("namespace"),
            "follow_hops": int(manifest.get("follow_hops") or 0),
            "max_follow_links_per_page": max_follow_links_per_page,
        },
        "supported_surface": {
            "canonical_state_surface": "wiki_article_state_v0_1",
            "article_sentence_surface": "full_article_sentence_rows",
            "event_candidate_surface": "wiki_timeline_aoo_extract",
            "timeline_surface": "wiki_random_timeline_readiness_report_v0_1",
            "shared_reducer_surface": "diagnostic_companion",
            "spacy_enabled": not no_spacy,
            "max_sentences": int(max_sentences),
            "max_events": int(max_events),
        },
        "summary": summary,
        "pages": page_rows if emit_page_rows else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score stored random-page Wikipedia snapshots for article-wide ingest coverage."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--emit-page-rows", action="store_true")
    parser.add_argument("--fail-on-empty", action="store_true")
    parser.add_argument("--max-sentences", type=int, default=400)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--no-spacy", action="store_true")
    args = parser.parse_args(argv)

    manifest = _load_json(args.manifest)
    report = build_article_ingest_report(
        manifest,
        sample_limit=args.sample_limit,
        emit_page_rows=args.emit_page_rows,
        max_sentences=args.max_sentences,
        max_events=args.max_events,
        no_spacy=args.no_spacy,
    )
    if args.fail_on_empty and report["summary"]["page_count"] == 0:
        raise SystemExit("no pages scored")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
