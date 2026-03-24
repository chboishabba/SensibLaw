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


SCHEMA_VERSION = "wiki_random_article_ingest_coverage_report_v0_11"

_NO_SPACE_SENTENCE_JOIN_RE = re.compile(r"[.!?][A-Z][a-z]")
_CAMEL_GLUE_RE = re.compile(r"\b[a-z]{4,}[A-Z][a-z]{2,}\b")
_CITATION_TAIL_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]\s*$")
_METADATA_TAIL_RE = re.compile(r"(?:\s+[|;]\s*[A-Za-z0-9_()/-]+){1,}\s*$")
_TEMPLATE_RESIDUE_MARKERS = ("{{", "}}", "[[", "]]", "thumb|", "File:", "Image:", "px|")
_CATEGORY_LINE_RE = re.compile(r"\[\[\s*category:[^\]]+\]\]", re.IGNORECASE)
_DEFAULTSORT_RE = re.compile(r"\{\{\s*defaultsort:[^}]+\}\}", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_BIOGRAPHY_CATEGORY_TERMS = (" births", " deaths", "people", "biography")
_PLACE_TERMS = ("city", "town", "village", "county", "district", "province", "state", "metropolitan area")
_FACILITY_TERMS = ("complex", "stadium", "hotel", "airport", "museum", "building", "arena", "bridge")
_PROJECT_TERMS = ("project", "repository", "organization", "organisation", "authority", "company", "institution")
_SPECIES_CATEGORY_TERMS = ("species", "moths", "birds", "plants", "taxa", "genera", "fauna")
_LIST_TEXT_MARKERS = (
    "list of",
    "may refer to",
    "disambiguation",
    "index of",
    "outline of",
    "partial list",
)
_TITLE_AGGREGATION_MARKERS = (
    "list of ",
    "index of ",
    "outline of ",
    "timeline of ",
)
_TITLE_AGGREGATION_SUFFIXES = (
    " by year",
    " by country",
    " by state",
)
_WARNING_AGGREGATION_MARKERS = (
    "partial_lists_continue_present",
)
_TITLE_BROAD_ADMIN_TERMS = (
    "district",
    "electoral district",
    "municipality",
    "county",
    "province",
    "state",
    "gmina",
    "voivodeship",
)
_TITLE_UMBRELLA_TERMS = (
    "championship",
    "championships",
    "tournament",
    "tournaments",
    "cup",
    "league",
    "season",
    "seasons",
    "spill",
)
_GENERIC_UMBRELLA_TERMS = (
    "competition",
    "election",
    "series",
    "event",
    "games",
    "games tournament",
    "tour",
    "conference",
)
_YEAR_AGGREGATION_TITLE_RE = re.compile(
    r"^(?:\d{3,4}(?:s)?|(?:early|mid|late)\s+\d{1,2}(?:st|nd|rd|th)\s+century)\s+in\s+"
)
_KEY_TERM_STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "also",
    "among",
    "and",
    "are",
    "around",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "could",
    "did",
    "does",
    "during",
    "each",
    "for",
    "from",
    "has",
    "have",
    "having",
    "here",
    "into",
    "its",
    "may",
    "more",
    "most",
    "not",
    "of",
    "on",
    "only",
    "or",
    "other",
    "over",
    "page",
    "pageid",
    "revid",
    "said",
    "she",
    "should",
    "some",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "title",
    "under",
    "until",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "would",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not value:
        return ""
    return str(value).strip()


def _extract_wikitext(snapshot: Mapping[str, Any]) -> str:
    root_value = snapshot.get("wikitext")
    if isinstance(root_value, str):
        return " ".join(root_value.split()).strip()

    if isinstance(root_value, Mapping):
        for key in ("*", "wikitext", "content", "text"):
            value = _to_text(root_value.get(key))
            if value:
                return value
        # Some payloads may carry page objects as a one-element list/dict wrapper.
        for key in ("revisions", "pages", "query"):
            value = root_value.get(key)
            extracted = _extract_wikitext_from_iterable(value) if value is not None else ""
            if extracted:
                return extracted

    extracted = _extract_wikitext_from_iterable(root_value)
    if extracted:
        return extracted
    return ""


def _extract_wikitext_from_iterable(value: Any) -> str:
    if isinstance(value, Mapping):
        for nested in value.values():
            text = _extract_wikitext({"wikitext": nested})
            if text:
                return text
        return ""
    if isinstance(value, list | tuple):
        for item in value:
            text = _extract_wikitext({"wikitext": item})
            if text:
                return text
    return ""


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / float(len(values)), 6)


def _mean_optional(values: list[float | None]) -> float | None:
    kept = [float(value) for value in values if value is not None]
    if not kept:
        return None
    return round(sum(kept) / float(len(kept)), 6)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _regime_weighted_deficit_score(score: float | None, weight: float) -> float | None:
    if score is None:
        return None
    weight = _clamp01(weight)
    return round(1.0 - ((1.0 - float(score)) * weight), 6)


def _linear_descending_score(value: float, *, good: float, bad: float) -> float:
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    if bad <= good:
        return 0.0
    return round(1.0 - ((value - good) / (bad - good)), 6)


def jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {str(item).strip().lower() for item in left if str(item).strip()}
    right_set = {str(item).strip().lower() for item in right if str(item).strip()}
    if not left_set and not right_set:
        return 0.0
    if not left_set or not right_set:
        return 0.0
    overlap = len(left_set & right_set)
    union = len(left_set | right_set)
    return round(float(overlap) / float(union), 6) if union else 0.0


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


def _tokenize_key_terms(text: Any) -> list[str]:
    normalized = _normalized_surface(text)
    if not normalized:
        return []
    return [
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in _KEY_TERM_STOPWORDS and not token.isdigit()
    ]


def extract_key_terms(article_state: Mapping[str, Any], *, limit: int = 40) -> list[str]:
    existing_terms = article_state.get("key_terms") if isinstance(article_state, Mapping) else None
    if isinstance(existing_terms, list) and any(str(term).strip() for term in existing_terms):
        terms = [str(term).strip().lower() for term in existing_terms if str(term).strip()]
        return terms[: max(0, int(limit))]
    counter: Counter[str] = Counter()
    article = article_state.get("article") if isinstance(article_state, Mapping) else None
    if isinstance(article, Mapping):
        for token in _tokenize_key_terms(article.get("title")):
            counter[token] += 2
    for token in _tokenize_key_terms(article_state.get("title")):
        counter[token] += 2
    for sentence in article_state.get("sentence_units") or []:
        if not isinstance(sentence, Mapping):
            continue
        for token in _tokenize_key_terms(sentence.get("section")):
            counter[token] += 1
        for token in _tokenize_key_terms(sentence.get("text")):
            counter[token] += 1
        for link in sentence.get("links") or []:
            for token in _tokenize_key_terms(link):
                counter[token] += 2
    for event in article_state.get("event_candidates") or []:
        if not isinstance(event, Mapping):
            continue
        for token in _tokenize_key_terms(event.get("action")):
            counter[token] += 2
        for actor in event.get("actors") or []:
            for token in _tokenize_key_terms(actor):
                counter[token] += 2
        for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            for obj in event.get(field) or []:
                for token in _tokenize_key_terms(obj):
                    counter[token] += 2
    terms = [token for token, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[: max(0, int(limit))]]
    return terms


def compute_richness_score(state: Mapping[str, Any]) -> float:
    sentence_count = int(state.get("article_sentence_count") or len(state.get("sentence_units") or []))
    observation_count = int(state.get("observation_count") or len(state.get("observations") or []))
    event_count = int(state.get("article_aao_event_count") or len(state.get("event_candidates") or []))
    sentence_score = min(1.0, sentence_count / 40.0)
    observation_score = min(1.0, observation_count / 25.0)
    event_score = min(1.0, event_count / 15.0)
    return _clamp01(round(0.5 * sentence_score + 0.3 * observation_score + 0.2 * event_score, 6))


def _follow_structure_counts(state: Mapping[str, Any]) -> tuple[int, int, int]:
    sentence_count = int(state.get("article_sentence_count") or len(state.get("sentence_units") or []))
    observation_count = int(state.get("observation_count") or len(state.get("observations") or []))
    event_count = int(state.get("article_aao_event_count") or len(state.get("event_candidates") or []))
    return sentence_count, observation_count, event_count


def compute_content_lift_profile(root_state: Mapping[str, Any], follow_state: Mapping[str, Any]) -> dict[str, Any]:
    root_terms = set(extract_key_terms(root_state or {})[:12])
    follow_terms = extract_key_terms(follow_state)[:12]
    novel_follow_terms = [term for term in follow_terms if term not in root_terms]

    event_count = int(follow_state.get("article_aao_event_count") or len(follow_state.get("event_candidates") or []))
    action_event_count = int(follow_state.get("action_event_count") or event_count)
    object_event_count = int(follow_state.get("object_event_count") or 0)
    claim_event_count = int(follow_state.get("claim_event_count") or 0)
    attribution_event_count = int(follow_state.get("attribution_event_count") or 0)

    relation_surface_score = _clamp01(
        round(
            0.45 * _ratio(action_event_count, event_count)
            + 0.35 * _ratio(object_event_count, event_count)
            + 0.20 * _ratio(claim_event_count + attribution_event_count, event_count),
            6,
        )
        if event_count
        else 0.0
    )
    novel_term_support_score = _clamp01(round(min(1.0, len(novel_follow_terms) / 4.0), 6))
    content_lift_score = _clamp01(
        round(0.65 * relation_surface_score + 0.35 * novel_term_support_score, 6)
    )
    reason_markers: list[str] = []
    if relation_surface_score >= 0.5:
        reason_markers.append("relation_bearing_lift")
    if novel_term_support_score >= 0.5:
        reason_markers.append("novel_term_lift")
    if event_count and _ratio(claim_event_count + attribution_event_count, event_count) >= 0.25:
        reason_markers.append("epistemic_lift")
    return {
        "relation_surface_score": relation_surface_score,
        "novel_term_support_score": novel_term_support_score,
        "content_lift_score": content_lift_score,
        "content_lift_reason_markers": reason_markers,
    }


def _canonicalize_follow_text_for_listiness(raw_text: str) -> str:
    cleaned = _CATEGORY_LINE_RE.sub(" ", raw_text)
    cleaned = _DEFAULTSORT_RE.sub(" ", cleaned)
    return cleaned


def _token_overlap_ratio(left_tokens: list[str], right_tokens: list[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    left = set(left_tokens)
    right = set(right_tokens)
    return round(len(left & right) / max(1, min(len(left), len(right))), 6)


def _normalize_terms(value: Any) -> list[str]:
    tokens = [token for token in _tokenize_key_terms(_to_text(value)) if token]
    return tokens


def _is_parent_child_generalization(follow_title: str, root_title: str) -> bool:
    follow_norm = _to_text(follow_title).lower()
    root_norm = _to_text(root_title).lower()
    if not follow_norm or not root_norm or follow_norm == root_norm:
        return False
    if len(follow_norm) <= len(root_norm) and root_norm.startswith(follow_norm + " "):
        return True
    if len(follow_norm) >= len(root_norm) and follow_norm.startswith(root_norm + " "):
        return True
    if root_norm and follow_norm and follow_norm in root_norm:
        follow_tokens = _normalize_terms(follow_title)
        root_tokens = _normalize_terms(root_title)
        if not follow_tokens or not root_tokens:
            return False
        overlap = _token_overlap_ratio(follow_tokens, root_tokens)
        if overlap >= 0.5 and len(follow_tokens) <= len(root_tokens):
            return True
    return False


def _tokens_lexically_related(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 5 and len(right) >= 5:
        return left.startswith(right[:5]) or right.startswith(left[:5])
    return False


def _derive_specificity_profile(
    root_state: Mapping[str, Any] | None,
    follow_state: Mapping[str, Any],
) -> dict[str, Any]:
    follow_title = str(follow_state.get("title") or "").strip()
    root_title = str((root_state or {}).get("title") or "").strip()
    if not follow_title:
        return {
            "specificity_title_markers": [],
            "specificity_lexical_markers": [],
            "specificity_no_lift_markers": [],
            "specificity_signal_weight": 0.0,
            "primary_specificity_reason": None,
            "title_overlap_ratio": 0.0,
            "term_overlap_ratio": 0.0,
            "novel_follow_term_count": 0,
        }
    lower_follow_title = follow_title.lower()
    lower_root_title = root_title.lower()
    follow_title_tokens = _tokenize_key_terms(follow_title)
    root_title_tokens = _tokenize_key_terms(root_title)
    root_terms = extract_key_terms(root_state or {})
    follow_terms = extract_key_terms(follow_state)

    title_markers: list[str] = []
    lexical_markers: list[str] = []
    no_lift_markers: list[str] = []

    if "," in follow_title and "," in root_title:
        follow_tail = lower_follow_title.split(",", 1)[1].strip()
        root_tail = lower_root_title.split(",", 1)[1].strip()
        if follow_tail and root_tail and follow_tail == root_tail:
            title_markers.append("shared_tail_locality_sibling")
    if any(term in lower_follow_title for term in _TITLE_BROAD_ADMIN_TERMS):
        title_markers.append("broad_admin_title")
    if any(term in lower_follow_title for term in _TITLE_UMBRELLA_TERMS):
        title_markers.append("umbrella_title")
    if any(term in lower_follow_title for term in _GENERIC_UMBRELLA_TERMS):
        title_markers.append("generic_umbrella_title")
    if _is_parent_child_generalization(follow_title, root_title):
        title_markers.append("parent_child_generalization")
    if re.match(r"^\d{4}\s+", follow_title):
        title_markers.append("year_prefixed_title")

    title_overlap = _token_overlap_ratio(follow_title_tokens, root_title_tokens)
    term_overlap = _token_overlap_ratio(follow_terms[:12], root_terms[:12])
    novel_follow_terms = [term for term in follow_terms[:12] if term not in set(root_terms[:12])]

    if root_title and follow_title and root_title != follow_title and title_overlap >= 0.5:
        lexical_markers.append("title_overlap_generalization")
    if len(follow_title_tokens) <= 2 and term_overlap >= 0.5 and len(root_title_tokens) >= len(follow_title_tokens):
        lexical_markers.append("short_broad_generalization")
    if (
        len(follow_title_tokens) == 1
        and root_title_tokens
        and any(
            _tokens_lexically_related(follow_title_tokens[0], token)
            for token in root_title_tokens + root_terms[:12]
        )
    ):
        lexical_markers.append("short_broad_generalization")
    if follow_title_tokens and root_terms and all(token in set(root_terms) for token in follow_title_tokens):
        lexical_markers.append("title_tokens_contained_in_root_terms")

    if term_overlap >= 0.5 and len(novel_follow_terms) <= 2:
        no_lift_markers.append("same_neighborhood_low_lift")
    if len(novel_follow_terms) <= 1 and len(follow_terms[:12]) >= 3 and term_overlap >= 0.34:
        no_lift_markers.append("few_novel_terms")
    if (
        "parent_child_generalization" in title_markers
        and term_overlap >= 0.5
        and len(novel_follow_terms) <= 3
    ):
        no_lift_markers.append("parent_child_no_lift")

    title_markers = list(dict.fromkeys(title_markers))
    lexical_markers = list(dict.fromkeys(lexical_markers))
    no_lift_markers = list(dict.fromkeys(no_lift_markers))

    weighted_hits = 0.0
    weighted_hits += 1.0 * float(len(title_markers))
    for marker in lexical_markers:
        if marker == "short_broad_generalization":
            weighted_hits += 1.5
        elif marker == "title_overlap_generalization":
            weighted_hits += 1.0
        else:
            weighted_hits += 0.75
    if "parent_child_generalization" in title_markers:
        weighted_hits += 1.25
    weighted_hits += 0.75 * float(len(no_lift_markers))
    if title_markers:
        primary_reason = title_markers[0]
    elif lexical_markers:
        primary_reason = lexical_markers[0]
    elif no_lift_markers:
        primary_reason = no_lift_markers[0]
    else:
        primary_reason = None
    return {
        "specificity_title_markers": title_markers,
        "specificity_lexical_markers": lexical_markers,
        "specificity_no_lift_markers": no_lift_markers,
        "specificity_signal_weight": round(weighted_hits, 6),
        "primary_specificity_reason": primary_reason,
        "title_overlap_ratio": title_overlap,
        "term_overlap_ratio": term_overlap,
        "novel_follow_term_count": len(novel_follow_terms),
    }


def _classify_follow_list_subtype(
    non_list_profile: Mapping[str, Any],
    information_gain_profile: Mapping[str, Any],
    *,
    richness_score: float,
) -> dict[str, Any]:
    list_text_markers = set(non_list_profile.get("list_text_markers") or [])
    list_warning_markers = set(non_list_profile.get("list_warning_markers") or [])
    title_markers = set(non_list_profile.get("specificity_title_markers") or [])
    lexical_markers = set(non_list_profile.get("specificity_lexical_markers") or [])
    information_gain_score = float(information_gain_profile.get("information_gain_score") or 0.0)
    content_lift_score = float(information_gain_profile.get("content_lift_score") or 0.0)
    non_list_score = float(non_list_profile.get("non_list_score") or 0.0)

    list_title_markers = set(non_list_profile.get("list_title_markers") or [])
    has_title_aggregation = bool(list_title_markers)
    has_list_text = bool(list_text_markers)
    has_warning_markers = bool(list_warning_markers)
    has_disambiguation = "disambiguation_title" in list_title_markers
    has_structural = has_list_text or has_warning_markers or has_disambiguation or has_title_aggregation

    if has_structural:
        return {
            "list_follow_subtype": "structural_list_like",
            "list_like_penalty_active": non_list_score <= 0.25,
            "list_like_penalty_reason": "structural_list_signature",
        }

    if (
        "shared_tail_locality_sibling" in title_markers
        and richness_score >= 0.25
        and (information_gain_score >= 0.35 or content_lift_score >= 0.45)
    ):
        return {
            "list_follow_subtype": "contentful_locality_continuation",
            "list_like_penalty_active": False,
            "list_like_penalty_reason": None,
        }

    if (
        "title_overlap_generalization" in lexical_markers
        and "same_neighborhood_low_lift" not in set(non_list_profile.get("specificity_no_lift_markers") or [])
        and (content_lift_score >= 0.45 or information_gain_score >= 0.40)
    ):
        return {
            "list_follow_subtype": "contentful_regime_adjacency",
            "list_like_penalty_active": False,
            "list_like_penalty_reason": None,
        }

    if (
        "parent_child_generalization" in title_markers
        and non_list_score <= 0.35
        and (information_gain_score < 0.50 or content_lift_score < 0.60)
    ):
        return {
            "list_follow_subtype": "parent_child_aggregation",
            "list_like_penalty_active": True,
            "list_like_penalty_reason": "parent_child_generalization_with_weak_lift",
        }

    if (
        "umbrella_title" in title_markers
        and information_gain_score >= 0.40
        and content_lift_score >= 0.45
    ):
        return {
            "list_follow_subtype": "seasonal_or_domain_continuation",
            "list_like_penalty_active": False,
            "list_like_penalty_reason": None,
        }

    if (
        not has_structural
        and information_gain_score < 0.35
        and (
            "umbrella_title" in title_markers
            or "generic_umbrella_title" in title_markers
            or "year_prefixed_title" in title_markers
            or "short_broad_generalization" in lexical_markers
            or "title_overlap_generalization" in lexical_markers
            or "broad_admin_title" in title_markers
        )
    ):
        return {
            "list_follow_subtype": "generic_continuation_routing_to_low_information",
            "list_like_penalty_active": False,
            "list_like_penalty_reason": None,
        }

    if non_list_score <= 0.25:
        return {
            "list_follow_subtype": "weak_specificity_continuation",
            "list_like_penalty_active": True,
            "list_like_penalty_reason": "low_specificity_signal_with_weak_content",
        }

    return {
        "list_follow_subtype": "high_specificity_continuation",
        "list_like_penalty_active": False,
        "list_like_penalty_reason": None,
    }


def compute_non_list_profile(
    state: Mapping[str, Any],
    *,
    root_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_text = str(state.get("raw_text") or state.get("source_text") or state.get("wikitext") or "")
    raw_text = _canonicalize_follow_text_for_listiness(raw_text).lower()
    title = str(state.get("title") or "").strip()
    lower_title = title.lower()
    warnings = [str(item).strip().lower() for item in (state.get("snapshot_warnings") or state.get("warnings") or []) if str(item).strip()]

    text_markers = [marker for marker in _LIST_TEXT_MARKERS if marker in raw_text]
    title_markers = [marker.strip() for marker in _TITLE_AGGREGATION_MARKERS if lower_title.startswith(marker)]
    if "(disambiguation)" in lower_title:
        title_markers.append("disambiguation_title")
    if _YEAR_AGGREGATION_TITLE_RE.search(lower_title):
        title_markers.append("year_in_title")
    for suffix in _TITLE_AGGREGATION_SUFFIXES:
        if lower_title.endswith(suffix):
            title_markers.append(suffix.strip())
    warning_markers = [marker for marker in _WARNING_AGGREGATION_MARKERS if marker in warnings]
    specificity_profile = _derive_specificity_profile(root_state, state)

    weighted_hits = (
        float(len(text_markers))
        + 1.25 * float(len(title_markers))
        + 1.0 * float(len(warning_markers))
        + float(specificity_profile["specificity_signal_weight"])
    )
    listiness = min(1.0, weighted_hits / 2.0)
    return {
        "non_list_score": round(1.0 - listiness, 6),
        "listiness": round(listiness, 6),
        "list_signal_weight": round(weighted_hits, 6),
        "list_text_markers": text_markers,
        "list_title_markers": title_markers,
        "list_warning_markers": warning_markers,
        **specificity_profile,
    }


def compute_non_list_score(state: Mapping[str, Any]) -> float:
    return float(compute_non_list_profile(state)["non_list_score"])


def compute_regime_similarity_score(root_state: Mapping[str, Any], follow_state: Mapping[str, Any]) -> float:
    root_regime = _coerce_regime_vector(root_state)
    follow_regime = _coerce_regime_vector(follow_state)
    return round(
        min(
            1.0,
            (
                float(root_regime.get("narrative") or 0.0) * float(follow_regime.get("narrative") or 0.0)
                + float(root_regime.get("descriptive") or 0.0) * float(follow_regime.get("descriptive") or 0.0)
                + float(root_regime.get("formal") or 0.0) * float(follow_regime.get("formal") or 0.0)
            ),
        ),
        6,
    )


def compute_information_gain_profile(root_state: Mapping[str, Any], follow_state: Mapping[str, Any]) -> dict[str, Any]:
    root_terms = extract_key_terms(root_state)
    follow_terms = extract_key_terms(follow_state)
    overlap = jaccard_similarity(root_terms, follow_terms)
    if overlap < 0.15:
        base_score = round((overlap / 0.15) * 0.5, 6)
    elif overlap <= 0.55:
        base_score = round(0.5 + (((overlap - 0.15) / 0.40) * 0.5), 6)
    elif overlap <= 0.85:
        base_score = round(1.0 - (((overlap - 0.55) / 0.30) * 0.5), 6)
    else:
        base_score = 0.5

    specificity = _derive_specificity_profile(root_state, follow_state)
    penalty = 0.0
    reason_markers: list[str] = []
    penalty_markers: list[str] = []

    title_markers = set(specificity["specificity_title_markers"])
    lexical_markers = set(specificity["specificity_lexical_markers"])
    no_lift_markers = set(specificity["specificity_no_lift_markers"])
    content_lift = compute_content_lift_profile(root_state, follow_state)
    novelty_floor_triggered = int(specificity["novel_follow_term_count"]) <= 1 and float(specificity["term_overlap_ratio"]) >= 0.34
    title_overlap_ratio = float(specificity["title_overlap_ratio"])
    low_lift_evidence = bool(no_lift_markers) or novelty_floor_triggered or float(content_lift["content_lift_score"]) < 0.34
    generic_breadth_signal = (
        bool(title_markers & {"umbrella_title", "generic_umbrella_title", "year_prefixed_title"})
        and title_overlap_ratio >= 0.5
        and int(specificity["novel_follow_term_count"]) <= 4
        and float(content_lift["content_lift_score"]) < 0.55
    )
    weak_root_overlap = (
        float(specificity["term_overlap_ratio"]) <= 0.12
        and float(content_lift["content_lift_score"]) >= 0.63
        and int(specificity["novel_follow_term_count"]) >= 6
        and not (title_markers or lexical_markers)
    )

    if generic_breadth_signal:
        reason_markers.append("generic_breadth")


    if "year_prefixed_title" in title_markers:
        reason_markers.append("year_prefixed_title")
        if low_lift_evidence:
            penalty += 0.08
            penalty_markers.append("year_prefixed_title")
    if "umbrella_title" in title_markers:
        reason_markers.append("umbrella_title")
        if low_lift_evidence:
            penalty += 0.08
            penalty_markers.append("umbrella_title")
        if generic_breadth_signal and "generic_breadth" not in penalty_markers:
            penalty += 0.06
            penalty_markers.append("generic_breadth")
    if "short_broad_generalization" in lexical_markers:
        reason_markers.append("short_broad_generalization")
        if low_lift_evidence:
            penalty += 0.10
            penalty_markers.append("short_broad_generalization")
    if "title_overlap_generalization" in lexical_markers:
        reason_markers.append("title_overlap_generalization")
        if float(specificity["term_overlap_ratio"]) >= 0.45 and int(specificity["novel_follow_term_count"]) <= 2:
            penalty += 0.06
            if "title_overlap_no_lift" not in penalty_markers:
                penalty_markers.append("title_overlap_no_lift")
        if low_lift_evidence:
            penalty += 0.06
            penalty_markers.append("title_overlap_generalization")
    if "title_tokens_contained_in_root_terms" in lexical_markers:
        reason_markers.append("title_tokens_contained_in_root_terms")
        if low_lift_evidence:
            penalty += 0.05
            penalty_markers.append("title_tokens_contained_in_root_terms")
    if "broad_admin_title" in title_markers:
        reason_markers.append("broad_admin_title")
        if low_lift_evidence or int(specificity["novel_follow_term_count"]) <= 2:
            penalty += 0.06
            if "broad_admin_title" not in penalty_markers:
                penalty_markers.append("broad_admin_title")
    if "generic_umbrella_title" in title_markers:
        reason_markers.append("generic_umbrella_title")
        if low_lift_evidence:
            penalty += 0.07
            penalty_markers.append("generic_umbrella_title")
        if generic_breadth_signal and "generic_breadth" not in penalty_markers:
            penalty += 0.06
            penalty_markers.append("generic_breadth")
    if "parent_child_generalization" in title_markers:
        reason_markers.append("parent_child_generalization")
        if low_lift_evidence or "same_neighborhood_low_lift" in no_lift_markers:
            penalty += 0.10
            penalty_markers.append("parent_child_generalization")
        if generic_breadth_signal and "generic_breadth" not in penalty_markers:
            penalty += 0.06
            penalty_markers.append("generic_breadth")
    if "same_neighborhood_low_lift" in no_lift_markers:
        reason_markers.append("same_neighborhood_low_lift")
        penalty += 0.16
        penalty_markers.append("same_neighborhood_low_lift")
    if "few_novel_terms" in no_lift_markers:
        reason_markers.append("few_novel_terms")
        penalty += 0.08
        penalty_markers.append("few_novel_terms")
    if novelty_floor_triggered:
        reason_markers.append("novelty_floor_penalty")
        penalty += 0.06
        penalty_markers.append("novelty_floor_penalty")
    if weak_root_overlap:
        reason_markers.append("weak_root_term_overlap")
        penalty += 0.12
        if "weak_root_term_overlap" not in penalty_markers:
            penalty_markers.append("weak_root_term_overlap")

    penalty = round(min(0.6, penalty), 6)
    content_lift_bonus = 0.0
    if not penalty_markers and float(content_lift["content_lift_score"]) >= 0.45:
        content_lift_bonus = round(min(0.12, (float(content_lift["content_lift_score"]) - 0.45) * 0.30), 6)
    score = _clamp01(round(base_score - penalty + content_lift_bonus, 6))
    primary_reason = reason_markers[0] if reason_markers else None
    return {
        "information_gain_score": score,
        "base_information_gain_score": base_score,
        "term_overlap": overlap,
        "content_lift_score": float(content_lift["content_lift_score"]),
        "relation_surface_score": float(content_lift["relation_surface_score"]),
        "novel_term_support_score": float(content_lift["novel_term_support_score"]),
        "content_lift_bonus": content_lift_bonus,
        "content_lift_reason_markers": list(content_lift["content_lift_reason_markers"]),
        "information_gain_penalty": penalty,
        "information_gain_reason_markers": reason_markers,
        "information_gain_penalty_markers": penalty_markers,
        "primary_information_gain_reason": primary_reason,
    }


def compute_information_gain_score(root_state: Mapping[str, Any], follow_state: Mapping[str, Any]) -> float:
    return float(compute_information_gain_profile(root_state, follow_state)["information_gain_score"])


def _prefer_low_information_primary_bucket(
    *,
    follow_state: Mapping[str, Any],
    richness_score: float,
    non_list_profile: Mapping[str, Any],
    information_gain_profile: Mapping[str, Any],
    list_like_profile: Mapping[str, Any],
) -> bool:
    sentence_count, observation_count, event_count = _follow_structure_counts(follow_state)
    is_true_stub = (
        richness_score < 0.12
        and sentence_count <= 1
        and observation_count == 0
        and event_count == 0
    )
    has_meaningful_structure = (
        richness_score >= 0.16
        or sentence_count >= 4
        or observation_count >= 2
        or event_count >= 1
    )
    generic_continuation_signal = bool(
        list_like_profile.get("list_follow_subtype") == "generic_continuation_routing_to_low_information"
        or non_list_profile.get("specificity_title_markers")
        or non_list_profile.get("specificity_lexical_markers")
        or non_list_profile.get("specificity_no_lift_markers")
        or information_gain_profile.get("information_gain_reason_markers")
    )
    return bool(not is_true_stub and has_meaningful_structure and generic_continuation_signal)


def _primary_follow_failure_bucket(
    *,
    quality_flags: list[str],
    follow_state: Mapping[str, Any],
    richness_score: float,
    non_list_profile: Mapping[str, Any],
    information_gain_profile: Mapping[str, Any],
    list_like_profile: Mapping[str, Any],
) -> str:
    if not quality_flags:
        return "stable_follow"
    if "list_like_follow" in quality_flags and str(list_like_profile.get("list_follow_subtype") or "") == "parent_child_aggregation":
        return "list_like_follow"
    if "low_information_gain_follow" in quality_flags and _prefer_low_information_primary_bucket(
        follow_state=follow_state,
        richness_score=richness_score,
        non_list_profile=non_list_profile,
        information_gain_profile=information_gain_profile,
        list_like_profile=list_like_profile,
    ):
        return "low_information_gain_follow"
    return quality_flags[0]


def compute_follow_target_quality(
    root_state: Mapping[str, Any],
    follow_state: Mapping[str, Any],
) -> dict[str, Any]:
    richness_score = compute_richness_score(follow_state)
    non_list_profile = compute_non_list_profile(follow_state, root_state=root_state)
    non_list_score = float(non_list_profile["non_list_score"])
    regime_similarity_score = compute_regime_similarity_score(root_state, follow_state)
    information_gain_profile = compute_information_gain_profile(root_state, follow_state)
    information_gain_score = float(information_gain_profile["information_gain_score"])
    list_like_profile = _classify_follow_list_subtype(
        non_list_profile,
        information_gain_profile,
        richness_score=richness_score,
    )
    list_like_penalty_active = bool(list_like_profile["list_like_penalty_active"])
    follow_target_quality_score = _clamp01(
        round(
            0.35 * richness_score
            + 0.25 * non_list_score
            + 0.20 * regime_similarity_score
            + 0.20 * information_gain_score,
            6,
        )
    )
    quality_flags: list[str] = []
    if non_list_score <= 0.25 and list_like_penalty_active:
        quality_flags.append("list_like_follow")
    if richness_score < 0.35:
        quality_flags.append("thin_follow")
    if information_gain_score < 0.35:
        quality_flags.append("low_information_gain_follow")
    if regime_similarity_score < 0.35:
        quality_flags.append("regime_jump_follow")
    primary_failure_bucket = _primary_follow_failure_bucket(
        quality_flags=quality_flags,
        follow_state=follow_state,
        richness_score=richness_score,
        non_list_profile=non_list_profile,
        information_gain_profile=information_gain_profile,
        list_like_profile=list_like_profile,
    )
    return {
        "richness_score": richness_score,
        "non_list_score": non_list_score,
        "regime_similarity_score": regime_similarity_score,
        "information_gain_score": information_gain_score,
        "follow_target_quality_score": follow_target_quality_score,
        "listiness": float(non_list_profile["listiness"]),
        "list_signal_weight": float(non_list_profile["list_signal_weight"]),
        "list_follow_subtype": str(list_like_profile["list_follow_subtype"]),
        "list_like_penalty_active": list_like_penalty_active,
        "list_like_penalty_reason": list_like_profile["list_like_penalty_reason"],
        "list_text_markers": list(non_list_profile["list_text_markers"]),
        "list_title_markers": list(non_list_profile["list_title_markers"]),
        "list_warning_markers": list(non_list_profile["list_warning_markers"]),
        "specificity_title_markers": list(non_list_profile["specificity_title_markers"]),
        "specificity_lexical_markers": list(non_list_profile["specificity_lexical_markers"]),
        "specificity_no_lift_markers": list(non_list_profile["specificity_no_lift_markers"]),
        "specificity_signal_weight": float(non_list_profile["specificity_signal_weight"]),
        "primary_specificity_reason": non_list_profile["primary_specificity_reason"],
        "title_overlap_ratio": float(non_list_profile["title_overlap_ratio"]),
        "term_overlap_ratio": float(non_list_profile["term_overlap_ratio"]),
        "novel_follow_term_count": int(non_list_profile["novel_follow_term_count"]),
        "base_information_gain_score": float(information_gain_profile["base_information_gain_score"]),
        "content_lift_score": float(information_gain_profile["content_lift_score"]),
        "relation_surface_score": float(information_gain_profile["relation_surface_score"]),
        "novel_term_support_score": float(information_gain_profile["novel_term_support_score"]),
        "content_lift_bonus": float(information_gain_profile["content_lift_bonus"]),
        "content_lift_reason_markers": list(information_gain_profile["content_lift_reason_markers"]),
        "information_gain_penalty": float(information_gain_profile["information_gain_penalty"]),
        "information_gain_reason_markers": list(information_gain_profile["information_gain_reason_markers"]),
        "information_gain_penalty_markers": list(information_gain_profile["information_gain_penalty_markers"]),
        "primary_information_gain_reason": information_gain_profile["primary_information_gain_reason"],
        "quality_flags": quality_flags,
        "primary_failure_bucket": primary_failure_bucket,
    }


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


def _coerce_regime_vector(article_state: Mapping[str, Any]) -> dict[str, float]:
    regime = article_state.get("regime")
    if isinstance(regime, Mapping):
        narrative = _clamp01(float(regime.get("narrative") or 0.0))
        descriptive = _clamp01(float(regime.get("descriptive") or 0.0))
        formal = _clamp01(float(regime.get("formal") or 0.0))
        total = narrative + descriptive + formal
        if total > 0.0:
            return {
                "narrative": round(narrative / total, 6),
                "descriptive": round(descriptive / total, 6),
                "formal": round(formal / total, 6),
            }
    return {"narrative": 1 / 3, "descriptive": 1 / 3, "formal": 1 / 3}


def _dominant_regime(regime: Mapping[str, float]) -> str:
    candidates = [(str(key), float(value)) for key, value in regime.items() if str(key)]
    if not candidates:
        return "unknown"
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates[0][0]


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


def _score_follow_target_quality(
    *,
    root_page_row: Mapping[str, Any],
    follow_page_row: Mapping[str, Any],
    follow_sample_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    details = compute_follow_target_quality(root_page_row, follow_page_row)
    return {
        **details,
        "follow_title": str(
            (follow_page_row.get("title") if isinstance(follow_page_row, Mapping) else "")
            or (follow_sample_row.get("title") if isinstance(follow_sample_row, Mapping) else "")
            or ""
        ),
    }


def _score_follow_yield(link_metrics: Mapping[str, Any]) -> dict[str, Any]:
    root_link_relevance_score = link_metrics.get("root_link_relevance_score")
    followed_link_relevance_score = link_metrics.get("followed_link_relevance_score")
    follow_target_quality_score = link_metrics.get("follow_target_quality_score")
    follow_yield_score = _mean_optional(
        [
            float(followed_link_relevance_score) if followed_link_relevance_score is not None else None,
            float(follow_target_quality_score) if follow_target_quality_score is not None else None,
        ]
    )
    return {
        "root_link_relevance_score": root_link_relevance_score,
        "followed_link_relevance_score": followed_link_relevance_score,
        "follow_target_quality_score": follow_target_quality_score,
        "follow_yield_score": follow_yield_score,
    }


def compute_path_score(
    root_state: Mapping[str, Any],
    hop1_state: Mapping[str, Any],
    hop2_state: Mapping[str, Any],
    hop1_quality: float,
    hop2_quality: float,
) -> float:
    coherence_01 = compute_regime_similarity_score(root_state, hop1_state)
    coherence_12 = compute_regime_similarity_score(hop1_state, hop2_state)
    path_coherence = round(0.5 * coherence_01 + 0.5 * coherence_12, 6)
    return _clamp01(round(0.4 * float(hop1_quality) + 0.4 * float(hop2_quality) + 0.2 * path_coherence, 6))


def _collect_tree_graph_metrics(root_node: Mapping[str, Any]) -> dict[str, Any]:
    root_page_row = root_node.get("page_row") if isinstance(root_node, Mapping) else {}
    root_edges = [edge for edge in root_node.get("edge_scores") or [] if isinstance(edge, Mapping)]
    hop1_details: list[dict[str, Any]] = []
    hop2_details: list[dict[str, Any]] = []
    candidate_paths: list[dict[str, Any]] = []
    hop1_scores: list[float] = []
    hop2_scores: list[float] = []

    for edge1 in root_edges:
        detail1 = dict(edge1.get("detail") or {})
        if detail1:
            hop1_details.append(detail1)
        edge1_score = edge1.get("score")
        if edge1_score is not None:
            hop1_scores.append(float(edge1_score))
        child_node = edge1.get("child")
        child_page_row = child_node.get("page_row") if isinstance(child_node, Mapping) else {}
        child_edges = [edge for edge in (child_node.get("edge_scores") or []) if isinstance(edge, Mapping)] if isinstance(child_node, Mapping) else []
        for edge2 in child_edges:
            detail2 = dict(edge2.get("detail") or {})
            if detail2:
                hop2_details.append(detail2)
            edge2_score = edge2.get("score")
            if edge2_score is not None:
                hop2_scores.append(float(edge2_score))
            grandchild_node = edge2.get("child")
            grandchild_page_row = grandchild_node.get("page_row") if isinstance(grandchild_node, Mapping) else {}
            if not isinstance(root_page_row, Mapping) or not isinstance(child_page_row, Mapping) or not isinstance(grandchild_page_row, Mapping):
                continue
            if edge1_score is None or edge2_score is None:
                continue
            path_score = compute_path_score(
                root_page_row,
                child_page_row,
                grandchild_page_row,
                float(edge1_score),
                float(edge2_score),
            )
            candidate_paths.append(
                {
                    "score": path_score,
                    "titles": [
                        str(root_page_row.get("title") or ""),
                        str(child_page_row.get("title") or ""),
                        str(grandchild_page_row.get("title") or ""),
                    ],
                }
            )

    hop1_quality = _mean_optional([float(value) for value in hop1_scores] or [])
    hop2_quality = _mean_optional([float(value) for value in hop2_scores] or [])
    hop_quality_decay = (
        round(max(0.0, float(hop1_quality) - float(hop2_quality)), 6)
        if hop1_quality is not None and hop2_quality is not None
        else None
    )
    hop2_listiness_rate = _mean_optional([round(1.0 - float(detail.get("non_list_score") or 0.0), 6) for detail in hop2_details] or [])
    hop2_regime_jump_rate = _mean_optional(
        [round(1.0 - float(detail.get("regime_similarity_score") or 0.0), 6) for detail in hop2_details] or []
    )
    avg_candidate_path_score = _mean_optional([float(item["score"]) for item in candidate_paths] or [])
    if candidate_paths:
        best_path = max(candidate_paths, key=lambda item: (item["score"], item["titles"]))
        best_path_score = float(best_path["score"])
        best_path_titles = list(best_path["titles"])
        best_path_vs_avg_gap = (
            round(best_path_score - float(avg_candidate_path_score), 6)
            if avg_candidate_path_score is not None
            else None
        )
    else:
        best_path_score = None
        best_path_titles = []
        best_path_vs_avg_gap = None
    return {
        "two_hop_metrics": {
            "hop1_quality": hop1_quality,
            "hop2_quality": hop2_quality,
            "hop_quality_decay": hop_quality_decay,
            "hop2_listiness_rate": hop2_listiness_rate,
            "hop2_regime_jump_rate": hop2_regime_jump_rate,
            "hop1_count": len(hop1_details),
            "hop2_count": len(hop2_details),
        },
        "best_path_metrics": {
            "best_path_score": best_path_score,
            "best_path_titles": best_path_titles,
            "avg_candidate_path_score": avg_candidate_path_score,
            "best_path_vs_avg_gap": best_path_vs_avg_gap,
            "best_path_count": len(candidate_paths),
        },
    }


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
    follow_target_rows: list[Mapping[str, Any]] | None = None,
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
    follow_target_rows = [row for row in (follow_target_rows or []) if isinstance(row, Mapping)]
    regime = _coerce_regime_vector(article_state)
    regime_narrative_weight = regime["narrative"]
    regime_descriptive_weight = regime["descriptive"]
    regime_formal_weight = regime["formal"]
    dominant_regime = _dominant_regime(regime)
    page_profile = _classify_page_family(payload, article_sentences)
    page_family = str(page_profile["family"])
    raw_text = str(payload.get("wikitext") or article_state.get("source_text", {}).get("wikitext") or "")
    key_terms = extract_key_terms(article_state)

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
    regime_observation_explosion_score = _regime_weighted_deficit_score(explosion_score, regime_narrative_weight)
    regime_actor_action_binding_score = _regime_weighted_deficit_score(
        actor_action_binding_score,
        _clamp01(regime_narrative_weight + (0.5 * regime_descriptive_weight)),
    )
    regime_object_binding_score = _regime_weighted_deficit_score(object_binding_score, regime_narrative_weight)
    regime_honesty_multiplier = _mean(
        [
            regime_observation_explosion_score if regime_observation_explosion_score is not None else explosion_score,
            text_hygiene_score,
            regime_actor_action_binding_score if regime_actor_action_binding_score is not None else actor_action_binding_score,
            regime_object_binding_score if regime_object_binding_score is not None else object_binding_score,
        ]
    )
    regime_article_ingest_honest_score = round(article_ingest_score * regime_honesty_multiplier, 6)
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
    follow_target_quality_details: list[dict[str, Any]] = []
    for index, follow_page_row in enumerate(follow_target_rows):
        follow_sample_row = follow_rows[index] if index < len(follow_rows) else {}
        follow_target_quality_details.append(
            _score_follow_target_quality(
                root_page_row={
                    "regime": regime,
                    "key_terms": key_terms,
                    "raw_text": raw_text,
                },
                follow_page_row=follow_page_row,
                follow_sample_row=follow_sample_row,
            )
        )
    follow_target_quality_score = _mean_optional(
        [detail["follow_target_quality_score"] for detail in follow_target_quality_details]
    )
    if follow_target_quality_score is not None:
        follow_target_quality_score = round(follow_target_quality_score, 6)
    else:
        follow_target_quality_score = None
    follow_yield_metrics = _score_follow_yield(
        {
            **link_metrics,
            "follow_target_quality_score": follow_target_quality_score,
        }
    )
    follow_yield_metrics["follow_target_quality_score"] = follow_target_quality_score
    follow_yield_metrics["follow_target_quality_count"] = len(follow_target_quality_details)
    if follow_target_quality_details:
        for key in (
            "richness_score",
            "non_list_score",
            "regime_similarity_score",
            "information_gain_score",
            "content_lift_score",
        ):
            component_values = [detail.get(key) for detail in follow_target_quality_details]
            follow_yield_metrics[key] = _mean_optional([float(value) if value is not None else None for value in component_values])
    if follow_target_quality_details:
        follow_yield_metrics["follow_target_quality_preview"] = follow_target_quality_details[:3]
    claim_attribution_metrics, claim_attr_issues = _score_claim_attribution_grounding(article_aao_rows)
    regime_abstention_score = _regime_weighted_deficit_score(
        abstention_metrics["abstention_calibration_score"],
        _clamp01(regime_narrative_weight + regime_descriptive_weight),
    )
    regime_link_relevance_score = _regime_weighted_deficit_score(
        link_metrics["root_link_relevance_score"],
        _clamp01(regime_narrative_weight + regime_descriptive_weight),
    )
    regime_claim_grounding_score = _regime_weighted_deficit_score(
        claim_attribution_metrics["claim_attribution_grounding_score"],
        _clamp01(regime_narrative_weight + regime_formal_weight),
    )

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
    regime_calibration_scores = {
        "abstention_calibration_score": regime_abstention_score,
        "link_relevance_score": regime_link_relevance_score,
        "claim_attribution_grounding_score": regime_claim_grounding_score,
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
    regime_calibration_multiplier = _mean_optional(
        [
            regime_abstention_score,
            regime_link_relevance_score,
            regime_claim_grounding_score,
        ]
    )
    if regime_calibration_multiplier is None:
        regime_calibration_multiplier = 1.0
    regime_calibration_multiplier = round(regime_calibration_multiplier, 6)
    regime_article_ingest_calibrated_score = round(
        regime_article_ingest_honest_score * regime_calibration_multiplier,
        6,
    )
    calibration_issues = abstention_issues + link_relevance_issues + claim_attr_issues

    return {
        "title": str(payload.get("title") or ""),
        "pageid": payload.get("pageid"),
        "revid": payload.get("revid"),
        "source_url": payload.get("source_url"),
        "regime": regime,
        "raw_text": raw_text,
        "key_terms": key_terms,
        "dominant_regime": dominant_regime,
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
        "follow_target_quality_score": follow_target_quality_score,
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
        "regime_adjusted_scores": {
            "observation_explosion_score": regime_observation_explosion_score,
            "text_hygiene_score": text_hygiene_score,
            "actor_action_binding_score": regime_actor_action_binding_score,
            "object_binding_score": regime_object_binding_score,
            "honesty_multiplier": regime_honesty_multiplier,
            "article_ingest_honest_score": regime_article_ingest_honest_score,
        },
        "calibration_scores": {
            **calibration_scores,
            "calibration_multiplier": calibration_multiplier,
            "article_ingest_calibrated_score": article_ingest_calibrated_score,
        },
        "regime_calibration_scores": {
            **regime_calibration_scores,
            "calibration_multiplier": regime_calibration_multiplier,
            "article_ingest_calibrated_score": regime_article_ingest_calibrated_score,
        },
        "density_metrics": density_metrics,
        "timeline_honesty": timeline_honesty,
        "page_profile": page_profile,
        "abstention_metrics": abstention_metrics,
        "abstention_warnings": abstention_warnings,
        "link_metrics": link_metrics,
        "follow_yield_metrics": follow_yield_metrics,
        "follow_target_quality_details": follow_target_quality_details[:5],
        "two_hop_metrics": {
            "hop1_quality": None,
            "hop2_quality": None,
            "hop_quality_decay": None,
            "hop2_listiness_rate": None,
            "hop2_regime_jump_rate": None,
            "hop1_count": 0,
            "hop2_count": 0,
        },
        "best_path_metrics": {
            "best_path_score": None,
            "best_path_titles": [],
            "avg_candidate_path_score": None,
            "best_path_vs_avg_gap": None,
            "best_path_count": 0,
        },
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
    follow_target_rows: list[Mapping[str, Any]] | None = None,
    max_sentences: int = 400,
    max_events: int = 64,
    max_follow_links_per_page: int = 0,
    no_spacy: bool = False,
) -> dict[str, Any]:
    if follow_target_rows is None and follow_rows:
        follow_target_rows = []
        for follow_row in follow_rows:
            snapshot_path = follow_row.get("snapshot_path") if isinstance(follow_row, Mapping) else None
            if not isinstance(snapshot_path, str):
                continue
            follow_payload = _load_json(Path(snapshot_path))
            follow_target_rows.append(
                score_snapshot_payload(
                    follow_payload,
                    follow_rows=[],
                    follow_target_rows=[],
                    max_sentences=max_sentences,
                    max_events=max_events,
                    max_follow_links_per_page=0,
                    no_spacy=no_spacy,
                )
            )
    wikitext = _extract_wikitext(payload)
    if not wikitext:
        payload = dict(payload)
    else:
        payload = dict(payload)
        payload["wikitext"] = wikitext
    if not wikitext.strip():
        article_state = {
            "sentence_units": [],
            "observations": [],
            "event_candidates": [],
            "timeline_projection": [],
            "parser": None,
            "extraction_profile": None,
        }
        timeline_row = {"scores": {}, "issues": ["snapshot_missing_wikitext"]}
        reducer_row = {"scores": {}, "issues": ["snapshot_missing_wikitext"]}
        row = _page_row_from_outputs(
            payload,
            article_state,
            timeline_row,
            reducer_row,
            follow_rows=follow_rows,
            follow_target_rows=follow_target_rows,
            max_follow_links_per_page=max_follow_links_per_page,
        )
        row["issues"].append("snapshot_missing_wikitext")
        warnings = [str(item) for item in (payload.get("warnings") or []) if str(item).strip()]
        if warnings:
            row["snapshot_warnings"] = warnings
        return row

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
        follow_target_rows=follow_target_rows,
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
    regime_score_sums = {
        "narrative": 0.0,
        "descriptive": 0.0,
        "formal": 0.0,
    }
    dominant_regime_counts: Counter[str] = Counter()
    regime_honesty_score_sums = {
        "observation_explosion_score": 0.0,
        "text_hygiene_score": 0.0,
        "actor_action_binding_score": 0.0,
        "object_binding_score": 0.0,
        "honesty_multiplier": 0.0,
        "article_ingest_honest_score": 0.0,
    }
    regime_calibration_score_sums: dict[str, float] = defaultdict(float)
    regime_calibration_score_counts: dict[str, int] = defaultdict(int)
    follow_target_quality_sum = 0.0
    follow_target_quality_count = 0
    follow_target_quality_by_depth_sum: dict[int, float] = defaultdict(float)
    follow_target_quality_by_depth_count: dict[int, int] = defaultdict(int)
    best_path_score_sum = 0.0
    best_path_score_count = 0
    best_path_avg_candidate_score_sum = 0.0
    best_path_avg_candidate_score_count = 0
    best_path_gap_sum = 0.0
    best_path_gap_count = 0
    follow_failure_bucket_counts: Counter[str] = Counter()
    follow_failure_bucket_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    specificity_reason_counts: Counter[str] = Counter()
    specificity_reason_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    information_gain_reason_counts: Counter[str] = Counter()
    information_gain_reason_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    calibration_score_sums: dict[str, float] = defaultdict(float)
    calibration_score_counts: dict[str, int] = defaultdict(int)
    density_metric_sums = {
        "observations_per_sentence": 0.0,
        "observations_per_event": 0.0,
        "steps_per_event": 0.0,
        "multi_step_event_ratio": 0.0,
        "zero_step_event_ratio": 0.0,
    }
    follow_yield_metric_sums: dict[str, float] = defaultdict(float)
    follow_yield_metric_counts: dict[str, int] = defaultdict(int)
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

    def _score_sample_tree(
        sample_row: Mapping[str, Any],
        *,
        depth: int = 0,
    ) -> dict[str, Any]:
        snapshot_path = sample_row.get("snapshot_path")
        if not isinstance(snapshot_path, str):
            raise ValueError("sample row missing snapshot_path")
        payload = _load_json(Path(snapshot_path))
        child_results = []
        raw_children = [row for row in (sample_row.get("followed_samples") or []) if isinstance(row, Mapping)]
        for child_row in raw_children:
            child_results.append(_score_sample_tree(child_row, depth=depth + 1))
        page_row = score_snapshot_payload(
            payload,
            follow_rows=raw_children,
            follow_target_rows=[child["page_row"] for child in child_results],
            max_sentences=max_sentences,
            max_events=max_events,
            max_follow_links_per_page=max_follow_links_per_page,
            no_spacy=no_spacy,
        )
        edge_scores = []
        for child_raw, child_result in zip(raw_children, child_results):
            edge_detail = _score_follow_target_quality(
                root_page_row=page_row,
                follow_page_row=child_result["page_row"],
                follow_sample_row=child_raw,
            )
            edge_scores.append(
                {
                    "depth": depth + 1,
                    "score": edge_detail["follow_target_quality_score"],
                    "detail": edge_detail,
                    "child": child_result,
                }
            )
        graph_metrics = _collect_tree_graph_metrics(
            {
                "page_row": page_row,
                "edge_scores": edge_scores,
            }
        )
        page_row["follow_target_quality_details"] = [edge["detail"] for edge in edge_scores[:5]]
        page_row["follow_yield_metrics"]["follow_target_quality_count"] = len(edge_scores)
        if edge_scores:
            page_row["follow_yield_metrics"]["follow_target_quality_preview"] = [edge["detail"] for edge in edge_scores[:3]]
        page_row["two_hop_metrics"] = graph_metrics["two_hop_metrics"]
        page_row["best_path_metrics"] = graph_metrics["best_path_metrics"]
        return {
            "depth": depth,
            "page_row": page_row,
            "sample_row": dict(sample_row),
            "children": child_results,
            "edge_scores": edge_scores,
        }

    def _collect_follow_metrics(
        node: Mapping[str, Any],
    ) -> None:
        nonlocal follow_target_quality_sum, follow_target_quality_count
        for edge in node.get("edge_scores") or []:
            edge_score = edge.get("score")
            if edge_score is None:
                continue
            edge_score = float(edge_score)
            edge_depth = int(edge.get("depth") or 0)
            follow_target_quality_sum += edge_score
            follow_target_quality_count += 1
            follow_target_quality_by_depth_sum[edge_depth] += edge_score
            follow_target_quality_by_depth_count[edge_depth] += 1
            detail = edge.get("detail") or {}
            bucket = str(detail.get("primary_failure_bucket") or "unknown_follow")
            follow_failure_bucket_counts[bucket] += 1
            examples = follow_failure_bucket_examples[bucket]
            if len(examples) < 5:
                child = edge.get("child") or {}
                child_page_row = child.get("page_row") or {}
                examples.append(
                    {
                        "root_title": str((node.get("page_row") or {}).get("title") or ""),
                        "follow_title": str(child_page_row.get("title") or ""),
                        "score": round(edge_score, 6),
                        "quality_flags": list(detail.get("quality_flags") or []),
                    }
                )
            specificity_reason = str(detail.get("primary_specificity_reason") or "").strip()
            if specificity_reason:
                specificity_reason_counts[specificity_reason] += 1
                reason_examples = specificity_reason_examples[specificity_reason]
                if len(reason_examples) < 5:
                    child = edge.get("child") or {}
                    child_page_row = child.get("page_row") or {}
                    reason_examples.append(
                        {
                            "root_title": str((node.get("page_row") or {}).get("title") or ""),
                            "follow_title": str(child_page_row.get("title") or ""),
                            "score": round(edge_score, 6),
                            "bucket": bucket,
                        }
                    )
            information_gain_reason = str(detail.get("primary_information_gain_reason") or "").strip()
            if information_gain_reason:
                information_gain_reason_counts[information_gain_reason] += 1
                gain_examples = information_gain_reason_examples[information_gain_reason]
                if len(gain_examples) < 5:
                    child = edge.get("child") or {}
                    child_page_row = child.get("page_row") or {}
                    gain_examples.append(
                        {
                            "root_title": str((node.get("page_row") or {}).get("title") or ""),
                            "follow_title": str(child_page_row.get("title") or ""),
                            "score": round(edge_score, 6),
                            "bucket": bucket,
                        }
                    )
            _collect_follow_metrics(edge["child"])

    for row in sample_rows:
        if not isinstance(row, Mapping):
            continue
        root_node = _score_sample_tree(row, depth=0)
        page_row = root_node["page_row"]
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
        for key in regime_honesty_score_sums:
            regime_honesty_score_sums[key] += float(page_row["regime_adjusted_scores"][key])
        for key, value in page_row["regime_calibration_scores"].items():
            if value is None:
                continue
            regime_calibration_score_sums[key] += float(value)
            regime_calibration_score_counts[key] += 1
        for key, value in page_row["calibration_scores"].items():
            if value is None:
                continue
            calibration_score_sums[key] += float(value)
            calibration_score_counts[key] += 1
        for key in regime_score_sums:
            regime_score_sums[key] += float(page_row["regime"][key])
        dominant_regime_counts[str(page_row["dominant_regime"])] += 1
        for key in density_metric_sums:
            density_metric_sums[key] += float(page_row["density_metrics"][key])
        for key, value in page_row["follow_yield_metrics"].items():
            if value is None or not isinstance(value, (int, float)):
                continue
            follow_yield_metric_sums[key] += float(value)
            follow_yield_metric_counts[key] += 1
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
        _collect_follow_metrics(root_node)
        best_path_metrics = page_row.get("best_path_metrics") or {}
        if best_path_metrics.get("best_path_score") is not None:
            best_path_score_sum += float(best_path_metrics["best_path_score"])
            best_path_score_count += 1
        if best_path_metrics.get("avg_candidate_path_score") is not None:
            best_path_avg_candidate_score_sum += float(best_path_metrics["avg_candidate_path_score"])
            best_path_avg_candidate_score_count += 1
        if best_path_metrics.get("best_path_vs_avg_gap") is not None:
            best_path_gap_sum += float(best_path_metrics["best_path_vs_avg_gap"])
            best_path_gap_count += 1

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
        "average_regime": {
            key: round((value / page_count), 6) if page_count else 0.0 for key, value in regime_score_sums.items()
        },
        "dominant_regime_counts": dict(sorted(dominant_regime_counts.items())),
        "average_regime_honesty_scores": {
            key: round((value / page_count), 6) if page_count else 0.0 for key, value in regime_honesty_score_sums.items()
        },
        "average_follow_yield_metrics": {
            key: round((follow_yield_metric_sums[key] / follow_yield_metric_counts[key]), 6)
            if follow_yield_metric_counts[key]
            else None
            for key in sorted(follow_yield_metric_sums.keys() | follow_yield_metric_counts.keys())
        },
        "average_follow_target_quality": {
            "overall": round((follow_target_quality_sum / follow_target_quality_count), 6)
            if follow_target_quality_count
            else None,
            "by_depth": {
                str(depth): round(
                    (follow_target_quality_by_depth_sum[depth] / follow_target_quality_by_depth_count[depth]),
                    6,
                )
                if follow_target_quality_by_depth_count[depth]
                else None
                for depth in sorted(follow_target_quality_by_depth_sum.keys() | follow_target_quality_by_depth_count.keys())
            },
        },
        "follow_failure_bucket_counts": dict(sorted(follow_failure_bucket_counts.items())),
        "follow_failure_bucket_examples": {
            bucket: examples
            for bucket, examples in sorted(follow_failure_bucket_examples.items())
        },
        "specificity_reason_counts": dict(sorted(specificity_reason_counts.items())),
        "specificity_reason_examples": {
            reason: examples
            for reason, examples in sorted(specificity_reason_examples.items())
        },
        "information_gain_reason_counts": dict(sorted(information_gain_reason_counts.items())),
        "information_gain_reason_examples": {
            reason: examples
            for reason, examples in sorted(information_gain_reason_examples.items())
        },
        "average_two_hop_metrics": {
            "hop1_quality": round(
                (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1]), 6
            )
            if follow_target_quality_by_depth_count[1]
            else None,
            "hop2_quality": round(
                (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2]), 6
            )
            if follow_target_quality_by_depth_count[2]
            else None,
            "hop_quality_decay": round(
                (
                    (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1])
                    - (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2])
                ),
                6,
            )
            if follow_target_quality_by_depth_count[1] and follow_target_quality_by_depth_count[2]
            else None,
            "hop1_count": follow_target_quality_by_depth_count[1],
            "hop2_count": follow_target_quality_by_depth_count[2],
            "hop1_follow_target_quality": round(
                (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1]), 6
            )
            if follow_target_quality_by_depth_count[1]
            else None,
            "hop2_follow_target_quality": round(
                (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2]), 6
            )
            if follow_target_quality_by_depth_count[2]
            else None,
            "quality_decay": round(
                (
                    (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1])
                    - (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2])
                ),
                6,
            )
            if follow_target_quality_by_depth_count[1] and follow_target_quality_by_depth_count[2]
            else None,
        },
        "average_best_path_metrics": {
            "best_path_score": round((best_path_score_sum / best_path_score_count), 6)
            if best_path_score_count
            else None,
            "avg_candidate_path_score": round((best_path_avg_candidate_score_sum / best_path_avg_candidate_score_count), 6)
            if best_path_avg_candidate_score_count
            else None,
            "best_path_vs_avg_gap": round((best_path_gap_sum / best_path_gap_count), 6)
            if best_path_gap_count
            else None,
            "best_path_count": best_path_score_count,
        },
        "two_hop_metrics": {
            "hop1_follow_target_quality": round(
                (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1]), 6
            )
            if follow_target_quality_by_depth_count[1]
            else None,
            "hop2_follow_target_quality": round(
                (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2]), 6
            )
            if follow_target_quality_by_depth_count[2]
            else None,
            "quality_decay": round(
                (
                    (follow_target_quality_by_depth_sum[1] / follow_target_quality_by_depth_count[1])
                    - (follow_target_quality_by_depth_sum[2] / follow_target_quality_by_depth_count[2])
                ),
                6,
            )
            if follow_target_quality_by_depth_count[1] and follow_target_quality_by_depth_count[2]
            else None,
            "hop1_count": follow_target_quality_by_depth_count[1],
            "hop2_count": follow_target_quality_by_depth_count[2],
        },
        "best_path_metrics": {
            "best_path_score": round((best_path_score_sum / best_path_score_count), 6)
            if best_path_score_count
            else None,
            "best_path_count": best_path_score_count,
        },
        "average_calibration_scores": {
            key: round((calibration_score_sums[key] / calibration_score_counts[key]), 6)
            if calibration_score_counts[key]
            else None
            for key in sorted(calibration_score_sums.keys() | calibration_score_counts.keys())
        },
        "average_regime_calibration_scores": {
            key: round((regime_calibration_score_sums[key] / regime_calibration_score_counts[key]), 6)
            if regime_calibration_score_counts[key]
            else None
            for key in sorted(regime_calibration_score_sums.keys() | regime_calibration_score_counts.keys())
        },
        "pages_with_calibration_metric": dict(sorted(calibration_score_counts.items())),
        "pages_with_regime_calibration_metric": dict(sorted(regime_calibration_score_counts.items())),
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
