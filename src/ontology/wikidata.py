from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import requests

from .wikidata_review_packet_claim_boundaries import (
    build_review_packet_claim_boundaries,
)
from .wikidata_review_packet_cross_source_alignment import (
    summarize_cross_source_alignment,
)
from .wikidata_review_packet_follow_depth import (
    enrich_review_packet_follow_depth,
)
from .wikidata_review_packet_reviewer_actions import (
    build_wikidata_review_packet_reviewer_actions,
)
from .wikidata_review_packet_variant_compare import (
    compare_review_packet_variants,
)


SCHEMA_VERSION = "wikidata_projection_v0_1"
FINDER_SCHEMA_VERSION = "wikidata_qualifier_drift_finder_v0_1"
MIGRATION_PACK_SCHEMA_VERSION = "sl.wikidata_migration_pack.v1"
SPLIT_PLAN_SCHEMA_VERSION = "sl.wikidata_split_plan.v0_1"
WIKIDATA_PHI_TEXT_BRIDGE_CASE_SCHEMA_VERSION = "sl.wikidata_phi_text_bridge_case.v1"
WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION = "sl.wikidata.climate_text_source.v1"
SOURCE_UNIT_SCHEMA_VERSION = "sl.source_unit.v1"
WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION = "sl.wikidata_review_packet.v0_1"
WIKIDATA_REVIEW_PACKET_SEMANTIC_LAYER_VERSION = "sl.wikidata_review_packet.semantic_layer.v0_1"
DEFAULT_FIND_QUALIFIER_PROPERTIES = ("P166", "P39", "P54", "P6")
DEFAULT_PROPERTY_FILTER = ("P279", "P31")
PROPERTY_PROFILES = {
    "default": DEFAULT_PROPERTY_FILTER,
    "prepopulation_core": ("P279", "P31", "P361", "P527"),
}
TEMPORAL_QUALIFIER_PROPERTIES = frozenset({"P580", "P582", "P585"})
REVIEW_QUALIFIER_PROPERTIES = frozenset({"P7452"})
PARTHOOD_PROPERTIES = frozenset({"P361", "P527"})
PARTHOOD_INVERSE_RELATIONS = {
    "P361": frozenset({"P361", "P527"}),
    "P527": frozenset({"P527", "P361"}),
}
PROPERTY_PRIORITY = {
    "P166": 40,
    "P39": 35,
    "P54": 30,
    "P6": 25,
}
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
MEDIAWIKI_API_ENDPOINT = "https://www.wikidata.org/w/api.php"
ENTITY_EXPORT_TEMPLATE = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json?revision={revid}"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SensibLaw-Wikidata-QualifierDrift/0.1",
}
CLIMATE_TEXT_CUE_TERMS = (
    "emission",
    "emissions",
    "carbon footprint",
    "co2",
    "co₂",
    "co2e",
    "tco2",
    "tco2e",
    "ghg",
    "greenhouse",
)
CLIMATE_TEXT_LINE_PATTERNS = (
    re.compile(r"(?P<year>(?:19|20)\d{2})\D{0,20}(?P<value>\d[\d,]*(?:\.\d+)?)"),
    re.compile(r"(?P<value>\d[\d,]*(?:\.\d+)?)\D{0,20}(?P<year>(?:19|20)\d{2})"),
)
CLIMATE_TEXT_PREDICATE = "annual_emissions"
SCOPE_QUALIFIER_PROPERTY = "P518"
SCOPE_TAG_PATTERNS = {
    "scope_1": re.compile(r"\bscope[\s_-]*1\b", re.IGNORECASE),
    "scope_2": re.compile(r"\bscope[\s_-]*2\b", re.IGNORECASE),
    "scope_3": re.compile(r"\bscope[\s_-]*3\b", re.IGNORECASE),
}
URL_PATTERN = re.compile(r"https?://[^\s<>()]+")
PROPERTY_ID_PATTERN = re.compile(r"\bP\d+\b")


def resolve_property_filter(
    *,
    profile: str | None = None,
    property_filter: Iterable[str] | None = None,
) -> tuple[str, ...]:
    selected_profile = (profile or "default").strip() or "default"
    if selected_profile not in PROPERTY_PROFILES:
        raise ValueError(f"unknown property profile: {selected_profile}")
    if property_filter:
        return tuple(sorted(set(property_filter)))
    return tuple(PROPERTY_PROFILES[selected_profile])


@dataclass(frozen=True)
class StatementBundle:
    subject: str
    property: str
    value: Any
    rank: str
    qualifiers: tuple[tuple[str, tuple[str, ...]], ...]
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]


@dataclass(frozen=True)
class WindowSlice:
    window_id: str
    bundles: tuple[StatementBundle, ...]


def _bundle_qualifier_map(bundle: StatementBundle) -> dict[str, tuple[str, ...]]:
    return {prop: values for prop, values in bundle.qualifiers}


def _bundle_qualifier_signature(bundle: StatementBundle) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(sorted(bundle.qualifiers))


def _time_qualifier_value_count(bundle: StatementBundle) -> int:
    qualifier_map = _bundle_qualifier_map(bundle)
    return sum(len(qualifier_map.get(prop, tuple())) for prop in TEMPORAL_QUALIFIER_PROPERTIES)


def _has_time_range(bundle: StatementBundle) -> bool:
    qualifier_map = _bundle_qualifier_map(bundle)
    return "P580" in qualifier_map and "P582" in qualifier_map


def _detect_independent_axes(
    bundle: StatementBundle,
    *,
    slot_bundles: Sequence[StatementBundle],
    distinct_values: set[str],
) -> list[dict[str, Any]]:
    axes: list[dict[str, Any]] = []
    qualifier_map = _bundle_qualifier_map(bundle)

    if len(distinct_values) > 1:
        axes.append(
            {
                "property": "__value__",
                "cardinality": len(distinct_values),
                "source": "slot",
                "reason": "multi_value_slot",
            }
        )

    qualifier_properties = {
        prop for sibling in slot_bundles for prop, _ in sibling.qualifiers
    } | set(qualifier_map)
    for prop in sorted(qualifier_properties):
        slot_values = {
            value
            for sibling in slot_bundles
            for sibling_prop, sibling_values in sibling.qualifiers
            if sibling_prop == prop
            for value in sibling_values
        }
        bundle_values = set(qualifier_map.get(prop, tuple()))
        if len(slot_values) > 1:
            axes.append(
                {
                    "property": prop,
                    "cardinality": len(slot_values),
                    "source": "slot",
                    "reason": "multi_valued_dimension",
                }
            )
        elif len(bundle_values) > 1:
            axes.append(
                {
                    "property": prop,
                    "cardinality": len(bundle_values),
                    "source": "bundle",
                    "reason": "multi_valued_dimension",
                }
            )

    return axes


def _split_required_reasons(
    bundle: StatementBundle,
    *,
    slot_bundles: Sequence[StatementBundle],
    distinct_values: set[str],
    independent_axes: Sequence[Mapping[str, Any]],
) -> list[str]:
    reasons: list[str] = [
        _stringify(axis.get("reason"))
        for axis in independent_axes
        if axis.get("reason")
    ]
    qualifier_map = _bundle_qualifier_map(bundle)
    has_temporal_detail = any(prop in qualifier_map for prop in TEMPORAL_QUALIFIER_PROPERTIES)

    sibling_same_value = [sibling for sibling in slot_bundles if _stringify(sibling.value) == _stringify(bundle.value)]
    sibling_signatures = {_bundle_qualifier_signature(sibling) for sibling in sibling_same_value}
    if len(sibling_signatures) > 1:
        reasons.append("duplicate_value_diff_qualifiers")

    sibling_temporal_signatures = {
        tuple(sorted((prop, values) for prop, values in _bundle_qualifier_map(sibling).items() if prop in TEMPORAL_QUALIFIER_PROPERTIES))
        for sibling in slot_bundles
        if any(prop in _bundle_qualifier_map(sibling) for prop in TEMPORAL_QUALIFIER_PROPERTIES)
    }
    if not has_temporal_detail and sibling_temporal_signatures:
        reasons.append("missing_time_qualifier_in_temporal_slot")
    elif len({signature for signature in sibling_temporal_signatures if signature}) > 1:
        reasons.append("mixed_temporal_resolution")

    if _time_qualifier_value_count(bundle) > 1:
        reasons.append("multiple_time_qualifiers")

    if _has_time_range(bundle):
        reasons.append("time_range_requires_split")

    return sorted(set(reasons))


def _suggest_migration_action(*, classification: str) -> str:
    if classification == "safe_equivalent":
        return "migrate"
    if classification == "safe_with_reference_transfer":
        return "migrate_with_refs"
    if classification == "split_required":
        return "split"
    if classification == "abstain":
        return "abstain"
    return "review"


def _normalize_bridge_qualifiers(raw: Any) -> dict[str, tuple[str, ...]]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("text observation qualifiers must be an object when present")
    return {
        _stringify(prop): _normalize_value_list(value)
        for prop, value in raw.items()
    }


def _bridge_temporal_values(qualifiers: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    values: list[str] = []
    for prop in TEMPORAL_QUALIFIER_PROPERTIES:
        values.extend(_stringify(value) for value in qualifiers.get(prop, ()))
    return tuple(sorted(set(values)))


def _bridge_temporal_years(qualifiers: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    years: set[str] = set()
    for value in _bridge_temporal_values(qualifiers):
        for match in re.findall(r"(?:19|20)\d{2}", value):
            years.add(match)
    return tuple(sorted(years))


def _bridge_scope_values(qualifiers: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    return tuple(sorted(set(_stringify(value) for value in qualifiers.get(SCOPE_QUALIFIER_PROPERTY, ()))))


def _normalize_text_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    promotion_status = _stringify(raw.get("promotion_status", ""))
    if promotion_status != "promoted_true":
        raise ValueError("text bridge only accepts promoted_true observations")
    observation_ref = _stringify(raw.get("observation_ref", ""))
    source_ref = _stringify(raw.get("source_ref", ""))
    if not observation_ref or not source_ref:
        raise ValueError("text observations require observation_ref and source_ref")
    anchors = raw.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("text observations require non-empty anchors")
    qualifiers = _normalize_bridge_qualifiers(raw.get("qualifiers"))
    return {
        "observation_ref": observation_ref,
        "source_ref": source_ref,
        "anchors": [
            {
                "start": int(anchor["start"]),
                "end": int(anchor["end"]),
                **({"text": _stringify(anchor.get("text"))} if anchor.get("text") is not None else {}),
            }
            for anchor in anchors
            if isinstance(anchor, Mapping) and "start" in anchor and "end" in anchor
        ],
        "subject": _stringify(raw.get("subject", "")),
        "predicate": _stringify(raw.get("predicate", "")),
        "object": _stringify(raw.get("object", "")),
        "qualifiers": {prop: list(values) for prop, values in qualifiers.items()},
        "promotion_status": promotion_status,
    }


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _normalize_climate_numeric_value(raw: str) -> str:
    cleaned = raw.replace(",", "").strip()
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned


def _extract_scope_tags_from_text(text: str) -> tuple[str, ...]:
    return tuple(sorted(tag for tag, pattern in SCOPE_TAG_PATTERNS.items() if pattern.search(text)))


def _normalize_string_list(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, (list, tuple)):
        values = [_stringify(value).strip() for value in raw if _stringify(value).strip()]
        return tuple(sorted(set(values)))
    value = _stringify(raw).strip()
    return (value,) if value else tuple()


def _extract_property_ids(text: str) -> list[str]:
    return sorted(set(match.group(0) for match in PROPERTY_ID_PATTERN.finditer(text or "")))


def _extract_urls(text: str) -> list[str]:
    return sorted(set(match.group(0).rstrip(".,)") for match in URL_PATTERN.finditer(text or "")))


def _anchor_excerpt(text: str, *, start: int, end: int) -> str:
    return (text or "")[max(start, 0):max(end, 0)].strip()


def _source_unit_anchor_refs(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    anchors = source.get("anchors")
    content = source.get("content")
    if not isinstance(anchors, list) or not isinstance(content, Mapping):
        return []
    text = _stringify(content.get("text", ""))
    anchor_refs: list[dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            continue
        start = int(anchor.get("start", 0) or 0)
        end = int(anchor.get("end", 0) or 0)
        anchor_refs.append(
            {
                "anchor_id": _stringify(anchor.get("anchor_id")),
                "start": start,
                "end": end,
                "label": anchor.get("label"),
                "text_excerpt": _anchor_excerpt(text, start=start, end=end),
            }
        )
    return anchor_refs


def _anchor_text_by_label(source: Mapping[str, Any], label: str) -> str:
    for anchor in _source_unit_anchor_refs(source):
        if _stringify(anchor.get("label")) == label:
            return _stringify(anchor.get("text_excerpt", ""))
    return ""


def _extract_unresolved_questions(text: str) -> list[str]:
    questions: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("?"):
            questions.append(line.lstrip("- ").strip())
            continue
        lowered = line.lower()
        if lowered.startswith("- is ") or lowered.startswith("is it "):
            questions.append(line.lstrip("- ").strip())
    return sorted(set(question for question in questions if question))


def _find_first_line_matching(text: str, patterns: Sequence[str]) -> str:
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if any(pattern in lowered for pattern in patterns):
            return line
    return ""


def _is_bounded_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("- "):
        return False
    if len(stripped) > 40:
        return False
    if any(token in stripped for token in (".", "(", ")", ":", "http://", "https://")):
        return False
    words = [word for word in stripped.split() if word]
    if not words or len(words) > 4:
        return False
    return stripped.lower() in {"tasks", "done", "to do", "queries"}


def _parse_bounded_wiki_sections(text: str) -> dict[str, Any]:
    headings: list[str] = []
    sections: list[dict[str, Any]] = []
    current_heading: str | None = None
    current_items: list[str] = []

    def flush_current() -> None:
        nonlocal current_heading, current_items
        if current_heading is not None:
            sections.append({"heading": current_heading, "items": list(current_items)})
        current_heading = None
        current_items = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            if current_heading is None:
                current_heading = "unheaded"
                if current_heading not in headings:
                    headings.append(current_heading)
            current_items.append(line[2:].strip())
            continue
        if _is_bounded_section_heading(line):
            flush_current()
            current_heading = line
            if line not in headings:
                headings.append(line)
    flush_current()

    section_map = {section["heading"].lower(): section["items"] for section in sections}
    todo_items = list(section_map.get("to do", []))
    done_items = list(section_map.get("done", []))
    query_rows = list(section_map.get("queries", []))
    cohort_task_lines = [
        item for item in todo_items
        if any(
            token in item.lower()
            for token in ("instance", "statements", "migration for", "evaluate migration")
        )
    ]
    return {
        "headings": headings,
        "sections": sections,
        "task_buckets": {
            "done": done_items,
            "todo": todo_items,
        },
        "cohort_task_lines": cohort_task_lines,
        "query_rows": query_rows,
    }


def _normalize_follow_receipts(raw: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for index, receipt in enumerate(raw or []):
        if not isinstance(receipt, Mapping):
            raise ValueError("follow receipts must be objects")
        receipt_id = _stringify(receipt.get("receipt_id", f"follow:{index + 1}")).strip()
        url = _stringify(receipt.get("url", "")).strip()
        follow_reason = _stringify(receipt.get("follow_reason", "")).strip()
        if not receipt_id or not url or not follow_reason:
            raise ValueError("follow receipts require receipt_id, url, and follow_reason")
        receipts.append(
            {
                "receipt_id": receipt_id,
                "url": url,
                "follow_reason": follow_reason,
                "extracted_evidence": [
                    _stringify(item).strip()
                    for item in receipt.get("extracted_evidence", [])
                    if _stringify(item).strip()
                ],
                "unresolved_uncertainty": [
                    _stringify(item).strip()
                    for item in receipt.get("unresolved_uncertainty", [])
                    if _stringify(item).strip()
                ],
            }
        )
    return receipts


def _bounded_follow_receipts_from_page_signals(
    *,
    parsed_page: Mapping[str, Any],
    page_signals: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query_links = page_signals.get("query_links")
    if not isinstance(query_links, list) or not query_links:
        return []
    query_rows = parsed_page.get("query_rows")
    if not isinstance(query_rows, list):
        query_rows = []

    receipts: list[dict[str, Any]] = []
    for index, url in enumerate(query_links):
        follow_url = _stringify(url).strip()
        if not follow_url:
            continue
        query_row = _stringify(query_rows[index]).strip() if index < len(query_rows) else ""
        extracted_evidence = [
            f"query_row: {query_row}" if query_row else f"query_link: {follow_url}",
        ]
        unresolved_uncertainty = [
            "query output is live search evidence rather than a revision-locked source",
            "followed link not expanded into a deeper fetch in this packet slice",
        ]
        if query_row:
            unresolved_uncertainty.append("query row should be checked against the reviewed split bundle")
        receipts.append(
            {
                "receipt_id": f"follow:query:{index + 1}",
                "url": follow_url,
                "follow_reason": "bounded follow of the query link named in the source surface",
                "extracted_evidence": extracted_evidence,
                "unresolved_uncertainty": unresolved_uncertainty,
            }
        )
    return receipts


def _select_source_unit(
    payload: Mapping[str, Any],
    *,
    source_unit_id: str | None = None,
) -> Mapping[str, Any]:
    source_units = _source_units_from_payload(payload)
    if source_unit_id is None:
        if not source_units:
            raise ValueError("source unit payload requires at least one source unit")
        return source_units[0]
    for source in source_units:
        if _stringify(source.get("source_unit_id")) == source_unit_id:
            return source
    raise ValueError(f"source unit not found: {source_unit_id}")


def _select_split_plan(
    payload: Mapping[str, Any],
    *,
    split_plan_id: str,
) -> Mapping[str, Any]:
    if _stringify(payload.get("schema_version", "")) != SPLIT_PLAN_SCHEMA_VERSION:
        raise ValueError(f"split plan payload must use {SPLIT_PLAN_SCHEMA_VERSION}")
    plans = payload.get("plans")
    if not isinstance(plans, list):
        raise ValueError("split plan payload requires a plans array")
    for plan in plans:
        if isinstance(plan, Mapping) and _stringify(plan.get("split_plan_id")) == split_plan_id:
            return plan
    raise ValueError(f"split plan not found: {split_plan_id}")


def _review_packet_page_signals(source: Mapping[str, Any]) -> dict[str, Any]:
    content = source.get("content")
    if not isinstance(content, Mapping):
        raise ValueError("source unit content must be an object")
    text = _stringify(content.get("text", ""))
    qualifier_text = _find_first_line_matching(
        text,
        ("qualifiers wip:", "qualifiers we can find:"),
    ) or _anchor_text_by_label(source, "expected_qualifier_family")
    reference_text = _find_first_line_matching(
        text,
        ("following reference properties:", "capture the references."),
    ) or _anchor_text_by_label(source, "expected_reference_family")
    urls = _extract_urls(text)
    query_links = [
        url for url in urls
        if "w.wiki/" in url or "query.wikidata.org" in url
    ]
    cited_links = list(query_links)
    outbound_links = [url for url in urls if url not in set(query_links)]
    return {
        "query_links": query_links,
        "cited_links": cited_links,
        "outbound_links": outbound_links,
        "unresolved_questions": _extract_unresolved_questions(text),
        "expected_qualifier_properties": _extract_property_ids(qualifier_text),
        "expected_reference_properties": _extract_property_ids(reference_text),
    }


def _reviewer_view_for_packet(
    *,
    split_plan: Mapping[str, Any],
    parsed_page: Mapping[str, Any],
    page_signals: Mapping[str, Any],
    follow_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    decision_focus = ["confirm_split_axes", "confirm_target_bundle_count"]
    if _stringify(split_plan.get("reference_propagation")) != "exact":
        decision_focus.append("confirm_reference_propagation")
    else:
        decision_focus.append("spot_check_reference_propagation")
    if _stringify(split_plan.get("qualifier_propagation")) != "exact":
        decision_focus.append("confirm_qualifier_propagation")
    else:
        decision_focus.append("spot_check_qualifier_propagation")
    if page_signals.get("unresolved_questions"):
        decision_focus.append("resolve_page_open_questions")
    todo_items = parsed_page.get("task_buckets", {}).get("todo", []) if isinstance(parsed_page.get("task_buckets"), Mapping) else []
    if todo_items:
        decision_focus.append("use_todo_bucket_as_review_checklist")
    uncertainty_flags: list[str] = []
    if page_signals.get("unresolved_questions"):
        uncertainty_flags.append("page_open_questions")
    if _stringify(split_plan.get("status")) == "review_only":
        uncertainty_flags.append("plan_status_review_only")
    if _stringify(split_plan.get("reference_propagation")) != "exact":
        uncertainty_flags.append("reference_propagation_requires_review")
    if _stringify(split_plan.get("qualifier_propagation")) != "exact":
        uncertainty_flags.append("qualifier_propagation_requires_review")
    if not follow_receipts:
        uncertainty_flags.append("no_follow_receipts")
    return {
        "decision_focus": decision_focus,
        "uncertainty_flags": uncertainty_flags,
        "recommended_next_step": _stringify(split_plan.get("suggested_action", "review_only")),
    }


def _comparison_variants_from_split_plan_payload(
    *,
    split_plan_payload: Mapping[str, Any],
    split_plan_id: str,
    max_variants: int = 3,
) -> list[dict[str, Any]]:
    plans = split_plan_payload.get("plans")
    if not isinstance(plans, list):
        return []
    variants: list[dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, Mapping):
            continue
        candidate_split_plan_id = _stringify(plan.get("split_plan_id")).strip()
        if not candidate_split_plan_id:
            entity_qid = _stringify(plan.get("entity_qid")).strip()
            if entity_qid:
                candidate_split_plan_id = f"split://{entity_qid}|{_stringify(split_plan_payload.get('source_property')).strip()}"
        if not candidate_split_plan_id or candidate_split_plan_id == split_plan_id:
            continue
        variants.append(
            {
                "candidate_id": candidate_split_plan_id,
                "classification": _stringify(plan.get("status")).strip(),
                "suggested_action": _stringify(plan.get("suggested_action")).strip(),
                "action": _stringify(plan.get("suggested_action")).strip(),
                "merged_split_axes": [
                    {
                        "property": _stringify(axis.get("property")).strip(),
                        "cardinality": int(axis.get("cardinality", 0) or 0),
                        "reason": _stringify(axis.get("reason")).strip(),
                        "source": _stringify(axis.get("source")).strip(),
                    }
                    for axis in plan.get("merged_split_axes", [])
                    if isinstance(axis, Mapping)
                ],
            }
        )
        if len(variants) >= max_variants:
            break
    return variants


def _build_review_packet_semantic_decomposition(
    *,
    anchor_refs: Sequence[Mapping[str, Any]],
    split_review_context: Mapping[str, Any],
    parsed_page: Mapping[str, Any],
    page_signals: Mapping[str, Any],
    follow_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    query_rows = [
        _stringify(item).strip()
        for item in parsed_page.get("query_rows", [])
        if _stringify(item).strip()
    ]
    unresolved_questions = [
        _stringify(item).strip()
        for item in page_signals.get("unresolved_questions", [])
        if _stringify(item).strip()
    ]
    todo_items = []
    task_buckets = parsed_page.get("task_buckets")
    if isinstance(task_buckets, Mapping):
        todo_items = [
            _stringify(item).strip()
            for item in task_buckets.get("todo", [])
            if _stringify(item).strip()
        ]
    normalized_anchor_refs = [
        anchor for anchor in anchor_refs
        if isinstance(anchor, Mapping) and _stringify(anchor.get("text_excerpt", "")).strip()
    ]
    split_plan_id = _stringify(split_review_context.get("split_plan_id", "")).strip()
    split_axes = [
        axis for axis in split_review_context.get("merged_split_axes", [])
        if isinstance(axis, Mapping)
    ]
    source_candidate_ids = [
        _stringify(candidate_id).strip()
        for candidate_id in split_review_context.get("source_candidate_ids", [])
        if _stringify(candidate_id).strip()
    ]

    candidate_units: list[dict[str, str]] = []
    candidate_units.extend(
        {
            "unit_id": f"query_row:{index + 1}",
            "unit_type": "query_row_surface",
            "text": row,
        }
        for index, row in enumerate(query_rows)
    )
    candidate_units.extend(
        {
            "unit_id": f"follow_receipt:{index + 1}",
            "unit_type": "follow_receipt_surface",
            "text": (
                f"receipt_id={_stringify(receipt.get('receipt_id')).strip()} "
                f"url={_stringify(receipt.get('url')).strip()} "
                f"reason={_stringify(receipt.get('follow_reason')).strip()} "
                f"evidence_count={len(receipt.get('extracted_evidence', []))} "
                f"unresolved_count={len(receipt.get('unresolved_uncertainty', []))}"
            ),
        }
        for index, receipt in enumerate(follow_receipts)
        if isinstance(receipt, Mapping)
        and _stringify(receipt.get("receipt_id")).strip()
        and _stringify(receipt.get("url")).strip()
    )
    candidate_units.extend(
        {
            "unit_id": f"open_question:{index + 1}",
            "unit_type": "open_question_surface",
            "text": question,
        }
        for index, question in enumerate(unresolved_questions)
    )
    candidate_units.extend(
        {
            "unit_id": f"todo_item:{index + 1}",
            "unit_type": "todo_surface",
            "text": item,
        }
        for index, item in enumerate(todo_items)
    )
    candidate_units.extend(
        {
            "unit_id": f"anchor:{_stringify(anchor.get('anchor_id')).strip() or index + 1}",
            "unit_type": "anchor_surface",
            "text": (
                f"{_stringify(anchor.get('label')).strip()}: "
                f"{_stringify(anchor.get('text_excerpt')).strip()}"
                if _stringify(anchor.get("label")).strip()
                else _stringify(anchor.get("text_excerpt")).strip()
            ),
        }
        for index, anchor in enumerate(normalized_anchor_refs)
    )
    if split_plan_id:
        candidate_units.append(
            {
                "unit_id": "split_plan:context",
                "unit_type": "split_context_surface",
                "text": (
                    f"{split_plan_id} status={_stringify(split_review_context.get('status'))} "
                    f"action={_stringify(split_review_context.get('suggested_action'))} "
                    f"review_required={bool(split_review_context.get('review_required'))} "
                    f"proposed_bundle_count={int(split_review_context.get('proposed_bundle_count', 0) or 0)}"
                ),
            }
        )
    candidate_units.extend(
        {
            "unit_id": f"split_axis:{index + 1}",
            "unit_type": "split_axis_surface",
            "text": (
                f"property={_stringify(axis.get('property'))} "
                f"source={_stringify(axis.get('source'))} "
                f"reason={_stringify(axis.get('reason'))} "
                f"cardinality={int(axis.get('cardinality', 0) or 0)}"
            ),
        }
        for index, axis in enumerate(split_axes)
    )
    if source_candidate_ids:
        candidate_units.append(
            {
                "unit_id": "split_candidates:summary",
                "unit_type": "split_context_surface",
                "text": (
                    f"source_candidate_ids={len(source_candidate_ids)} "
                    f"sample={','.join(source_candidate_ids[:3])}"
                ),
            }
        )

    missing_evidence = [
        "no_revision_locked_excerpts_for_candidate_units",
        "no_claim_boundary_mapping_for_candidate_units",
        "no_cross_source_alignment_for_candidate_units",
    ]
    if query_rows:
        missing_evidence.append("query_rows_not_expanded_into_fetched_semantic_units")
    if follow_receipts:
        missing_evidence.append("follow_receipts_not_promoted_to_semantic_claims")
    if unresolved_questions:
        missing_evidence.append("open_questions_not_resolved_into_grounded_assertions")
    if todo_items:
        missing_evidence.append("todo_items_not_lifted_into_review_decision_graph")
    if normalized_anchor_refs:
        missing_evidence.append("anchor_refs_not_promoted_to_grounded_claims")
    if split_axes or split_plan_id:
        missing_evidence.append("split_context_not_lifted_into_semantic_decision_graph")

    normalized_missing_evidence = sorted(set(missing_evidence))
    candidate_units.extend(
        {
            "unit_id": f"missing_evidence:{index + 1}",
            "unit_type": "missing_evidence_surface",
            "text": gap,
        }
        for index, gap in enumerate(normalized_missing_evidence)
    )

    return {
        "layer_schema_version": WIKIDATA_REVIEW_PACKET_SEMANTIC_LAYER_VERSION,
        "decomposition_state": "surface_only",
        "separate_from_parsed_page": True,
        "candidate_units": candidate_units,
        "missing_evidence": normalized_missing_evidence,
    }


def build_wikidata_review_packet(
    *,
    source_unit_payload: Mapping[str, Any],
    split_plan_payload: Mapping[str, Any],
    split_plan_id: str,
    source_unit_id: str | None = None,
    follow_receipts: Sequence[Mapping[str, Any]] | None = None,
    follow_depth_source_text_by_url: Mapping[str, str] | None = None,
    comparison_variants: Sequence[Mapping[str, Any]] | None = None,
    include_semantic_decomposition: bool = False,
) -> dict[str, Any]:
    source = _select_source_unit(source_unit_payload, source_unit_id=source_unit_id)
    split_plan = _select_split_plan(split_plan_payload, split_plan_id=split_plan_id)
    revision = source.get("revision")
    origin = source.get("origin")
    if not isinstance(revision, Mapping) or not isinstance(origin, Mapping):
        raise ValueError("source units require revision and origin objects")
    content = source.get("content")
    if not isinstance(content, Mapping):
        raise ValueError("source unit content must be an object")
    parsed_page = _parse_bounded_wiki_sections(_stringify(content.get("text", "")))
    page_signals = _review_packet_page_signals(source)
    if follow_receipts is None:
        normalized_receipts = _bounded_follow_receipts_from_page_signals(
            parsed_page=parsed_page,
            page_signals=page_signals,
        )
    else:
        normalized_receipts = _normalize_follow_receipts(follow_receipts)
    packet_key = (
        f"{_stringify(source.get('source_unit_id'))}|"
        f"{_stringify(split_plan.get('split_plan_id'))}"
    )
    packet_id = f"review-packet:{hashlib.sha1(packet_key.encode('utf-8')).hexdigest()[:16]}"
    packet = {
        "schema_version": WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "review_entity_qid": _stringify(split_plan.get("entity_qid")),
        "source_surface": {
            "source_unit_id": _stringify(source.get("source_unit_id")),
            "source_entity_qid": _stringify(source.get("entity_qid")),
            "revision": {
                "revision_id": revision.get("revision_id"),
                "revision_timestamp": _stringify(revision.get("revision_timestamp")),
                "retrieval_method": _stringify(revision.get("retrieval_method")),
            },
            "origin": {
                "source_type": _stringify(origin.get("source_type")),
                "source_url": origin.get("source_url"),
                "title": origin.get("title"),
            },
            "anchor_refs": _source_unit_anchor_refs(source),
        },
        "split_review_context": {
            "split_plan_id": _stringify(split_plan.get("split_plan_id")),
            "source_slot_id": _stringify(split_plan.get("source_slot_id")),
            "source_candidate_ids": [
                _stringify(item) for item in split_plan.get("source_candidate_ids", [])
            ],
            "status": _stringify(split_plan.get("status")),
            "review_required": bool(split_plan.get("review_required")),
            "suggested_action": _stringify(split_plan.get("suggested_action")),
            "merged_split_axes": [
                {
                    "property": _stringify(axis.get("property")),
                    "source": _stringify(axis.get("source")),
                    "reason": _stringify(axis.get("reason")),
                    "cardinality": int(axis.get("cardinality", 0) or 0),
                }
                for axis in split_plan.get("merged_split_axes", [])
                if isinstance(axis, Mapping)
            ],
            "proposed_bundle_count": int(split_plan.get("proposed_bundle_count", 0) or 0),
            "reference_propagation": _stringify(split_plan.get("reference_propagation")),
            "qualifier_propagation": _stringify(split_plan.get("qualifier_propagation")),
        },
        "parsed_page": parsed_page,
        "page_signals": page_signals,
        "follow_receipts": normalized_receipts,
        "reviewer_view": _reviewer_view_for_packet(
            split_plan=split_plan,
            parsed_page=parsed_page,
            page_signals=page_signals,
            follow_receipts=normalized_receipts,
        ),
    }
    if include_semantic_decomposition:
        auto_comparison_variants = list(comparison_variants or [])
        if not auto_comparison_variants:
            auto_comparison_variants = _comparison_variants_from_split_plan_payload(
                split_plan_payload=split_plan_payload,
                split_plan_id=split_plan_id,
            )
        semantic_decomposition = _build_review_packet_semantic_decomposition(
            anchor_refs=packet["source_surface"]["anchor_refs"],
            split_review_context=packet["split_review_context"],
            parsed_page=parsed_page,
            page_signals=page_signals,
            follow_receipts=normalized_receipts,
        )
        semantic_decomposition["follow_depth"] = enrich_review_packet_follow_depth(
            packet,
            source_text_by_url=follow_depth_source_text_by_url,
        )
        semantic_decomposition["claim_boundaries"] = build_review_packet_claim_boundaries(
            source_surface=packet["source_surface"],
            split_review_context=packet["split_review_context"],
            parsed_page=parsed_page,
            page_signals=page_signals,
        )
        semantic_decomposition["cross_source_alignment"] = summarize_cross_source_alignment(
            packet_id=packet_id,
            wiki_surface={
                "qid": _stringify(packet.get("review_entity_qid")),
                "source": _stringify(packet["source_surface"]["origin"].get("source_type")),
                "fields": list(parsed_page.get("query_rows", [])),
                "summary": _stringify(packet["source_surface"]["origin"].get("title")),
            },
            query_slice={
                "qid": _stringify(packet.get("review_entity_qid")),
                "fields": list(parsed_page.get("query_rows", [])),
                "summary": "query rows from parsed page",
            },
            split_bundle={
                "primary_qid": _stringify(packet.get("review_entity_qid")),
                "fields": [
                    axis.get("property")
                    for axis in packet["split_review_context"].get("merged_split_axes", [])
                    if isinstance(axis, Mapping)
                ],
                "summary": _stringify(packet["split_review_context"].get("suggested_action")),
            },
        )
        semantic_decomposition["reviewer_actions"] = (
            build_wikidata_review_packet_reviewer_actions(packet)
        )
        if auto_comparison_variants:
            semantic_decomposition["variant_comparison"] = compare_review_packet_variants(
                primary_variant={
                    "candidate_id": packet["split_review_context"].get("split_plan_id"),
                    "suggested_action": packet["split_review_context"].get("suggested_action"),
                    "merged_split_axes": packet["split_review_context"].get("merged_split_axes", []),
                    "action": packet["split_review_context"].get("suggested_action"),
                },
                comparison_variants=auto_comparison_variants,
            )
        else:
            semantic_decomposition["variant_comparison"] = {
                "non_authoritative": True,
                "diagnostic_flags": ["no_comparisons_provided"],
                "comparisons": [],
            }
        packet["semantic_decomposition"] = semantic_decomposition
    return packet


def build_nat_cohort_c_population_scan(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if _stringify(payload.get("cohort_id")) != "non_ghg_protocol_or_missing_p459":
        raise ValueError("Cohort C population scan requires the Cohort C payload")
    sample_candidates = [
        {
            "qid": _stringify(candidate.get("qid")),
            "label": _stringify(candidate.get("label")),
            "p459_status": _stringify(candidate.get("p459_status")),
            "qualifier_snippet": _stringify(candidate.get("qualifier_snippet")),
            "policy_note": _stringify(candidate.get("policy_note")),
        }
        for candidate in payload.get("sample_candidates", [])
        if isinstance(candidate, Mapping)
    ]
    p459_status_counts: dict[str, int] = {}
    for candidate in sample_candidates:
        status = candidate["p459_status"] or "unknown"
        p459_status_counts[status] = p459_status_counts.get(status, 0) + 1
    return {
        "lane_id": _stringify(payload.get("lane_id")),
        "cohort_id": _stringify(payload.get("cohort_id")),
        "selection_rule": _stringify(payload.get("selection_rule")),
        "source_revision_fixture": _stringify(payload.get("source_revision_fixture")),
        "scan_status": "review_first_population_scan_ready",
        "next_gate": _stringify(payload.get("next_gate")),
        "sample_candidates": sample_candidates,
        "summary": {
            "candidate_count": len(sample_candidates),
            "p459_status_counts": p459_status_counts,
            "review_first": True,
            "policy_risk": "high",
        },
        "notes": list(payload.get("notes", []))
        if isinstance(payload.get("notes"), list)
        else [],
    }


def _sparql_nat_cohort_c_population_scan_query(*, row_limit: int) -> str:
    return f"""
SELECT ?item ?itemLabel ?statement ?p459 ?p459Label ?qualifier_pid
WHERE {{
  ?item p:P5991 ?statement .
  OPTIONAL {{
    ?statement pq:P459 ?p459 .
    OPTIONAL {{
      ?p459 rdfs:label ?p459Label .
      FILTER(LANG(?p459Label) = "en")
    }}
  }}
  OPTIONAL {{
    ?statement ?pq ?qv .
    FILTER(STRSTARTS(STR(?pq), "http://www.wikidata.org/prop/qualifier/"))
    BIND(STRAFTER(STR(?pq), "http://www.wikidata.org/prop/qualifier/") AS ?qualifier_pid)
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
  FILTER(!BOUND(?p459) || !BOUND(?p459Label) || LCASE(STR(?p459Label)) != "ghg protocol")
}}
LIMIT {max(1, int(row_limit))}
""".strip()


def build_nat_cohort_c_population_scan_from_sparql_results(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    bindings = payload.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        raise ValueError("SPARQL payload requires a results.bindings array")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in bindings:
        if not isinstance(row, Mapping):
            continue
        item = row.get("item", {}).get("value") if isinstance(row.get("item"), Mapping) else None
        statement = (
            row.get("statement", {}).get("value") if isinstance(row.get("statement"), Mapping) else None
        )
        if not item or not statement:
            continue
        qid = _extract_qid(_stringify(item))
        statement_id = _extract_qid(_stringify(statement))
        item_label = (
            row.get("itemLabel", {}).get("value")
            if isinstance(row.get("itemLabel"), Mapping)
            else None
        )
        p459 = row.get("p459", {}).get("value") if isinstance(row.get("p459"), Mapping) else None
        p459_label = (
            row.get("p459Label", {}).get("value")
            if isinstance(row.get("p459Label"), Mapping)
            else None
        )
        qualifier_pid = (
            row.get("qualifier_pid", {}).get("value")
            if isinstance(row.get("qualifier_pid"), Mapping)
            else None
        )
        candidate = grouped.setdefault(
            (qid, statement_id),
            {
                "qid": qid,
                "label": _stringify(item_label) or qid,
                "statement_id": statement_id,
                "has_p459": p459 is not None,
                "p459_label": _stringify(p459_label),
                "qualifier_properties": set(),
            },
        )
        if qualifier_pid:
            candidate["qualifier_properties"].add(_stringify(qualifier_pid))

    sample_candidates: list[dict[str, Any]] = []
    p459_status_counts: dict[str, int] = {}
    for (qid, statement_id), candidate in sorted(grouped.items()):
        p459_label = _stringify(candidate.get("p459_label"))
        p459_status = "missing" if not candidate.get("has_p459") else "non_GHG_protocol"
        qualifier_properties = sorted(candidate.get("qualifier_properties", set()))
        sample_candidates.append(
            {
                "qid": qid,
                "label": _stringify(candidate.get("label")) or qid,
                "statement_id": statement_id,
                "p459_status": p459_status,
                "p459_label": p459_label if p459_label else None,
                "qualifier_properties": qualifier_properties,
                "qualifier_snippet": (
                    "determination method missing"
                    if p459_status == "missing"
                    else f"determination method label: {p459_label or 'unlabelled'}"
                ),
                "policy_note": (
                    "live candidate lacks determination method"
                    if p459_status == "missing"
                    else "live candidate uses a non-GHG protocol determination method"
                ),
            }
        )
        p459_status_counts[p459_status] = p459_status_counts.get(p459_status, 0) + 1

    return {
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "non_ghg_protocol_or_missing_p459",
        "selection_rule": "determination method or standard (P459) is missing or not GHG protocol",
        "source_revision_fixture": "live_query_preview",
        "scan_status": "live_population_scan_preview",
        "next_gate": "review_first_population_scan",
        "sample_candidates": sample_candidates,
        "summary": {
            "candidate_count": len(sample_candidates),
            "p459_status_counts": p459_status_counts,
            "review_first": True,
            "policy_risk": "high",
        },
        "notes": [
            "This live preview stays bounded and review-first.",
            "It is diagnostic, not a migration or promotion authority.",
        ],
    }


def build_nat_cohort_c_population_scan_live(
    *,
    row_limit: int = 20,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    query = _sparql_nat_cohort_c_population_scan_query(row_limit=row_limit)
    try:
        payload = _http_get_json(
            SPARQL_ENDPOINT,
            params={"format": "json", "query": query},
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return {
            "lane_id": "wikidata_nat_wdu_p5991_p14143",
            "cohort_id": "non_ghg_protocol_or_missing_p459",
            "selection_rule": "determination method or standard (P459) is missing or not GHG protocol",
            "source_revision_fixture": "live_query_preview",
            "scan_status": "live_population_scan_unavailable",
            "next_gate": "review_first_population_scan",
            "sample_candidates": [],
            "summary": {
                "candidate_count": 0,
                "p459_status_counts": {},
                "review_first": True,
                "policy_risk": "high",
            },
            "failures": [
                {
                    "stage": "live_query",
                    "error": _stringify(exc),
                    "endpoint": SPARQL_ENDPOINT,
                }
            ],
            "notes": [
                "The live preview helper is fail-closed when the Wikidata query endpoint is unavailable.",
            ],
        }
    if not isinstance(payload, Mapping):
        raise ValueError("Cohort C live scan requires a JSON object payload")
    return build_nat_cohort_c_population_scan_from_sparql_results(payload)


def _source_unit_scope_tags(source: Mapping[str, Any], *, line_text: str) -> tuple[str, ...]:
    tags = set(_extract_scope_tags_from_text(line_text))
    tags.update(_extract_scope_tags_from_text(_stringify(source.get("source_id", ""))))
    tags.update(_extract_scope_tags_from_text(_stringify(source.get("source_unit_id", ""))))
    metadata = source.get("metadata")
    if isinstance(metadata, Mapping):
        tags.update(_normalize_string_list(metadata.get("scope_tags")))
    return tuple(sorted(tag for tag in tags if tag))


def _iter_climate_text_line_spans(text: str) -> Iterable[tuple[int, int, str]]:
    cursor = 0
    for line in text.splitlines(keepends=True):
        line_start = cursor
        line_end = cursor + len(line.rstrip("\n"))
        yield line_start, line_end, line.rstrip("\n")
        cursor += len(line)
    if not text:
        return


def adapt_legacy_climate_text_source_to_source_units(payload: Mapping[str, Any]) -> dict[str, Any]:
    if _stringify(payload.get("schema_version", "")) != WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION:
        raise ValueError(
            f"climate text payload must use {WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION}"
        )
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("climate text payload requires a sources array")

    source_units: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("climate text source rows must be objects")
        source_units.append(
            {
                "source_id": _stringify(source.get("source_id", "")).strip(),
                "entity_qid": _stringify(source.get("entity_qid", "")).strip(),
                "source_unit_id": _stringify(source.get("source_unit_id", "")).strip(),
                "revision": {
                    "revision_id": _stringify(source.get("revision_id", "")).strip(),
                    "revision_timestamp": _stringify(source.get("revision_timestamp", "")).strip(),
                    "retrieval_method": "pdf_snapshot",
                },
                "origin": {
                    "source_type": "pdf",
                    "source_url": source.get("source_url"),
                    "title": source.get("title"),
                },
                "content": {
                    "format": "text",
                    "text": _stringify(source.get("text", "")),
                },
                "anchors": [],
                "metadata": {},
            }
        )
    return {"schema_version": SOURCE_UNIT_SCHEMA_VERSION, "source_units": source_units}


def _source_units_from_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    schema_version = _stringify(payload.get("schema_version", ""))
    if schema_version == WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION:
        payload = adapt_legacy_climate_text_source_to_source_units(payload)
        schema_version = SOURCE_UNIT_SCHEMA_VERSION
    if schema_version != SOURCE_UNIT_SCHEMA_VERSION:
        raise ValueError(
            f"source payload must use {SOURCE_UNIT_SCHEMA_VERSION} or {WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION}"
        )
    source_units = payload.get("source_units")
    if not isinstance(source_units, list):
        raise ValueError("source unit payload requires a source_units array")
    return source_units


def _extract_climate_text_rows_from_source_unit(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    source_id = _stringify(source.get("source_id", "")).strip()
    entity_qid = _stringify(source.get("entity_qid", "")).strip()
    source_unit_id = _stringify(source.get("source_unit_id", "")).strip()
    revision = source.get("revision")
    content = source.get("content")
    if not isinstance(revision, Mapping) or not isinstance(content, Mapping):
        raise ValueError("source units require revision and content objects")
    revision_id = _stringify(revision.get("revision_id", "")).strip()
    revision_timestamp = _stringify(revision.get("revision_timestamp", "")).strip()
    text = _stringify(content.get("text", ""))
    if not source_id or not entity_qid or not source_unit_id or not revision_id or not revision_timestamp or not text:
        raise ValueError(
            "source units require source_id, entity_qid, source_unit_id, revision.revision_id, revision.revision_timestamp, and content.text"
        )

    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for line_start, line_end, line in _iter_climate_text_line_spans(text):
        if not line.strip():
            continue
        lowered = line.lower()
        if not any(term in lowered for term in CLIMATE_TEXT_CUE_TERMS):
            continue
        match = None
        for pattern in CLIMATE_TEXT_LINE_PATTERNS:
            match = pattern.search(line)
            if match:
                break
        if match is None:
            continue
        year = match.group("year")
        value = _normalize_climate_numeric_value(match.group("value"))
        dedupe_key = (entity_qid, year, value)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        rows.append(
            {
                "entity_qid": entity_qid,
                "source_id": source_id,
                "source_unit_id": source_unit_id,
                "source_quote": line.strip(),
                "source_span": {
                    "start_char": line_start,
                    "end_char": line_end,
                },
                "observed_at": year,
                "object_value": value,
                "scope_tags": list(_source_unit_scope_tags(source, line_text=line)),
                "revision_id": revision_id,
                "revision_timestamp": revision_timestamp,
            }
        )
    return rows


def build_observation_claim_payload_from_source_units(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    source_units = _source_units_from_payload(payload)

    observations: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence_links: list[dict[str, Any]] = []

    for source in source_units:
        if not isinstance(source, Mapping):
            raise ValueError("source units must be objects")
        for row in _extract_climate_text_rows_from_source_unit(source):
            key = (
                f"{row['entity_qid']}|{row['source_unit_id']}|{row['observed_at']}|"
                f"{row['object_value']}|{row['source_span']['start_char']}-{row['source_span']['end_char']}"
            )
            suffix = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
            observation_id = f"obs:climate:{suffix}"
            claim_id = f"claim:climate:{suffix}"
            link_id = f"link:climate:{suffix}"

            observation = {
                "observation_id": observation_id,
                "source_unit_id": row["source_unit_id"],
                "source_quote": row["source_quote"],
                "source_span": row["source_span"],
                "evidence_refs": [
                    {
                        "span_ref": (
                            f"{row['source_unit_id']}:{row['source_span']['start_char']}-"
                            f"{row['source_span']['end_char']}"
                        ),
                        "ref_type": "text_span",
                    }
                ],
                "status": "active",
                "canonicality": "verified",
                "payload_version": "sl.observation_claim.contract.v1",
                "asserted_at": row["revision_timestamp"],
                "observed_at": row["observed_at"],
            }
            observation["hash"] = _stable_digest(observation)

            claim = {
                "claim_id": claim_id,
                "observation_id": observation_id,
                "predicate": CLIMATE_TEXT_PREDICATE,
                "subject_id": row["entity_qid"],
                "object_id": row["object_value"],
                "subject_type": "entity",
                "object_type": "quantity",
                "norm_id": None,
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.9,
                "claim_created_at": row["revision_timestamp"],
                "claim_updated_at": row["revision_timestamp"],
                "evidence_links": [link_id],
            }
            claim["hash"] = _stable_digest(claim)

            evidence_link = {
                "link_id": link_id,
                "claim_id": claim_id,
                "observation_id": observation_id,
                "source_unit_id": row["source_unit_id"],
                "link_kind": "supporting",
                "span_ref": (
                    f"{row['source_unit_id']}:{row['source_span']['start_char']}-"
                    f"{row['source_span']['end_char']}"
                ),
                "trace_refs": [
                    f"revision:{row['revision_id']}",
                    f"source:{row['source_id']}",
                ] + [f"scope_tag:{tag}" for tag in row.get("scope_tags", [])],
            }
            evidence_link["link_hash"] = _stable_digest(evidence_link)

            observations.append(observation)
            claims.append(claim)
            evidence_links.append(evidence_link)

    return {
        "payload_version": "sl.observation_claim.contract.v1",
        "observations": observations,
        "claims": claims,
        "evidence_links": evidence_links,
    }


def build_observation_claim_payload_from_revision_locked_climate_text_sources(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return build_observation_claim_payload_from_source_units(payload)


def build_wikidata_phi_text_bridge_case(
    candidate: Mapping[str, Any],
    *,
    text_observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_id = _stringify(candidate.get("candidate_id", ""))
    if not candidate_id:
        raise ValueError("candidate requires candidate_id")
    claim_bundle = candidate.get("claim_bundle_before")
    if not isinstance(claim_bundle, Mapping):
        raise ValueError("candidate requires claim_bundle_before")

    normalized_observations = [_normalize_text_observation(row) for row in text_observations]
    bundle_subject = _stringify(claim_bundle.get("subject", ""))
    bundle_value = _stringify(claim_bundle.get("value"))
    bundle_qualifiers = _normalize_bridge_qualifiers(claim_bundle.get("qualifiers"))
    bundle_temporal_values = set(_bridge_temporal_values(bundle_qualifiers))
    bundle_temporal_years = set(_bridge_temporal_years(bundle_qualifiers))
    bundle_scope_values = set(_bridge_scope_values(bundle_qualifiers))

    alignment: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    missing_dimensions: list[dict[str, Any]] = []
    aligned_objects: set[str] = set()
    text_temporal_signatures: set[tuple[str, ...]] = set()
    text_scope_signatures: set[tuple[str, ...]] = set()

    for observation in normalized_observations:
        checks: list[str] = []
        observation_qualifiers = _normalize_bridge_qualifiers(observation.get("qualifiers"))
        temporal_values = _bridge_temporal_values(observation_qualifiers)
        temporal_years = set(_bridge_temporal_years(observation_qualifiers))
        scope_values = _bridge_scope_values(observation_qualifiers)
        if observation["subject"] == bundle_subject:
            checks.append("subject_match")
        else:
            conflicts.append(
                {
                    "observation_ref": observation["observation_ref"],
                    "kind": "subject_mismatch",
                    "detail": f"text subject {observation['subject']} != bundle subject {bundle_subject}",
                }
            )

        if observation["object"] == bundle_value:
            checks.append("value_match")
            aligned_objects.add(observation["object"])
        elif bundle_temporal_years and temporal_years and bundle_temporal_years.isdisjoint(temporal_years):
            missing_dimensions.append(
                {
                    "kind": "value_mismatch_outside_bundle_period",
                    "detail": (
                        f"text observation {observation['observation_ref']} carries year(s) "
                        f"{sorted(temporal_years)} outside bundle year(s) {sorted(bundle_temporal_years)}"
                    ),
                }
            )
        elif bundle_scope_values and scope_values and bundle_scope_values != set(scope_values):
            missing_dimensions.append(
                {
                    "kind": "value_mismatch_outside_bundle_scope",
                    "detail": (
                        f"text observation {observation['observation_ref']} carries scope tag(s) "
                        f"{list(scope_values)} outside bundle scope value(s) {sorted(bundle_scope_values)}"
                    ),
                }
            )
        else:
            conflicts.append(
                {
                    "observation_ref": observation["observation_ref"],
                    "kind": "value_mismatch",
                    "detail": f"text object {observation['object']} != bundle value {bundle_value}",
                }
            )

        if temporal_values:
            text_temporal_signatures.add(temporal_values)
            if bundle_temporal_values and set(temporal_values) == bundle_temporal_values:
                checks.append("temporal_match")
            elif not bundle_temporal_values:
                missing_dimensions.append(
                    {
                        "kind": "bundle_missing_temporal_dimension",
                        "detail": f"text observation {observation['observation_ref']} carries temporal detail absent from the structured bundle",
                    }
                )
            else:
                missing_dimensions.append(
                    {
                        "kind": "temporal_dimension_mismatch",
                        "detail": f"text temporal values {list(temporal_values)} do not match bundle temporal values {sorted(bundle_temporal_values)}",
                    }
                )

        if scope_values:
            text_scope_signatures.add(scope_values)
            if bundle_scope_values and set(scope_values) == bundle_scope_values:
                checks.append("scope_match")
            elif not bundle_scope_values:
                missing_dimensions.append(
                    {
                        "kind": "bundle_missing_scope_dimension",
                        "detail": (
                            f"text observation {observation['observation_ref']} carries scope tag(s) absent "
                            "from the structured bundle"
                        ),
                    }
                )
            else:
                missing_dimensions.append(
                    {
                        "kind": "scope_dimension_mismatch",
                        "detail": (
                            f"text scope tag(s) {list(scope_values)} do not match bundle scope value(s) "
                            f"{sorted(bundle_scope_values)}"
                        ),
                    }
                )

        if checks:
            alignment.append({"observation_ref": observation["observation_ref"], "checks": checks})

    if len(text_temporal_signatures) > 1:
        missing_dimensions.append(
            {
                "kind": "multiple_text_temporal_slices",
                "detail": "text observations describe more than one temporal slice for the same structured candidate",
            }
        )

    if len({observation["object"] for observation in normalized_observations}) > 1:
        missing_dimensions.append(
            {
                "kind": "multiple_text_values",
                "detail": "text observations describe more than one object value for the same structured candidate",
            }
        )

    if len(text_scope_signatures) > 1:
        missing_dimensions.append(
            {
                "kind": "multiple_text_scope_slices",
                "detail": "text observations describe more than one scope slice for the same structured candidate",
            }
        )

    if conflicts:
        pressure = "contradiction"
        pressure_confidence = 0.78
        pressure_summary = "Promoted text observations conflict with the current structured bundle."
    elif missing_dimensions:
        pressure = "split_pressure"
        pressure_confidence = 0.82
        pressure_summary = "Promoted text observations suggest that the current structured bundle compresses multiple dimensions."
    elif alignment:
        pressure = "reinforce"
        pressure_confidence = 0.9
        pressure_summary = "Promoted text observations reinforce the current structured bundle."
    else:
        pressure = "abstain"
        pressure_confidence = 0.2
        pressure_summary = "Promoted text observations did not provide enough aligned support."

    return {
        "schema_version": WIKIDATA_PHI_TEXT_BRIDGE_CASE_SCHEMA_VERSION,
        "bridge_case_ref": f"bridge://wikidata/{candidate_id}",
        "candidate_id": candidate_id,
        "structured_bundle": {
            "candidate_id": candidate_id,
            "entity_qid": _stringify(candidate.get("entity_qid", "")),
            "slot_id": _stringify(candidate.get("slot_id", "")),
            "statement_index": int(candidate.get("statement_index", 0)),
            "classification": _stringify(candidate.get("classification", "")),
            "action": _stringify(candidate.get("action", "")),
            "claim_bundle_before": deepcopy(claim_bundle),
            "claim_bundle_after": deepcopy(candidate.get("claim_bundle_after", {})),
        },
        "text_observations": normalized_observations,
        "comparison": {
            "alignment": alignment,
            "conflicts": conflicts,
            "missing_dimensions": missing_dimensions,
            "comparison_summary": pressure_summary,
        },
        "pressure": pressure,
        "pressure_confidence": pressure_confidence,
        "pressure_summary": pressure_summary,
    }


def attach_wikidata_phi_text_bridge(
    migration_pack: Mapping[str, Any],
    *,
    observations_by_candidate: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    enriched = deepcopy(dict(migration_pack))
    candidates = enriched.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    bridge_cases: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("migration pack candidates must be objects")
        candidate_id = _stringify(candidate.get("candidate_id", ""))
        observation_rows = list(observations_by_candidate.get(candidate_id, []))
        if not observation_rows:
            candidate.setdefault("text_evidence_refs", [])
            candidate.setdefault("bridge_case_ref", None)
            candidate.setdefault("pressure", None)
            candidate.setdefault("pressure_confidence", None)
            candidate.setdefault("pressure_summary", None)
            continue
        bridge_case = build_wikidata_phi_text_bridge_case(candidate, text_observations=observation_rows)
        bridge_cases.append(bridge_case)
        candidate["text_evidence_refs"] = [row["observation_ref"] for row in bridge_case["text_observations"]]
        candidate["bridge_case_ref"] = bridge_case["bridge_case_ref"]
        candidate["pressure"] = bridge_case["pressure"]
        candidate["pressure_confidence"] = bridge_case["pressure_confidence"]
        candidate["pressure_summary"] = bridge_case["pressure_summary"]

    enriched["bridge_cases"] = bridge_cases
    return enriched


def attach_wikidata_phi_text_bridge_from_observation_claim(
    migration_pack: Mapping[str, Any],
    *,
    observation_claim_payload: Mapping[str, Any],
    predicate_allowlist: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidates = migration_pack.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    observations_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = _stringify(candidate.get("candidate_id", ""))
        entity_qid = _stringify(candidate.get("entity_qid", ""))
        if not candidate_id or not entity_qid:
            continue
        observations_by_candidate[candidate_id] = extract_phi_text_observations_from_observation_claim_payload(
            observation_claim_payload,
            subject_id=entity_qid,
            predicate_allowlist=predicate_allowlist,
        )

    return attach_wikidata_phi_text_bridge(
        migration_pack,
        observations_by_candidate=observations_by_candidate,
    )


def attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(
    migration_pack: Mapping[str, Any],
    *,
    climate_text_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    observation_claim_payload = build_observation_claim_payload_from_revision_locked_climate_text_sources(
        climate_text_payload
    )
    enriched = attach_wikidata_phi_text_bridge_from_observation_claim(
        migration_pack,
        observation_claim_payload=observation_claim_payload,
        predicate_allowlist=(CLIMATE_TEXT_PREDICATE,),
    )
    return enriched, observation_claim_payload


def attach_wikidata_phi_text_bridge_from_source_units(
    migration_pack: Mapping[str, Any],
    *,
    source_unit_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    observation_claim_payload = build_observation_claim_payload_from_source_units(source_unit_payload)
    enriched = attach_wikidata_phi_text_bridge_from_observation_claim(
        migration_pack,
        observation_claim_payload=observation_claim_payload,
        predicate_allowlist=(CLIMATE_TEXT_PREDICATE,),
    )
    return enriched, observation_claim_payload


def _stringify(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _claim_bundle_signature(raw: Mapping[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_span_ref(span_ref: str) -> dict[str, Any] | None:
    if ":" not in span_ref or "-" not in span_ref:
        return None
    tail = span_ref.rsplit(":", 1)[-1]
    start_text, sep, end_text = tail.partition("-")
    if not sep or not start_text.isdigit() or not end_text.isdigit():
        return None
    return {"start": int(start_text), "end": int(end_text)}


def extract_phi_text_observations_from_observation_claim_payload(
    payload: Mapping[str, Any],
    *,
    subject_id: str,
    predicate_allowlist: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if _stringify(payload.get("payload_version", "")) != "sl.observation_claim.contract.v1":
        raise ValueError("observation claim payload must use sl.observation_claim.contract.v1")

    observations = payload.get("observations")
    claims = payload.get("claims")
    evidence_links = payload.get("evidence_links")
    if not isinstance(observations, list) or not isinstance(claims, list) or not isinstance(evidence_links, list):
        raise ValueError("observation claim payload requires observations, claims, and evidence_links arrays")

    observation_index = {
        _stringify(row.get("observation_id", "")): row
        for row in observations
        if isinstance(row, Mapping) and _stringify(row.get("observation_id", ""))
    }
    evidence_link_index = {
        _stringify(row.get("link_id", "")): row
        for row in evidence_links
        if isinstance(row, Mapping) and _stringify(row.get("link_id", ""))
    }
    allowed_predicates = {value.strip() for value in (predicate_allowlist or []) if value and value.strip()}
    out: list[dict[str, Any]] = []

    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        if _stringify(claim.get("subject_id", "")) != subject_id:
            continue
        predicate = _stringify(claim.get("predicate", ""))
        if allowed_predicates and predicate not in allowed_predicates:
            continue
        if _stringify(claim.get("posture", "")) != "asserted":
            continue
        if _stringify(claim.get("evidence_quality", "")) not in {"medium", "high"}:
            continue

        observation = observation_index.get(_stringify(claim.get("observation_id", "")))
        if not isinstance(observation, Mapping):
            continue
        if _stringify(observation.get("status", "")) != "active":
            continue
        if _stringify(observation.get("canonicality", "")) not in {"verified", "adjudicated"}:
            continue

        anchors: list[dict[str, Any]] = []
        source_span = observation.get("source_span")
        if isinstance(source_span, Mapping) and isinstance(source_span.get("start_char"), int) and isinstance(source_span.get("end_char"), int):
            anchors.append(
                {
                    "start": int(source_span["start_char"]),
                    "end": int(source_span["end_char"]),
                    "text": _stringify(observation.get("source_quote", "")),
                }
            )
        else:
            for evidence_ref in observation.get("evidence_refs", []):
                if not isinstance(evidence_ref, Mapping):
                    continue
                parsed = _parse_span_ref(_stringify(evidence_ref.get("span_ref", "")))
                if parsed is None:
                    continue
                parsed["text"] = _stringify(observation.get("source_quote", ""))
                anchors.append(parsed)
        if not anchors:
            continue

        observed_at = claim.get("observed_at")
        if observed_at is None:
            observed_at = observation.get("observed_at")
        qualifiers: dict[str, Any] = {}
        if observed_at is not None:
            qualifiers["P585"] = _stringify(observed_at)
        scope_tags = set(_extract_scope_tags_from_text(_stringify(observation.get("source_quote", ""))))
        for link_id in claim.get("evidence_links", []):
            evidence_link = evidence_link_index.get(_stringify(link_id))
            if not isinstance(evidence_link, Mapping):
                continue
            for trace_ref in evidence_link.get("trace_refs", []):
                trace_text = _stringify(trace_ref)
                if trace_text.startswith("scope_tag:"):
                    scope_value = trace_text.partition(":")[2].strip()
                    if scope_value:
                        scope_tags.add(scope_value)
        if scope_tags:
            qualifiers[SCOPE_QUALIFIER_PROPERTY] = sorted(scope_tags)

        out.append(
            {
                "observation_ref": _stringify(claim.get("claim_id", "")),
                "source_ref": _stringify(observation.get("source_unit_id", "")),
                "anchors": anchors,
                "subject": subject_id,
                "predicate": predicate,
                "object": _stringify(claim.get("object_id")),
                "qualifiers": qualifiers,
                "promotion_status": "promoted_true",
            }
        )

    return out


def _extract_datavalue(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return raw
    value = raw.get("value")
    if isinstance(value, Mapping):
        if "id" in value:
            return value["id"]
        if "text" in value:
            return value["text"]
        if "time" in value:
            return value["time"]
        if "amount" in value:
            return value["amount"]
    return value


def _normalize_value_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, (list, tuple)):
        return tuple(sorted(_stringify(item) for item in value))
    return (_stringify(value),)


def _normalize_qualifiers(raw: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, Mapping):
        items = raw.items()
    elif isinstance(raw, list):
        pairs: list[tuple[str, Any]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("qualifier list entries must be objects")
            prop = item.get("property")
            if prop is None:
                raise ValueError("qualifier list entries require property")
            pairs.append((_stringify(prop), item.get("value")))
        items = pairs
    else:
        raise ValueError("qualifiers must be an object or list")
    return tuple(
        sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in items)
    )


def _normalize_references(raw: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if raw is None:
        return tuple()
    if not isinstance(raw, list):
        raise ValueError("references must be a list")
    blocks: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    for block in raw:
        if not isinstance(block, Mapping):
            raise ValueError("reference blocks must be objects")
        normalized = tuple(
            sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in block.items())
        )
        blocks.append(normalized)
    return tuple(sorted(blocks))


def _parse_bundle(raw: Mapping[str, Any]) -> StatementBundle:
    subject = raw.get("subject")
    prop = raw.get("property")
    if not subject or not prop:
        raise ValueError("statement bundles require subject and property")
    return StatementBundle(
        subject=_stringify(subject),
        property=_stringify(prop),
        value=raw.get("value"),
        rank=_stringify(raw.get("rank", "normal")),
        qualifiers=_normalize_qualifiers(raw.get("qualifiers")),
        references=_normalize_references(raw.get("references")),
    )


def _extract_references_from_wikidata(raw_refs: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if not isinstance(raw_refs, list):
        return tuple()
    blocks: list[dict[str, list[Any]]] = []
    for ref in raw_refs:
        if not isinstance(ref, Mapping):
            continue
        snaks = ref.get("snaks")
        if not isinstance(snaks, Mapping):
            continue
        block: dict[str, list[Any]] = {}
        for prop, snak_list in snaks.items():
            if not isinstance(snak_list, list):
                continue
            values: list[Any] = []
            for snak in snak_list:
                if not isinstance(snak, Mapping):
                    continue
                datavalue = snak.get("datavalue")
                extracted = _extract_datavalue(datavalue)
                if extracted is not None:
                    values.append(extracted)
            if values:
                block[_stringify(prop)] = values
        if block:
            blocks.append(block)
    return _normalize_references(blocks)


def _extract_qualifiers_from_wikidata(raw_quals: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(raw_quals, Mapping):
        return tuple()
    normalized: dict[str, list[Any]] = {}
    for prop, snak_list in raw_quals.items():
        if not isinstance(snak_list, list):
            continue
        values: list[Any] = []
        for snak in snak_list:
            if not isinstance(snak, Mapping):
                continue
            extracted = _extract_datavalue(snak.get("datavalue"))
            if extracted is not None:
                values.append(extracted)
        if values:
            normalized[_stringify(prop)] = values
    return _normalize_qualifiers(normalized)


def load_windows(payload: Mapping[str, Any]) -> tuple[WindowSlice, ...]:
    raw_windows = payload.get("windows")
    if not isinstance(raw_windows, list) or not raw_windows:
        raise ValueError("payload requires non-empty windows list")
    windows: list[WindowSlice] = []
    for index, raw_window in enumerate(raw_windows):
        if not isinstance(raw_window, Mapping):
            raise ValueError("window entries must be objects")
        window_id = raw_window.get("id") or f"window_{index + 1}"
        raw_bundles = raw_window.get("statement_bundles")
        if not isinstance(raw_bundles, list):
            raise ValueError("window entries require statement_bundles list")
        windows.append(
            WindowSlice(
                window_id=_stringify(window_id),
                bundles=tuple(_parse_bundle(bundle) for bundle in raw_bundles),
            )
        )
    return tuple(windows)


def build_slice_from_entity_exports(
    window_sources: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    profile: str | None = None,
    property_filter: Iterable[str] | None = None,
) -> Dict[str, Any]:
    allowed = resolve_property_filter(profile=profile, property_filter=property_filter)
    windows: list[dict[str, Any]] = []
    for window_id, sources in window_sources.items():
        bundles: list[dict[str, Any]] = []
        source_labels: list[str] = []
        for source in sources:
            source_name = _stringify(source.get("_source_path", "unknown"))
            source_labels.append(source_name)
            entities = source.get("entities")
            if not isinstance(entities, Mapping):
                raise ValueError("entity export payload requires top-level entities object")
            for entity_id, entity in sorted(entities.items()):
                if not isinstance(entity, Mapping):
                    continue
                claims = entity.get("claims")
                if not isinstance(claims, Mapping):
                    continue
                for prop in allowed:
                    claim_list = claims.get(prop)
                    if not isinstance(claim_list, list):
                        continue
                    for statement in claim_list:
                        if not isinstance(statement, Mapping):
                            continue
                        mainsnak = statement.get("mainsnak")
                        if not isinstance(mainsnak, Mapping):
                            continue
                        extracted = _extract_datavalue(mainsnak.get("datavalue"))
                        if extracted is None:
                            continue
                        bundles.append(
                            {
                                "subject": _stringify(entity_id),
                                "property": prop,
                                "value": extracted,
                                "rank": _stringify(statement.get("rank", "normal")),
                                "qualifiers": dict(_extract_qualifiers_from_wikidata(statement.get("qualifiers"))),
                                "references": [
                                    {key: list(values) for key, values in block}
                                    for block in _extract_references_from_wikidata(statement.get("references"))
                                ],
                            }
                        )
        windows.append(
            {
                "id": _stringify(window_id),
                "statement_bundles": bundles,
                "source_files": sorted(source_labels),
            }
        )
    return {
        "metadata": {
            "generated_by": "build_slice_from_entity_exports",
            "properties": list(allowed),
        },
        "windows": windows,
    }


def _extract_qid(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _sparql_candidate_query(property_pid: str, *, row_limit: int) -> str:
    return f"""
SELECT ?item ?statement ?qualifier_pid
WHERE {{
  ?item p:{property_pid} ?statement .
  ?statement ?pq ?qv .
  FILTER(STRSTARTS(STR(?pq), "http://www.wikidata.org/prop/qualifier/"))
  BIND(STRAFTER(STR(?pq), "http://www.wikidata.org/prop/qualifier/") AS ?qualifier_pid)
}}
LIMIT {max(1, int(row_limit))}
""".strip()


def _http_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    timeout_seconds: int = 30,
) -> Any:
    response = requests.get(
        url,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=max(1, int(timeout_seconds)),
    )
    response.raise_for_status()
    return response.json()


def _emit_progress(progress_callback: Any, stage: str, details: Mapping[str, Any]) -> None:
    if callable(progress_callback):
        progress_callback(stage, dict(details))


def _collect_current_qualifier_candidates(
    *,
    property_filter: Sequence[str],
    candidate_limit: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for property_pid in property_filter:
        query = _sparql_candidate_query(
            property_pid,
            row_limit=max(candidate_limit * 3, 30),
        )
        try:
            payload = _http_get_json(
                SPARQL_ENDPOINT,
                params={"format": "json", "query": query},
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            failures.append(
                {
                    "stage": "candidate_query",
                    "property_pid": property_pid,
                    "error": _stringify(exc),
                }
            )
            continue
        bindings = payload.get("results", {}).get("bindings", [])
        statement_groups: dict[tuple[str, str], set[str]] = {}
        for row in bindings:
            item_raw = row.get("item", {}).get("value")
            statement_uri = row.get("statement", {}).get("value")
            qualifier_pid = row.get("qualifier_pid", {}).get("value")
            if not item_raw or not statement_uri or not qualifier_pid:
                continue
            qid = _extract_qid(item_raw)
            statement_id = _extract_qid(statement_uri)
            candidate = grouped.setdefault(
                (qid, property_pid),
                {
                    "qid": qid,
                    "label": qid,
                    "property_pid": property_pid,
                    "statement_ids": set(),
                    "qualifier_properties": set(),
                    "statement_qualifier_sets": [],
                },
            )
            candidate["statement_ids"].add(statement_id)
            candidate["qualifier_properties"].add(qualifier_pid)
            statement_groups.setdefault((qid, statement_id), set()).add(qualifier_pid)
        for (qid, statement_id), qualifier_set in statement_groups.items():
            candidate = grouped[(qid, property_pid)]
            candidate["statement_qualifier_sets"].append(tuple(sorted(qualifier_set)))

    results: list[dict[str, Any]] = []
    for (qid, property_pid), candidate in sorted(grouped.items()):
        qualifier_properties = sorted(candidate["qualifier_properties"])
        results.append(
            {
                "qid": qid,
                "label": candidate["label"],
                "property_pid": property_pid,
                "statement_count": len(candidate["statement_ids"]),
                "qualifier_property_count": len(qualifier_properties),
                "qualifier_properties": qualifier_properties,
                "statement_qualifier_sets": sorted(
                    {
                        item
                        for item in candidate["statement_qualifier_sets"]
                    },
                    key=lambda item: (len(item), item),
                ),
            }
        )
    return results, failures


def _fetch_recent_revisions(
    qid: str,
    *,
    revision_limit: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    payload = _http_get_json(
        MEDIAWIKI_API_ENDPOINT,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": qid,
            "rvlimit": max(2, int(revision_limit)),
            "rvprop": "ids|timestamp",
            "format": "json",
        },
        timeout_seconds=timeout_seconds,
    )
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, Mapping) or not pages:
        return []
    page = next(iter(pages.values()))
    revisions = page.get("revisions", [])
    if not isinstance(revisions, list):
        return []
    return [
        {"revid": int(item["revid"]), "timestamp": _stringify(item["timestamp"])}
        for item in revisions
        if isinstance(item, Mapping) and "revid" in item and "timestamp" in item
    ]


def _fetch_entity_export_revision(qid: str, revid: int, *, timeout_seconds: int) -> dict[str, Any]:
    url = ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid)
    payload = _http_get_json(url, timeout_seconds=timeout_seconds)
    if not isinstance(payload, dict):
        raise ValueError(f"entity export must be an object for {qid}@{revid}")
    return payload


def _slot_reports_from_entity_export(
    payload: Mapping[str, Any],
    *,
    property_filter: Sequence[str],
    e0: int = 1,
) -> dict[str, dict[str, Any]]:
    slice_payload = build_slice_from_entity_exports(
        {"scan": [dict(payload)]},
        property_filter=property_filter,
    )
    windows = load_windows(slice_payload)
    return _aggregate_window(windows[0], e0=e0)


def _compare_slot_reports_for_qualifier_drift(
    left_slots: Mapping[str, Mapping[str, Any]],
    right_slots: Mapping[str, Mapping[str, Any]],
    *,
    from_window: str,
    to_window: str,
) -> list[dict[str, Any]]:
    all_slot_ids = sorted(set(left_slots) | set(right_slots))
    findings: list[dict[str, Any]] = []
    for slot_id in all_slot_ids:
        left = left_slots.get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        right = right_slots.get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        signatures_changed = left["qualifier_signatures"] != right["qualifier_signatures"]
        property_set_changed = left["qualifier_property_set"] != right["qualifier_property_set"]
        entropy_delta = round(right["qualifier_entropy"] - left["qualifier_entropy"], 6)
        if not signatures_changed and not property_set_changed and entropy_delta == 0.0:
            continue
        severity = "low"
        if property_set_changed:
            severity = "high"
        elif signatures_changed:
            severity = "medium"
        findings.append(
            {
                "slot_id": slot_id,
                "subject_qid": slot_id.split("|", 1)[0],
                "property_pid": slot_id.split("|", 1)[1],
                "from_window": from_window,
                "to_window": to_window,
                "qualifier_signatures_t1": left["qualifier_signatures"],
                "qualifier_signatures_t2": right["qualifier_signatures"],
                "qualifier_property_set_t1": left["qualifier_property_set"],
                "qualifier_property_set_t2": right["qualifier_property_set"],
                "qualifier_entropy_t1": left["qualifier_entropy"],
                "qualifier_entropy_t2": right["qualifier_entropy"],
                "qualifier_entropy_delta": entropy_delta,
                "severity": severity,
            }
        )
    findings.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}[item["severity"]],
            item["slot_id"],
        )
    )
    return findings


def _score_candidate(candidate: Mapping[str, Any], revisions: Sequence[Mapping[str, Any]]) -> tuple[int, list[str]]:
    property_pid = _stringify(candidate["property_pid"])
    qualifier_properties = set(candidate.get("qualifier_properties", []))
    statement_count = int(candidate.get("statement_count", 0))
    score = PROPERTY_PRIORITY.get(property_pid, 10)
    reasons = [f"property_priority:{PROPERTY_PRIORITY.get(property_pid, 10)}"]
    if len(qualifier_properties) >= 2:
        score += 15
        reasons.append("multi_qualifier_property_bonus:15")
    qualifier_property_points = len(qualifier_properties) * 5
    if qualifier_property_points:
        score += qualifier_property_points
        reasons.append(f"qualifier_property_count_bonus:{qualifier_property_points}")
    if qualifier_properties & TEMPORAL_QUALIFIER_PROPERTIES:
        score += 8
        reasons.append("temporal_qualifier_bonus:8")
    if qualifier_properties & REVIEW_QUALIFIER_PROPERTIES:
        score += 8
        reasons.append("review_qualifier_bonus:8")
    if statement_count > 1:
        statement_bonus = min((statement_count - 1) * 3, 12)
        score += statement_bonus
        reasons.append(f"multi_statement_bonus:{statement_bonus}")
    revision_bonus = min(max(len(revisions) - 1, 0), 10)
    if revision_bonus:
        score += revision_bonus
        reasons.append(f"revision_pair_bonus:{revision_bonus}")
    return score, reasons


def find_qualifier_drift_candidates(
    *,
    property_filter: Iterable[str] | None = None,
    candidate_limit: int = 20,
    revision_limit: int = 5,
    timeout_seconds: int = 30,
    progress_callback: Any | None = None,
) -> Dict[str, Any]:
    allowed = tuple(sorted(set(property_filter or DEFAULT_FIND_QUALIFIER_PROPERTIES)))
    _emit_progress(
        progress_callback,
        "candidate_query_started",
        {
            "section": "wikidata_candidate_query",
            "completed": 0,
            "total": len(allowed),
            "message": "Collecting qualifier-bearing statement candidates.",
        },
    )
    raw_candidates, failures = _collect_current_qualifier_candidates(
        property_filter=allowed,
        candidate_limit=candidate_limit,
        timeout_seconds=timeout_seconds,
    )
    _emit_progress(
        progress_callback,
        "candidate_query_finished",
        {
            "section": "wikidata_candidate_query",
            "completed": len(allowed),
            "total": len(allowed),
            "message": f"Collected {len(raw_candidates)} raw candidates with {len(failures)} failures.",
        },
    )
    if not raw_candidates and failures:
        return {
            "schema_version": FINDER_SCHEMA_VERSION,
            "candidate_query_mode": "per_property_raw_rows_v1",
            "properties": list(allowed),
            "candidate_limit": int(candidate_limit),
            "revision_limit": int(revision_limit),
            "timeout_seconds": int(timeout_seconds),
            "candidate_count": 0,
            "scanned_candidate_count": 0,
            "candidates": [],
            "confirmed_drift_cases": [],
            "stable_baselines": [],
            "failures": failures,
        }
    entity_cache: dict[tuple[str, int], dict[str, Any]] = {}
    ranked_candidates: list[dict[str, Any]] = []
    confirmed_drift_cases: list[dict[str, Any]] = []
    stable_baselines: list[dict[str, Any]] = []

    for index, candidate in enumerate(raw_candidates, start=1):
        qid = candidate["qid"]
        property_pid = candidate["property_pid"]
        _emit_progress(
            progress_callback,
            "revision_metadata_started",
            {
                "section": "wikidata_revision_metadata",
                "completed": index - 1,
                "total": len(raw_candidates),
                "message": f"Fetching recent revisions for {qid} {property_pid}.",
            },
        )
        try:
            revisions = _fetch_recent_revisions(
                qid,
                revision_limit=revision_limit,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            failures.append(
                {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "stage": "revision_metadata",
                    "error": _stringify(exc),
                }
            )
            continue

        score, ranking_reasons = _score_candidate(candidate, revisions)
        ranked_candidates.append(
            {
                **candidate,
                "score": score,
                "ranking_reasons": ranking_reasons,
                "recent_revisions": revisions,
                "recent_revision_ids": [item["revid"] for item in revisions],
            }
        )
        _emit_progress(
            progress_callback,
            "revision_metadata_progress",
            {
                "section": "wikidata_revision_metadata",
                "completed": index,
                "total": len(raw_candidates),
                "message": f"Fetched {len(revisions)} revisions for {qid} {property_pid}.",
            },
        )

    ranked_candidates.sort(
        key=lambda item: (-item["score"], item["qid"], item["property_pid"])
    )

    selected_candidates = ranked_candidates[: max(1, int(candidate_limit))]
    for candidate_index, candidate in enumerate(selected_candidates, start=1):
        qid = candidate["qid"]
        property_pid = candidate["property_pid"]
        revisions = candidate["recent_revision_ids"]
        revision_meta = {
            item["revid"]: item["timestamp"]
            for item in candidate["recent_revisions"]
        }
        if len(revisions) < 2:
            stable_baselines.append(
                {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "score": candidate["score"],
                    "recent_revision_ids": revisions,
                    "scanned_pairs": 0,
                    "status": "insufficient_revisions",
                }
            )
            continue

        found_case = None
        had_failure = False
        scanned_pairs = 0
        total_pairs = max(len(revisions) - 1, 0)
        _emit_progress(
            progress_callback,
            "revision_compare_started",
            {
                "section": "wikidata_revision_compare",
                "completed": candidate_index - 1,
                "total": len(selected_candidates),
                "message": f"Comparing revision windows for {qid} {property_pid}.",
                "candidate_qid": qid,
                "property_pid": property_pid,
                "pair_total": total_pairs,
            },
        )
        for index in range(len(revisions) - 1):
            newer_revid = revisions[index]
            older_revid = revisions[index + 1]
            scanned_pairs += 1
            _emit_progress(
                progress_callback,
                "revision_compare_progress",
                {
                    "section": "wikidata_revision_compare",
                    "completed": candidate_index - 1,
                    "total": len(selected_candidates),
                    "message": f"Compared pair {scanned_pairs}/{max(total_pairs, 1)} for {qid} {property_pid}.",
                    "candidate_qid": qid,
                    "property_pid": property_pid,
                    "pair_completed": scanned_pairs,
                    "pair_total": total_pairs,
                    "from_revision": older_revid,
                    "to_revision": newer_revid,
                },
            )
            try:
                older_payload = entity_cache.setdefault(
                    (qid, older_revid),
                    _fetch_entity_export_revision(
                        qid,
                        older_revid,
                        timeout_seconds=timeout_seconds,
                    ),
                )
                newer_payload = entity_cache.setdefault(
                    (qid, newer_revid),
                    _fetch_entity_export_revision(
                        qid,
                        newer_revid,
                        timeout_seconds=timeout_seconds,
                    ),
                )
                older_slots = _slot_reports_from_entity_export(
                    older_payload,
                    property_filter=(property_pid,),
                )
                newer_slots = _slot_reports_from_entity_export(
                    newer_payload,
                    property_filter=(property_pid,),
                )
                drift = _compare_slot_reports_for_qualifier_drift(
                    older_slots,
                    newer_slots,
                    from_window=str(older_revid),
                    to_window=str(newer_revid),
                )
            except Exception as exc:
                failures.append(
                    {
                        "qid": qid,
                        "label": candidate["label"],
                        "property_pid": property_pid,
                        "stage": "revision_compare",
                        "from_revision": older_revid,
                        "to_revision": newer_revid,
                        "error": _stringify(exc),
                    }
                )
                had_failure = True
                break
            if drift:
                found_case = {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "score": candidate["score"],
                    "ranking_reasons": candidate["ranking_reasons"],
                    "statement_count": candidate["statement_count"],
                    "qualifier_properties": candidate["qualifier_properties"],
                    "from_revision": {
                        "revid": older_revid,
                        "timestamp": revision_meta.get(older_revid, "unknown"),
                    },
                    "to_revision": {
                        "revid": newer_revid,
                        "timestamp": revision_meta.get(newer_revid, "unknown"),
                    },
                    "qualifier_drift": drift,
                    "entity_export_urls": {
                        "from": ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=older_revid),
                        "to": ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=newer_revid),
                    },
                    "suggested_fixture_stem": f"{qid.lower()}_{property_pid.lower()}_{older_revid}_{newer_revid}",
                }
                break
        if found_case:
            confirmed_drift_cases.append(found_case)
            _emit_progress(
                progress_callback,
                "revision_compare_finished",
                {
                    "section": "wikidata_revision_compare",
                    "completed": candidate_index,
                    "total": len(selected_candidates),
                    "status": "confirmed_drift",
                    "message": f"Confirmed qualifier drift for {qid} {property_pid}.",
                    "candidate_qid": qid,
                    "property_pid": property_pid,
                    "pair_completed": scanned_pairs,
                    "pair_total": total_pairs,
                },
            )
            continue
        if had_failure:
            _emit_progress(
                progress_callback,
                "revision_compare_finished",
                {
                    "section": "wikidata_revision_compare",
                    "completed": candidate_index,
                    "total": len(selected_candidates),
                    "status": "failed",
                    "message": f"Failed to compare revisions for {qid} {property_pid}.",
                    "candidate_qid": qid,
                    "property_pid": property_pid,
                    "pair_completed": scanned_pairs,
                    "pair_total": total_pairs,
                },
            )
            continue
        stable_baselines.append(
            {
                "qid": qid,
                "label": candidate["label"],
                "property_pid": property_pid,
                "score": candidate["score"],
                "recent_revision_ids": revisions,
                "scanned_pairs": scanned_pairs,
                "status": "stable",
            }
        )
        _emit_progress(
            progress_callback,
            "revision_compare_finished",
            {
                "section": "wikidata_revision_compare",
                "completed": candidate_index,
                "total": len(selected_candidates),
                "status": "stable",
                "message": f"No qualifier drift found for {qid} {property_pid}.",
                "candidate_qid": qid,
                "property_pid": property_pid,
                "pair_completed": scanned_pairs,
                "pair_total": total_pairs,
            },
        )

    return {
        "schema_version": FINDER_SCHEMA_VERSION,
        "candidate_query_mode": "per_property_raw_rows_v1",
        "properties": list(allowed),
        "candidate_limit": int(candidate_limit),
        "revision_limit": int(revision_limit),
        "timeout_seconds": int(timeout_seconds),
        "candidate_count": len(ranked_candidates),
        "scanned_candidate_count": len(confirmed_drift_cases) + len(stable_baselines),
        "candidates": ranked_candidates[: max(1, int(candidate_limit))],
        "confirmed_drift_cases": confirmed_drift_cases,
        "stable_baselines": stable_baselines,
        "failures": failures,
    }


def _qualifier_signature(qualifiers: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    return json.dumps(qualifiers, ensure_ascii=False, separators=(",", ":"))


def _reference_signature(
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
) -> str:
    return json.dumps(references, ensure_ascii=False, separators=(",", ":"))


def _reference_property_set(
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
) -> list[str]:
    return sorted({prop for block in references for prop, _ in block})


def _reference_metrics(
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
) -> tuple[int, int, int]:
    n_blocks = len(references)
    distinct_sources = set()
    has_time = 0
    for block in references:
        for prop, values in block:
            if prop == "P248":
                distinct_sources.update(values)
            if prop in {"P577", "P813", "retrieved", "publication_date"} and values:
                has_time = 1
    return n_blocks, len(distinct_sources), has_time


def _project_bundle(bundle: StatementBundle, *, e0: int) -> Dict[str, Any]:
    n_refs, n_sources, has_time = _reference_metrics(bundle.references)
    evidence = min(n_refs + n_sources + has_time, 9)
    tau = 0
    if evidence >= e0:
        if bundle.rank == "preferred":
            tau = 1
        elif bundle.rank == "deprecated":
            tau = -1
    return {
        "tau": tau,
        "evidence": evidence,
        "conflict": 0,
        "audit": {
            "rule_ids": ["base", "quals", "refs", "rank"],
            "rank": bundle.rank,
            "qualifier_signature": _qualifier_signature(bundle.qualifiers),
            "reference_signature": _reference_signature(bundle.references),
            "reference_block_count": n_refs,
            "distinct_sources": n_sources,
            "has_time_reference": bool(has_time),
        },
    }


def _aggregate_window(window: WindowSlice, *, e0: int) -> Dict[str, Any]:
    slots: dict[tuple[str, str], dict[str, Any]] = {}
    for bundle in window.bundles:
        slot_key = (bundle.subject, bundle.property)
        projected = _project_bundle(bundle, e0=e0)
        slot = slots.setdefault(
            slot_key,
            {
                "subject_qid": bundle.subject,
                "property_pid": bundle.property,
                "bundle_count": 0,
                "taus": [],
                "sum_e": 0,
                "sum_c": 0,
                "audit": [],
                "qualifier_signatures": [],
                "qualifier_property_sets": [],
                "reference_signatures": [],
                "reference_property_sets": [],
                "value_set": set(),
            },
        )
        qualifier_props = tuple(prop for prop, _ in bundle.qualifiers)
        slot["bundle_count"] += 1
        slot["taus"].append(projected["tau"])
        slot["sum_e"] += projected["evidence"]
        slot["sum_c"] += projected["conflict"]
        slot["audit"].append(projected["audit"])
        slot["qualifier_signatures"].append(projected["audit"]["qualifier_signature"])
        slot["qualifier_property_sets"].append(qualifier_props)
        slot["reference_signatures"].append(projected["audit"]["reference_signature"])
        slot["reference_property_sets"].append(tuple(_reference_property_set(bundle.references)))
        slot["value_set"].add(_stringify(bundle.value))

    result_slots: dict[str, dict[str, Any]] = {}
    for subject, prop in sorted(slots):
        slot = slots[(subject, prop)]
        signature_counts: dict[str, int] = {}
        for signature in slot["qualifier_signatures"]:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        total_signatures = len(slot["qualifier_signatures"]) or 1
        qualifier_entropy = 0.0
        for count in signature_counts.values():
            probability = count / total_signatures
            qualifier_entropy -= probability * math.log2(probability)
        qualifier_property_set = sorted(
            {
                prop_name
                for prop_tuple in slot["qualifier_property_sets"]
                for prop_name in prop_tuple
            }
        )
        reference_property_set = sorted(
            {
                prop_name
                for prop_tuple in slot["reference_property_sets"]
                for prop_name in prop_tuple
            }
        )
        taus = set(slot["taus"])
        if taus == {1}:
            tau_star = 1
        elif taus == {-1}:
            tau_star = -1
        elif 1 in taus and -1 in taus:
            tau_star = 0
            slot["sum_c"] += 1
        else:
            tau_star = 0
        result_slots[f"{subject}|{prop}"] = {
            "subject_qid": subject,
            "property_pid": prop,
            "tau": tau_star,
            "sum_e": slot["sum_e"],
            "sum_c": slot["sum_c"],
            "bundle_count": slot["bundle_count"],
            "audit": slot["audit"],
            "qualifier_signatures": sorted(signature_counts),
            "qualifier_property_set": qualifier_property_set,
            "qualifier_entropy": round(qualifier_entropy, 6),
            "reference_signatures": sorted(set(slot["reference_signatures"])),
            "reference_property_set": reference_property_set,
            "value_set": sorted(slot["value_set"]),
        }
    return result_slots


def _compare_slot_reports_for_reference_drift(
    left_slots: Mapping[str, Mapping[str, Any]],
    right_slots: Mapping[str, Mapping[str, Any]],
    *,
    from_window: str,
    to_window: str,
) -> list[dict[str, Any]]:
    all_slot_ids = sorted(set(left_slots) | set(right_slots))
    findings: list[dict[str, Any]] = []
    for slot_id in all_slot_ids:
        left = left_slots.get(
            slot_id,
            {
                "reference_signatures": [],
                "reference_property_set": [],
            },
        )
        right = right_slots.get(
            slot_id,
            {
                "reference_signatures": [],
                "reference_property_set": [],
            },
        )
        signatures_changed = left["reference_signatures"] != right["reference_signatures"]
        property_set_changed = left["reference_property_set"] != right["reference_property_set"]
        if not signatures_changed and not property_set_changed:
            continue
        severity = "low"
        if property_set_changed:
            severity = "high"
        elif signatures_changed:
            severity = "medium"
        findings.append(
            {
                "slot_id": slot_id,
                "subject_qid": slot_id.split("|", 1)[0],
                "property_pid": slot_id.split("|", 1)[1],
                "from_window": from_window,
                "to_window": to_window,
                "reference_signatures_t1": left["reference_signatures"],
                "reference_signatures_t2": right["reference_signatures"],
                "reference_property_set_t1": left["reference_property_set"],
                "reference_property_set_t2": right["reference_property_set"],
                "severity": severity,
            }
        )
    findings.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}[item["severity"]],
            item["slot_id"],
        )
    )
    return findings


def _build_edges(window: WindowSlice, prop: str) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for bundle in window.bundles:
        if bundle.property != prop:
            continue
        target = _stringify(bundle.value)
        edges.append((bundle.subject, target))
    return sorted(edges)


def _tarjan_scc(edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    nodes = set()
    for source, target in edges:
        nodes.add(source)
        nodes.add(target)
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])
    for neighbors in adjacency.values():
        neighbors.sort()

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while stack:
                current = stack.pop()
                on_stack.remove(current)
                component.append(current)
                if current == node:
                    break
            components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    return sorted((component for component in components if len(component) > 1), key=lambda c: (len(c), c))


def _find_mixed_order_nodes(window: WindowSlice) -> list[dict[str, Any]]:
    roles: dict[str, set[str]] = {}
    evidence: dict[str, list[dict[str, str]]] = {}
    for bundle in window.bundles:
        if bundle.property == "P31":
            roles.setdefault(bundle.subject, set()).add("subject_p31")
            value = _stringify(bundle.value)
            roles.setdefault(value, set()).add("value_p31")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P31", "role": "subject", "value_qid": value}
            )
            evidence.setdefault(value, []).append(
                {"property_pid": "P31", "role": "value", "subject_qid": bundle.subject}
            )
        elif bundle.property == "P279":
            target = _stringify(bundle.value)
            roles.setdefault(bundle.subject, set()).add("subject_p279")
            roles.setdefault(target, set()).add("value_p279")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P279", "role": "subject", "value_qid": target}
            )
            evidence.setdefault(target, []).append(
                {"property_pid": "P279", "role": "value", "subject_qid": bundle.subject}
            )

    findings: list[dict[str, Any]] = []
    for node in sorted(roles):
        node_roles = roles[node]
        if "subject_p31" in node_roles and ("subject_p279" in node_roles or "value_p279" in node_roles):
            findings.append(
                {
                    "qid": node,
                    "roles": sorted(node_roles),
                    "audit_trace": sorted(
                        evidence.get(node, []),
                        key=lambda item: (
                            item["property_pid"],
                            item["role"],
                            item.get("subject_qid", ""),
                            item.get("value_qid", ""),
                        ),
                    ),
                }
            )
    return findings


def _find_metaclass_candidates(window: WindowSlice) -> list[dict[str, Any]]:
    incoming_p31: dict[str, int] = {}
    higher_order_targets: set[str] = set()
    for bundle in window.bundles:
        if bundle.property == "P31":
            target = _stringify(bundle.value)
            incoming_p31[target] = incoming_p31.get(target, 0) + 1
        if bundle.property in {"P31", "P279"}:
            higher_order_targets.add(bundle.subject)

    findings: list[dict[str, Any]] = []
    for target in sorted(incoming_p31):
        if target not in higher_order_targets:
            continue
        incoming = incoming_p31[target]
        findings.append(
            {
                "qid": target,
                "p31_incoming_count": incoming,
                "metaclass_ratio": 1.0,
            }
        )
    return findings


def _infer_node_type(
    node: str, instances: set[str], classes: set[str]
) -> str:
    if node in instances and node in classes:
        return "ambiguous"
    if node in instances:
        return "instance"
    if node in classes:
        return "class"
    return "unknown"


def _build_parthood_typing(window: WindowSlice) -> dict[str, Any]:
    instances: set[str] = set()
    classes: set[str] = set()
    for bundle in window.bundles:
        if bundle.property != "P31":
            continue
        instances.add(bundle.subject)
        classes.add(_stringify(bundle.value))

    parthood_edges: set[tuple[str, str, str]] = set()
    for bundle in window.bundles:
        if bundle.property not in PARTHOOD_PROPERTIES:
            continue
        subject = bundle.subject
        value = _stringify(bundle.value)
        parthood_edges.add((bundle.property, subject, value))

    typing_rows: list[dict[str, Any]] = []
    redundant_pairs: set[tuple[str, str, str]] = set()
    counts: dict[str, int] = {
        "class->class": 0,
        "instance->class": 0,
        "instance->instance": 0,
        "ambiguous": 0,
        "abstained": 0,
        "mixed_redundant": 0,
        "cross_property_inverse": 0,
    }
    for property_pid, subject, value in sorted(parthood_edges):
        subject_type = _infer_node_type(subject, instances, classes)
        value_type = _infer_node_type(value, instances, classes)
        bucket = "abstained"
        confidence = "abstain"
        reasons: list[str] = []
        inverse_properties: list[str] = []
        for inverse_property in sorted(PARTHOOD_INVERSE_RELATIONS.get(property_pid, frozenset())):
            if (inverse_property, value, subject) in parthood_edges:
                inverse_properties.append(inverse_property)
        inverse_present = bool(inverse_properties)
        inverse_relation = (
            "same_property_redundant" if property_pid in inverse_properties else "cross_property_expected" if inverse_present else "none"
        )

        if subject_type == "class" and value_type == "class":
            bucket = "class->class"
        elif subject_type == "instance" and value_type == "class":
            bucket = "instance->class"
        elif subject_type == "instance" and value_type == "instance":
            bucket = "instance->instance"
        elif subject_type == "ambiguous" or value_type == "ambiguous":
            bucket = "ambiguous"
            reasons.append("ambiguous_node_type")
        elif subject_type == "unknown" or value_type == "unknown":
            bucket = "abstained"
            reasons.append("insufficient_classification_evidence")
        else:
            bucket = "mixed"
            reasons.append("mixed_type_profile")

        if bucket in {"class->class", "instance->class", "instance->instance"}:
            confidence = "certain"
            counts[bucket] += 1
        elif bucket == "ambiguous":
            counts["ambiguous"] += 1
        else:
            counts["abstained"] += 1

        if inverse_relation == "cross_property_expected":
            counts["cross_property_inverse"] += 1

        if inverse_relation == "same_property_redundant" and bucket in {"class->class", "instance->instance"}:
            pair_key = (property_pid, *sorted((subject, value)))
            if pair_key not in redundant_pairs:
                counts["mixed_redundant"] += 1
                redundant_pairs.add(pair_key)

        typing_rows.append(
            {
                "slot_id": f"{subject}|{property_pid}|{value}",
                "subject_qid": subject,
                "value_qid": value,
                "property_pid": property_pid,
                "bucket": bucket,
                "subject_type": subject_type,
                "value_type": value_type,
                "classification": confidence,
                "inverse_properties": inverse_properties,
                "inverse_relation": inverse_relation,
                "reasons": sorted(set(reasons)),
                "inverse_present": inverse_present,
                "mixed_redundancy_flag": inverse_relation == "same_property_redundant" and bucket == "instance->instance",
            }
        )

    return {
        "classifications": sorted(
            typing_rows,
            key=lambda item: (item["property_pid"], item["subject_qid"], item["value_qid"]),
        ),
        "counts": counts,
    }


def _build_qualifier_drift(
    slot_reports: Mapping[str, Mapping[str, Mapping[str, Any]]],
    windows: Sequence[WindowSlice],
) -> list[dict[str, Any]]:
    if len(windows) < 2:
        return []
    first = windows[0].window_id
    second = windows[1].window_id
    return _compare_slot_reports_for_qualifier_drift(
        slot_reports[first],
        slot_reports[second],
        from_window=first,
        to_window=second,
    )


def _build_reference_drift(
    slot_reports: Mapping[str, Mapping[str, Mapping[str, Any]]],
    windows: Sequence[WindowSlice],
) -> list[dict[str, Any]]:
    if len(windows) < 2:
        return []
    first = windows[0].window_id
    second = windows[1].window_id
    return _compare_slot_reports_for_reference_drift(
        slot_reports[first],
        slot_reports[second],
        from_window=first,
        to_window=second,
    )


def _bundle_to_claim_bundle(bundle: StatementBundle, *, window_id: str, property_override: str | None = None) -> dict[str, Any]:
    return {
        "subject": bundle.subject,
        "property": property_override or bundle.property,
        "value": _stringify(bundle.value),
        "rank": bundle.rank,
        "qualifiers": {prop: list(values) for prop, values in bundle.qualifiers},
        "references": [{prop: list(values) for prop, values in block} for block in bundle.references],
        "window_id": window_id,
    }


def build_wikidata_migration_pack(
    payload: Mapping[str, Any],
    *,
    source_property: str,
    target_property: str,
    e0: int = 1,
) -> dict[str, Any]:
    windows = load_windows(payload)
    if not windows:
        raise ValueError("payload requires at least one window")
    filtered_windows = tuple(
        WindowSlice(
            window_id=window.window_id,
            bundles=tuple(bundle for bundle in window.bundles if bundle.property == source_property),
        )
        for window in windows
    )
    current_window = filtered_windows[-1]
    previous_window = filtered_windows[-2] if len(filtered_windows) >= 2 else None

    slot_reports: dict[str, dict[str, Any]] = {}
    for window in filtered_windows:
        slot_reports[window.window_id] = _aggregate_window(window, e0=e0)

    qualifier_drift = _build_qualifier_drift(slot_reports, filtered_windows)
    reference_drift = _build_reference_drift(slot_reports, filtered_windows)
    qualifier_drift_by_slot = {row["slot_id"]: row for row in qualifier_drift}
    reference_drift_by_slot = {row["slot_id"]: row for row in reference_drift}

    bundles_by_slot: dict[str, list[StatementBundle]] = {}
    for bundle in current_window.bundles:
        bundles_by_slot.setdefault(f"{bundle.subject}|{bundle.property}", []).append(bundle)

    candidates: list[dict[str, Any]] = []
    counts_by_bucket: dict[str, int] = {}
    checked_safe_subset: list[str] = []
    abstained: list[str] = []
    ambiguous: list[str] = []

    for slot_id in sorted(bundles_by_slot):
        slot_bundles = bundles_by_slot[slot_id]
        current_slot = slot_reports[current_window.window_id].get(slot_id, {})
        previous_slot = slot_reports.get(previous_window.window_id, {}).get(slot_id, {}) if previous_window else {}
        slot_present_in_previous = previous_window is not None and slot_id in slot_reports.get(previous_window.window_id, {})
        qualifier_row = qualifier_drift_by_slot.get(slot_id) if slot_present_in_previous else None
        reference_row = reference_drift_by_slot.get(slot_id) if slot_present_in_previous else None
        distinct_values = set(current_slot.get("value_set", []))

        for index, bundle in enumerate(slot_bundles, start=1):
            classification = "safe_with_reference_transfer" if bundle.references else "safe_equivalent"
            confidence = 0.95 if not bundle.references else 0.9
            requires_review = False
            reasons: list[str] = []
            evidence_gate_met = int(current_slot.get("sum_e", 0)) >= max(int(e0), 1)
            independent_axes = _detect_independent_axes(
                bundle,
                slot_bundles=slot_bundles,
                distinct_values=distinct_values,
            )
            split_reasons = _split_required_reasons(
                bundle,
                slot_bundles=slot_bundles,
                distinct_values=distinct_values,
                independent_axes=independent_axes,
            )

            if not evidence_gate_met:
                classification = "abstain"
                confidence = 0.2
                requires_review = True
                reasons.append("evidence_gate_not_met")
            elif split_reasons:
                classification = "split_required"
                confidence = 0.4
                requires_review = True
                reasons.extend(split_reasons)
            elif reference_row is not None:
                classification = "reference_drift"
                confidence = 0.45
                requires_review = True
                reasons.append(f"reference_drift:{reference_row['severity']}")
            elif qualifier_row is not None:
                classification = "qualifier_drift"
                confidence = 0.45
                requires_review = True
                reasons.append(f"qualifier_drift:{qualifier_row['severity']}")

            candidate_id = f"{slot_id}|{index}"
            action = _suggest_migration_action(classification=classification)
            counts_by_bucket[classification] = counts_by_bucket.get(classification, 0) + 1
            if classification in {"safe_equivalent", "safe_with_reference_transfer"}:
                checked_safe_subset.append(candidate_id)
            elif classification == "abstain":
                abstained.append(candidate_id)
            elif classification == "ambiguous_semantics":
                ambiguous.append(candidate_id)

            qualifier_diff = {
                "status": "no_previous_window" if previous_window is None else "unchanged",
                "from_window": previous_window.window_id if previous_window else None,
                "to_window": current_window.window_id,
                "severity": None,
                "qualifier_property_set_t1": previous_slot.get("qualifier_property_set", []),
                "qualifier_property_set_t2": current_slot.get("qualifier_property_set", []),
                "qualifier_signatures_t1": previous_slot.get("qualifier_signatures", []),
                "qualifier_signatures_t2": current_slot.get("qualifier_signatures", []),
            }
            if qualifier_row is not None:
                qualifier_diff = {
                    "status": "qualifier_drift",
                    **qualifier_row,
                }

            reference_diff = {
                "status": "no_previous_window" if previous_window is None else "unchanged",
                "from_window": previous_window.window_id if previous_window else None,
                "to_window": current_window.window_id,
                "severity": None,
                "reference_property_set_t1": previous_slot.get("reference_property_set", []),
                "reference_property_set_t2": current_slot.get("reference_property_set", []),
                "reference_signatures_t1": previous_slot.get("reference_signatures", []),
                "reference_signatures_t2": current_slot.get("reference_signatures", []),
            }
            if reference_row is not None:
                reference_diff = {
                    "status": "reference_drift",
                    **reference_row,
                }

            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "entity_qid": bundle.subject,
                    "slot_id": slot_id,
                    "statement_index": index,
                    "classification": classification,
                    "action": action,
                    "confidence": round(confidence, 6),
                    "requires_review": requires_review,
                    "reasons": sorted(set(reasons)),
                    "split_axes": independent_axes,
                    "text_evidence_refs": [],
                    "bridge_case_ref": None,
                    "pressure": None,
                    "pressure_confidence": None,
                    "pressure_summary": None,
                    "claim_bundle_before": _bundle_to_claim_bundle(bundle, window_id=current_window.window_id),
                    "claim_bundle_after": _bundle_to_claim_bundle(
                        bundle,
                        window_id=current_window.window_id,
                        property_override=target_property,
                    ),
                    "qualifier_diff": qualifier_diff,
                    "reference_diff": reference_diff,
                }
            )

    candidates.sort(key=lambda item: (item["entity_qid"], item["statement_index"], item["candidate_id"]))
    return {
        "schema_version": MIGRATION_PACK_SCHEMA_VERSION,
        "source_property": source_property,
        "target_property": target_property,
        "window_basis": {
            "current_window_id": current_window.window_id,
            "previous_window_id": previous_window.window_id if previous_window else None,
        },
        "source_slice": {
            "window_ids": [window.window_id for window in filtered_windows],
            "source_property": source_property,
            "target_property": target_property,
        },
        "candidates": candidates,
        "bridge_cases": [],
        "summary": {
            "candidate_count": len(candidates),
            "counts_by_bucket": counts_by_bucket,
            "checked_safe_subset": checked_safe_subset,
            "abstained": abstained,
            "ambiguous": ambiguous,
            "requires_review_count": sum(1 for item in candidates if item["requires_review"]),
        },
    }


def export_migration_pack_openrefine_csv(
    migration_pack: Mapping[str, Any],
    *,
    output_path: str,
) -> dict[str, Any]:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    fieldnames = [
        "candidate_id",
        "entity_qid",
        "slot_id",
        "statement_index",
        "from_property",
        "to_property",
        "value",
        "rank",
        "classification",
        "action",
        "confidence",
        "requires_review",
        "suggested_action",
        "split_axis_count",
        "split_axis_properties",
        "qualifier_drift",
        "reference_drift",
        "qualifier_diff_status",
        "reference_diff_status",
        "qualifier_diff_severity",
        "reference_diff_severity",
        "reference_count",
        "qualifier_count",
        "reason_codes",
        "notes",
    ]

    summary_counts: dict[str, int] = {}
    output_str = _stringify(output_path)
    with open(output_str, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            before = candidate.get("claim_bundle_before", {})
            qualifier_diff = candidate.get("qualifier_diff", {})
            reference_diff = candidate.get("reference_diff", {})
            classification = _stringify(candidate.get("classification"))
            summary_counts[classification] = summary_counts.get(classification, 0) + 1
            reasons = list(candidate.get("reasons", [])) if isinstance(candidate.get("reasons"), list) else []
            split_axes = list(candidate.get("split_axes", [])) if isinstance(candidate.get("split_axes"), list) else []
            split_axis_properties = [
                _stringify(axis.get("property"))
                for axis in split_axes
                if isinstance(axis, Mapping) and axis.get("property")
            ]
            suggested_action = _stringify(
                candidate.get("action")
                or _suggest_migration_action(classification=classification)
            )
            writer.writerow(
                {
                    "candidate_id": _stringify(candidate.get("candidate_id")),
                    "entity_qid": _stringify(candidate.get("entity_qid")),
                    "slot_id": _stringify(candidate.get("slot_id")),
                    "statement_index": _stringify(candidate.get("statement_index")),
                    "from_property": _stringify(before.get("property")),
                    "to_property": _stringify(migration_pack.get("target_property")),
                    "value": _stringify(before.get("value")),
                    "rank": _stringify(before.get("rank")),
                    "classification": classification,
                    "action": suggested_action,
                    "confidence": _stringify(candidate.get("confidence")),
                    "requires_review": "true" if bool(candidate.get("requires_review")) else "false",
                    "suggested_action": suggested_action,
                    "split_axis_count": _stringify(len(split_axes)),
                    "split_axis_properties": "|".join(split_axis_properties),
                    "qualifier_drift": "true" if _stringify(qualifier_diff.get("status")) == "qualifier_drift" else "false",
                    "reference_drift": "true" if _stringify(reference_diff.get("status")) == "reference_drift" else "false",
                    "qualifier_diff_status": _stringify(qualifier_diff.get("status")),
                    "reference_diff_status": _stringify(reference_diff.get("status")),
                    "qualifier_diff_severity": _stringify(qualifier_diff.get("severity")),
                    "reference_diff_severity": _stringify(reference_diff.get("severity")),
                    "reference_count": _stringify(len(before.get("references", [])) if isinstance(before.get("references"), list) else 0),
                    "qualifier_count": _stringify(len(before.get("qualifiers", {})) if isinstance(before.get("qualifiers"), Mapping) else 0),
                    "reason_codes": "|".join(_stringify(item) for item in reasons),
                    "notes": "",
                }
            )

    return {
        "output": output_str,
        "row_count": sum(summary_counts.values()),
        "counts_by_bucket": summary_counts,
    }


def export_migration_pack_checked_safe_csv(
    migration_pack: Mapping[str, Any],
    *,
    output_path: str,
) -> dict[str, Any]:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    fieldnames = [
        "candidate_id",
        "entity_qid",
        "slot_id",
        "statement_index",
        "classification",
        "action",
        "from_property",
        "to_property",
        "value",
        "rank",
        "qualifiers_json",
        "references_json",
        "target_claim_bundle_json",
    ]

    safe_classes = {"safe_equivalent", "safe_with_reference_transfer"}
    output_str = _stringify(output_path)
    row_count = 0
    counts_by_bucket: dict[str, int] = {}
    with open(output_str, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            classification = _stringify(candidate.get("classification"))
            if classification not in safe_classes:
                continue
            before = candidate.get("claim_bundle_before", {})
            after = candidate.get("claim_bundle_after", {})
            counts_by_bucket[classification] = counts_by_bucket.get(classification, 0) + 1
            row_count += 1
            writer.writerow(
                {
                    "candidate_id": _stringify(candidate.get("candidate_id")),
                    "entity_qid": _stringify(candidate.get("entity_qid")),
                    "slot_id": _stringify(candidate.get("slot_id")),
                    "statement_index": _stringify(candidate.get("statement_index")),
                    "classification": classification,
                    "action": _stringify(candidate.get("action") or _suggest_migration_action(classification=classification)),
                    "from_property": _stringify(before.get("property")),
                    "to_property": _stringify(after.get("property") or migration_pack.get("target_property")),
                    "value": _stringify(before.get("value")),
                    "rank": _stringify(before.get("rank")),
                    "qualifiers_json": json.dumps(before.get("qualifiers", {}), ensure_ascii=False, sort_keys=True),
                    "references_json": json.dumps(before.get("references", []), ensure_ascii=False, sort_keys=True),
                    "target_claim_bundle_json": json.dumps(after, ensure_ascii=False, sort_keys=True),
                }
            )

    return {
        "output": output_str,
        "row_count": row_count,
        "counts_by_bucket": counts_by_bucket,
        "export_scope": "checked_safe_subset_only",
    }


def verify_migration_pack_against_after_state(
    migration_pack: Mapping[str, Any],
    after_payload: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    after_windows = load_windows(after_payload)
    if not after_windows:
        raise ValueError("after payload requires at least one window")
    after_window = after_windows[-1]

    bundles_by_slot: dict[str, list[StatementBundle]] = {}
    for bundle in after_window.bundles:
        bundles_by_slot.setdefault(f"{bundle.subject}|{bundle.property}", []).append(bundle)

    safe_classes = {"safe_equivalent", "safe_with_reference_transfer"}
    verification_rows: list[dict[str, Any]] = []
    counts_by_status: dict[str, int] = {}

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        classification = _stringify(candidate.get("classification"))
        if classification not in safe_classes:
            continue

        before_raw = candidate.get("claim_bundle_before")
        after_raw = candidate.get("claim_bundle_after")
        if not isinstance(before_raw, Mapping) or not isinstance(after_raw, Mapping):
            raise ValueError("checked-safe candidates require claim_bundle_before and claim_bundle_after")

        before_bundle = _parse_bundle(before_raw)
        after_bundle = _parse_bundle(after_raw)
        after_slot_bundles = bundles_by_slot.get(f"{after_bundle.subject}|{after_bundle.property}", [])
        source_slot_bundles = bundles_by_slot.get(f"{before_bundle.subject}|{before_bundle.property}", [])

        exact_target_matches = sum(1 for bundle in after_slot_bundles if bundle == after_bundle)
        value_rank_matches = [
            bundle
            for bundle in after_slot_bundles
            if _stringify(bundle.value) == _stringify(after_bundle.value) and bundle.rank == after_bundle.rank
        ]
        qualifier_preserved = any(bundle.qualifiers == after_bundle.qualifiers for bundle in value_rank_matches)
        reference_preserved = any(bundle.references == after_bundle.references for bundle in value_rank_matches)
        source_still_present = any(bundle == before_bundle for bundle in source_slot_bundles)

        if exact_target_matches == 1:
            status = "verified"
        elif exact_target_matches > 1:
            status = "duplicate_target"
        elif value_rank_matches:
            status = "target_present_but_drifted"
        else:
            status = "target_missing"

        counts_by_status[status] = counts_by_status.get(status, 0) + 1
        verification_rows.append(
            {
                "candidate_id": _stringify(candidate.get("candidate_id")),
                "entity_qid": _stringify(candidate.get("entity_qid")),
                "classification": classification,
                "action": _stringify(candidate.get("action")),
                "status": status,
                "exact_target_match_count": exact_target_matches,
                "value_rank_match_count": len(value_rank_matches),
                "qualifier_preserved": qualifier_preserved,
                "reference_preserved": reference_preserved,
                "source_still_present": source_still_present,
                "target_slot_id": f"{after_bundle.subject}|{after_bundle.property}",
                "source_slot_id": f"{before_bundle.subject}|{before_bundle.property}",
            }
        )

    return {
        "schema_version": "sl.wikidata_migration_verification.v0_1",
        "source_property": migration_pack.get("source_property"),
        "target_property": migration_pack.get("target_property"),
        "after_window_id": after_window.window_id,
        "verification_scope": "checked_safe_subset_only",
        "rows": verification_rows,
        "summary": {
            "verified_candidate_count": len(verification_rows),
            "counts_by_status": counts_by_status,
        },
    }


def build_wikidata_split_plan(
    migration_pack: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    candidates_by_slot: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _stringify(candidate.get("classification")) != "split_required":
            continue
        slot_id = _stringify(candidate.get("slot_id"))
        if not slot_id:
            continue
        candidates_by_slot.setdefault(slot_id, []).append(candidate)

    plans: list[dict[str, Any]] = []
    counts_by_status: dict[str, int] = {}

    for slot_id in sorted(candidates_by_slot):
        slot_candidates = sorted(
            candidates_by_slot[slot_id],
            key=lambda item: (
                _stringify(item.get("entity_qid")),
                int(item.get("statement_index", 0) or 0),
                _stringify(item.get("candidate_id")),
            ),
        )
        if not slot_candidates:
            continue

        source_candidate_ids = [_stringify(item.get("candidate_id")) for item in slot_candidates]
        proposed_target_bundles: list[dict[str, Any]] = []
        seen_bundle_signatures: set[str] = set()
        exact_reference_preservation = True
        exact_qualifier_preservation = True
        all_split_actions = True
        merged_axes: dict[tuple[str, str, str], dict[str, Any]] = {}

        for candidate in slot_candidates:
            before = candidate.get("claim_bundle_before", {})
            after = candidate.get("claim_bundle_after", {})
            if not isinstance(before, Mapping) or not isinstance(after, Mapping):
                raise ValueError("split-required candidates require before/after claim bundles")

            exact_reference_preservation = exact_reference_preservation and before.get("references") == after.get("references")
            exact_qualifier_preservation = exact_qualifier_preservation and before.get("qualifiers") == after.get("qualifiers")
            all_split_actions = all_split_actions and _stringify(candidate.get("action")) == "split"

            bundle_signature = _claim_bundle_signature(after)
            if bundle_signature not in seen_bundle_signatures:
                proposed_target_bundles.append(dict(after))
                seen_bundle_signatures.add(bundle_signature)

            for axis in candidate.get("split_axes", []):
                if not isinstance(axis, Mapping):
                    continue
                key = (
                    _stringify(axis.get("property")),
                    _stringify(axis.get("source")),
                    _stringify(axis.get("reason")),
                )
                cardinality = int(axis.get("cardinality", 0) or 0)
                existing = merged_axes.get(key)
                if existing is None or cardinality > int(existing.get("cardinality", 0) or 0):
                    merged_axes[key] = {
                        "property": key[0],
                        "source": key[1],
                        "reason": key[2],
                        "cardinality": cardinality,
                    }

        structurally_decomposable = (
            all_split_actions
            and len(proposed_target_bundles) >= 2
            and len(proposed_target_bundles) == len(slot_candidates)
            and bool(merged_axes)
        )
        status = "structurally_decomposable" if structurally_decomposable else "review_only"
        counts_by_status[status] = counts_by_status.get(status, 0) + 1

        plans.append(
            {
                "split_plan_id": f"split://{slot_id}",
                "entity_qid": _stringify(slot_candidates[0].get("entity_qid")),
                "source_slot_id": slot_id,
                "source_candidate_ids": source_candidate_ids,
                "status": status,
                "review_required": True,
                "merged_split_axes": sorted(
                    merged_axes.values(),
                    key=lambda item: (item["property"], item["source"], item["reason"]),
                ),
                "proposed_target_bundles": proposed_target_bundles,
                "proposed_bundle_count": len(proposed_target_bundles),
                "reference_propagation": "exact" if exact_reference_preservation else "review_required",
                "qualifier_propagation": "exact" if exact_qualifier_preservation else "review_required",
                "suggested_action": "review_structured_split" if structurally_decomposable else "review_only",
            }
        )

    return {
        "schema_version": SPLIT_PLAN_SCHEMA_VERSION,
        "source_property": migration_pack.get("source_property"),
        "target_property": migration_pack.get("target_property"),
        "plans": plans,
        "summary": {
            "plan_count": len(plans),
            "counts_by_status": counts_by_status,
        },
    }


def project_wikidata_payload(
    payload: Mapping[str, Any], *, e0: int = 1, profile: str | None = None, property_filter: Iterable[str] | None = None
) -> Dict[str, Any]:
    windows = load_windows(payload)
    selected_profile = (profile or "default").strip() or "default"
    allowed = resolve_property_filter(profile=selected_profile, property_filter=property_filter)
    filtered_windows = tuple(
        WindowSlice(
            window_id=window.window_id,
            bundles=tuple(bundle for bundle in window.bundles if bundle.property in allowed),
        )
        for window in windows
    )

    window_reports: list[dict[str, Any]] = []
    slot_reports: dict[str, dict[str, Any]] = {}
    for window in filtered_windows:
        slots = _aggregate_window(window, e0=e0)
        slot_reports[window.window_id] = slots
        p279_edges = _build_edges(window, "P279")
        sccs = _tarjan_scc(p279_edges)
        mixed_order_nodes = _find_mixed_order_nodes(window)
        metaclass_candidates = _find_metaclass_candidates(window)
        window_reports.append(
            {
                "id": window.window_id,
                "bundle_count": len(window.bundles),
                "slot_count": len(slots),
                "slots": [slots[key] | {"slot_id": key} for key in sorted(slots)],
                "diagnostics": {
                    "p279_sccs": [
                        {"scc_id": f"{window.window_id}:scc:{idx + 1}", "members": members, "size": len(members)}
                        for idx, members in enumerate(sccs)
                    ],
                    "mixed_order_nodes": mixed_order_nodes,
                    "metaclass_candidates": metaclass_candidates,
                    "parthood_typing": _build_parthood_typing(window),
                },
            }
        )

    unstable_slots: list[dict[str, Any]] = []
    if len(filtered_windows) >= 2:
        first = filtered_windows[0].window_id
        second = filtered_windows[1].window_id
        all_slot_ids = sorted(set(slot_reports[first]) | set(slot_reports[second]))
        for slot_id in all_slot_ids:
            left_present = slot_id in slot_reports[first]
            right_present = slot_id in slot_reports[second]
            left = slot_reports[first].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            right = slot_reports[second].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            delta_e = right["sum_e"] - left["sum_e"]
            delta_c = right["sum_c"] - left["sum_c"]
            indicator = 1 if left["tau"] != right["tau"] else 0
            if indicator or delta_e or delta_c:
                severity = "low"
                if indicator and left["tau"] != 0 and right["tau"] != 0:
                    severity = "high"
                elif indicator:
                    severity = "medium"
                unstable_slots.append(
                    {
                        "slot_id": slot_id,
                        "subject_qid": slot_id.split("|", 1)[0],
                        "property_pid": slot_id.split("|", 1)[1],
                        "from_window": first,
                        "to_window": second,
                        "tau_t1": left["tau"],
                        "tau_t2": right["tau"],
                        "delta_e": delta_e,
                        "delta_c": delta_c,
                        "eii": indicator,
                        "present_in_both": left_present and right_present,
                        "severity": severity,
                    }
                )
        unstable_slots.sort(
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}[item["severity"]],
                -item["eii"],
                -(1 if item["present_in_both"] else 0),
                item["slot_id"],
            )
        )

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in unstable_slots:
        severity_counts[item["severity"]] += 1
    qualifier_drift = _build_qualifier_drift(slot_reports, filtered_windows)
    reference_drift = _build_reference_drift(slot_reports, filtered_windows)
    qualifier_severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in qualifier_drift:
        qualifier_severity_counts[item["severity"]] += 1
    reference_severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in reference_drift:
        reference_severity_counts[item["severity"]] += 1

    review_summary = {
        "next_bounded_slice_recommendation": "Qualifier drift is now active; expand qualifier-bearing slices and review property-set instability before wider ontology phases.",
        "unstable_slot_counts": severity_counts,
        "top_unstable_slot_ids": [item["slot_id"] for item in unstable_slots[:5]],
        "structural_focus": [
            "mixed_order_nodes",
            "p279_sccs",
            "metaclass_candidates",
            "parthood_typing",
        ],
        "qualifier_drift_counts": qualifier_severity_counts,
        "top_qualifier_drift_slot_ids": [item["slot_id"] for item in qualifier_drift[:5]],
        "reference_drift_counts": reference_severity_counts,
        "top_reference_drift_slot_ids": [item["slot_id"] for item in reference_drift[:5]],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "bounded_slice": {
            "profile": selected_profile,
            "properties": list(allowed),
            "window_ids": [window.window_id for window in filtered_windows],
        },
        "assumptions": {
            "rank_evidence_gate_e0": e0,
            "advisory_only": True,
            "tokenizer_lexeme_boundary_preserved": True,
        },
        "windows": window_reports,
        "unstable_slots": unstable_slots,
        "qualifier_drift": qualifier_drift,
        "reference_drift": reference_drift,
        "review_summary": review_summary,
    }


__all__ = [
    "SCHEMA_VERSION",
    "FINDER_SCHEMA_VERSION",
    "DEFAULT_PROPERTY_FILTER",
    "PROPERTY_PROFILES",
    "MIGRATION_PACK_SCHEMA_VERSION",
    "WIKIDATA_CLIMATE_TEXT_SOURCE_SCHEMA_VERSION",
    "SOURCE_UNIT_SCHEMA_VERSION",
    "WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION",
    "adapt_legacy_climate_text_source_to_source_units",
    "build_wikidata_review_packet",
    "build_nat_cohort_c_population_scan",
    "build_nat_cohort_c_population_scan_from_sparql_results",
    "build_nat_cohort_c_population_scan_live",
    "build_observation_claim_payload_from_source_units",
    "build_observation_claim_payload_from_revision_locked_climate_text_sources",
    "attach_wikidata_phi_text_bridge_from_source_units",
    "attach_wikidata_phi_text_bridge_from_revision_locked_climate_text",
    "build_slice_from_entity_exports",
    "build_wikidata_migration_pack",
    "export_migration_pack_openrefine_csv",
    "find_qualifier_drift_candidates",
    "load_windows",
    "project_wikidata_payload",
    "resolve_property_filter",
]
