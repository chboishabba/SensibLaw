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
from src.policy.compiler_contract import build_wikidata_migration_pack_contract
from src.policy.product_gate import build_product_gate


SCHEMA_VERSION = "wikidata_projection_v0_1"
FINDER_SCHEMA_VERSION = "wikidata_qualifier_drift_finder_v0_1"
MIGRATION_PACK_SCHEMA_VERSION = "sl.wikidata_migration_pack.v1"
CANDIDATE_PROMOTION_GATE_SCHEMA_VERSION = "sl.wikidata_candidate_promotion_gate.v0_1"
SPLIT_PLAN_SCHEMA_VERSION = "sl.wikidata_split_plan.v0_1"
WIKIDATA_PHI_TEXT_BRIDGE_CASE_SCHEMA_VERSION = "sl.wikidata_phi_text_bridge_case.v1"
WIKIDATA_CLIMATE_REVIEW_DEMONSTRATOR_SCHEMA_VERSION = (
    "sl.wikidata_climate_review_demonstrator.v0_1"
)
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
GHG_SCOPE_PROPERTIES = frozenset({"P3831", "P518"})
GHG_DETERMINATION_METHOD_PROPERTY = "P459"
GHG_PROTOCOL_QIDS = frozenset({"Q56296245"})
CLIMATE_UNIT_QIDS = frozenset({"Q57084755", "Q57084901"})
PARTHOOD_INVERSE_RELATIONS = {
    "P361": frozenset({"P361", "P527"}),
    "P527": frozenset({"P527", "P361"}),
}
CLIMATE_MODEL_SOURCE_PROPERTIES = frozenset({"P5991"})
CLIMATE_MODEL_TARGET_PROPERTIES = frozenset({"P14143"})
CLIMATE_MODEL_METHOD_PROPERTY = "P459"
CLIMATE_MODEL_SCOPE_PROPERTIES = frozenset({"P3831", "P518"})
CLIMATE_MODEL_ACCEPTED_UNITS = frozenset({"Q57084755", "Q57084901", "co2e"})
SUBJECT_RESOLUTION_SCHEMA_VERSION = "sl.wikidata_subject_resolution.v0_1"
COMPANY_SUBJECT_TYPE_QIDS = frozenset(
    {
        "Q783794",   # company
        "Q6881511",  # enterprise
        "Q4830453",  # business
    }
)
NON_COMPANY_SUBJECT_TYPE_QIDS = frozenset(
    {
        "Q5",        # human
        "Q43229",    # organization
        "Q16334295", # group of humans
        "Q618123",   # geographical object
    }
)
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
    unit: str | None
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
    climate_profile: Mapping[str, Any] | None = None,
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
    if climate_profile is not None:
        climate_status = _stringify(climate_profile.get("status"))
        if climate_status == "split":
            reasons.extend(
                _stringify(reason)
                for reason in climate_profile.get("reasons", [])
                if _stringify(reason).strip()
            )
        elif climate_status == "invalid":
            reasons.extend(
                _stringify(reason)
                for reason in climate_profile.get("reasons", [])
                if _stringify(reason).strip()
            )

    return sorted(set(reasons))


def _extract_year_candidates(values: Sequence[str]) -> tuple[str, ...]:
    years: set[str] = set()
    for value in values:
        for match in re.findall(r"(?:19|20)\d{2}", _stringify(value)):
            years.add(match)
    return tuple(sorted(years))


def _resolve_bundle_year(bundle: StatementBundle) -> tuple[str | None, list[str]]:
    qualifier_map = _bundle_qualifier_map(bundle)
    issues: list[str] = []
    point_years = _extract_year_candidates(qualifier_map.get("P585", ()))
    if len(point_years) == 1:
        return point_years[0], issues
    if len(point_years) > 1:
        issues.append("multiple_point_in_time_years")
        return None, issues

    start_years = _extract_year_candidates(qualifier_map.get("P580", ()))
    end_years = _extract_year_candidates(qualifier_map.get("P582", ()))
    if start_years and end_years:
        if len(start_years) == 1 and len(end_years) == 1 and start_years[0] == end_years[0]:
            return start_years[0], issues
        issues.append("multi_year_range")
        return None, issues
    if start_years or end_years:
        issues.append("partial_time_range")
        return None, issues

    issues.append("missing_time")
    return None, issues


def _extract_bundle_scope_values(bundle: StatementBundle) -> tuple[str, ...]:
    qualifier_map = _bundle_qualifier_map(bundle)
    values: set[str] = set()
    for property_id in GHG_SCOPE_PROPERTIES:
        values.update(_stringify(value) for value in qualifier_map.get(property_id, ()))
    return tuple(sorted(values))


def _extract_bundle_method_values(bundle: StatementBundle) -> tuple[str, ...]:
    qualifier_map = _bundle_qualifier_map(bundle)
    return tuple(sorted(_stringify(value) for value in qualifier_map.get(GHG_DETERMINATION_METHOD_PROPERTY, ())))


def _extract_bundle_unit_id(bundle: StatementBundle) -> str | None:
    if bundle.unit:
        unit = _stringify(bundle.unit).strip()
        if unit.startswith("http://www.wikidata.org/entity/"):
            return _extract_qid(unit)
        if unit:
            return unit
    value = bundle.value
    if isinstance(value, Mapping):
        unit = value.get("unit")
        if unit is not None:
            return _extract_qid(_stringify(unit))
    return None


def _build_candidate_model_validation(
    bundle: StatementBundle,
    *,
    source_property: str,
    target_property: str,
    split_reasons: Sequence[str],
) -> dict[str, Any]:
    if source_property != "P5991" or target_property != "P14143":
        return {
            "lane": "generic",
            "status": "not_applicable",
            "valid": False,
            "issues": [],
            "resolved_year": None,
            "resolved_scope": None,
            "scope_values": [],
            "determination_method_values": [],
            "resolved_unit_qid": None,
            "suggested_action": "review_only",
            "execution_ready": False,
        }

    resolved_year, issues = _resolve_bundle_year(bundle)
    scope_values = list(_extract_bundle_scope_values(bundle))
    method_values = list(_extract_bundle_method_values(bundle))
    unit_id = _extract_bundle_unit_id(bundle)

    if len(scope_values) > 1:
        issues.append("multiple_scope_values")
    if len(method_values) > 1:
        issues.append("multiple_determination_methods")
    if not method_values:
        issues.append("missing_determination_method")
    elif not any(value in GHG_PROTOCOL_QIDS for value in method_values):
        issues.append("non_ghg_protocol_method")
    if unit_id and unit_id not in CLIMATE_UNIT_QIDS:
        issues.append("non_climate_unit")

    resolved_scope = None
    if len(scope_values) == 1:
        resolved_scope = scope_values[0]
    elif not scope_values:
        resolved_scope = "TOTAL"

    execution_ready = bool(
        split_reasons
        and resolved_year
        and "multiple_scope_values" not in issues
        and "multiple_determination_methods" not in issues
        and "multi_year_range" not in issues
        and "partial_time_range" not in issues
        and "multiple_point_in_time_years" not in issues
    )
    if execution_ready:
        status = "model_safe_with_split"
    elif resolved_year and not split_reasons:
        status = "model_safe"
    else:
        status = "model_review_required"
    valid = status in {"model_safe", "model_safe_with_split"}

    return {
        "lane": "ghg_climate_migration",
        "status": status,
        "valid": valid,
        "issues": sorted(set(issues)),
        "resolved_year": resolved_year,
        "resolved_scope": resolved_scope,
        "scope_values": scope_values,
        "determination_method_values": method_values,
        "resolved_unit_qid": unit_id,
        "suggested_action": "migrate_with_split" if execution_ready else "review_only",
        "execution_ready": execution_ready,
    }


def _build_candidate_execution_hints(
    bundle: StatementBundle,
    *,
    target_property: str,
    model_validation: Mapping[str, Any],
) -> dict[str, Any]:
    qualifier_map = _bundle_qualifier_map(bundle)
    execution_backend = "qs3" if bundle.rank in {"preferred", "deprecated"} else "openrefine"
    return {
        "execution_ready": bool(model_validation.get("execution_ready")),
        "target_property": target_property,
        "resolved_year": model_validation.get("resolved_year"),
        "resolved_scope": model_validation.get("resolved_scope"),
        "scope_values": list(model_validation.get("scope_values", [])),
        "determination_method_values": list(model_validation.get("determination_method_values", [])),
        "resolved_unit_qid": model_validation.get("resolved_unit_qid"),
        "qualifier_properties": sorted(qualifier_map),
        "execution_backend": execution_backend,
        "suggested_action": _stringify(model_validation.get("suggested_action")),
    }


def _subject_family_for_candidate(
    *,
    subject_resolution: Mapping[str, Any],
) -> str:
    resolved_family = _stringify(subject_resolution.get("subject_family"))
    if resolved_family in {"company", "non_company", "unknown"}:
        return resolved_family
    return "unknown"


def _build_subject_type_context(window: WindowSlice) -> dict[str, Any]:
    instance_of_by_subject: dict[str, list[str]] = {}
    subclass_of_by_subject: dict[str, list[str]] = {}
    for bundle in window.bundles:
        if bundle.property == "P31":
            instance_of_by_subject.setdefault(bundle.subject, []).append(_stringify(bundle.value))
        elif bundle.property == "P279":
            subclass_of_by_subject.setdefault(bundle.subject, []).append(_stringify(bundle.value))
    return {
        "instance_of_by_subject": {
            qid: sorted({value for value in values if value})
            for qid, values in instance_of_by_subject.items()
        },
        "subclass_of_by_subject": {
            qid: sorted({value for value in values if value})
            for qid, values in subclass_of_by_subject.items()
        },
    }


def _collect_subject_type_ancestors(
    *,
    type_qids: Sequence[str],
    subclass_of_by_subject: Mapping[str, Sequence[str]],
) -> tuple[list[str], list[dict[str, str]], list[str]]:
    ancestors: set[str] = set()
    traversal: list[dict[str, str]] = []
    ambiguous_roots: list[str] = []
    stack: list[tuple[str, str | None]] = [(_stringify(type_qid), None) for type_qid in type_qids if _stringify(type_qid)]
    seen: set[str] = set()
    while stack:
        current, parent = stack.pop()
        if not current or current in seen:
            continue
        seen.add(current)
        ancestors.add(current)
        if parent is not None:
            traversal.append({"from_qid": parent, "to_qid": current, "property": "P279"})
        for parent_qid in subclass_of_by_subject.get(current, ()):
            normalized_parent = _stringify(parent_qid)
            if not normalized_parent:
                continue
            if normalized_parent in COMPANY_SUBJECT_TYPE_QIDS and normalized_parent in NON_COMPANY_SUBJECT_TYPE_QIDS:
                ambiguous_roots.append(normalized_parent)
            stack.append((normalized_parent, current))
    return sorted(ancestors), traversal, sorted(set(ambiguous_roots))


def _build_subject_resolution(
    *,
    entity_qid: str,
    window: WindowSlice,
) -> dict[str, Any]:
    type_context = _build_subject_type_context(window)
    instance_of_by_subject = type_context["instance_of_by_subject"]
    subclass_of_by_subject = type_context["subclass_of_by_subject"]
    direct_instance_of = list(instance_of_by_subject.get(entity_qid, ()))
    if not direct_instance_of:
        return {
            "schema_version": SUBJECT_RESOLUTION_SCHEMA_VERSION,
            "status": "unresolved",
            "subject_family": "unknown",
            "resolution_basis": "no_typed_evidence",
            "window_id": window.window_id,
            "direct_instance_of": [],
            "resolved_via": None,
            "matched_type_qids": [],
            "traversed_subclass_of": [],
            "evidence": [],
        }

    ancestry_qids, traversed_subclass_of, _ = _collect_subject_type_ancestors(
        type_qids=direct_instance_of,
        subclass_of_by_subject=subclass_of_by_subject,
    )
    company_matches = sorted(qid for qid in ancestry_qids if qid in COMPANY_SUBJECT_TYPE_QIDS)
    non_company_matches = sorted(qid for qid in ancestry_qids if qid in NON_COMPANY_SUBJECT_TYPE_QIDS)
    evidence = [
        {
            "property": "P31",
            "subject_qid": entity_qid,
            "value_qid": value_qid,
            "window_id": window.window_id,
        }
        for value_qid in direct_instance_of
    ] + [
        {
            "property": edge["property"],
            "subject_qid": edge["from_qid"],
            "value_qid": edge["to_qid"],
            "window_id": window.window_id,
        }
        for edge in traversed_subclass_of
    ]

    if company_matches and not non_company_matches:
        subject_family = "company"
        status = "resolved"
        resolution_basis = "typed_evidence"
        resolved_via = "p31_p279_chain"
        matched_type_qids = company_matches
    elif non_company_matches and not company_matches:
        subject_family = "non_company"
        status = "resolved"
        resolution_basis = "typed_evidence"
        resolved_via = "p31_p279_chain"
        matched_type_qids = non_company_matches
    else:
        subject_family = "unknown"
        status = "unresolved"
        resolution_basis = "conflicting_typed_evidence" if company_matches and non_company_matches else "typed_evidence_not_mapped"
        resolved_via = None
        matched_type_qids = sorted(set(company_matches + non_company_matches))

    return {
        "schema_version": SUBJECT_RESOLUTION_SCHEMA_VERSION,
        "status": status,
        "subject_family": subject_family,
        "resolution_basis": resolution_basis,
        "window_id": window.window_id,
        "direct_instance_of": direct_instance_of,
        "resolved_via": resolved_via,
        "matched_type_qids": matched_type_qids,
        "traversed_subclass_of": traversed_subclass_of,
        "evidence": evidence,
    }


def _ghg_semantic_family_for_candidate(
    *,
    model_validation: Mapping[str, Any],
) -> str:
    resolved_scope = _stringify(model_validation.get("resolved_scope"))
    scope_values = [_stringify(value) for value in model_validation.get("scope_values", []) if _stringify(value).strip()]
    if resolved_scope and resolved_scope != "TOTAL":
        return "scope_specific_emissions"
    if resolved_scope == "TOTAL":
        return "absolute_emissions"
    if scope_values:
        return "compound_scope_emissions"
    return "absolute_emissions"


def _reporting_period_kind_for_candidate(
    *,
    claim_bundle_before: Mapping[str, Any],
    model_validation: Mapping[str, Any],
) -> str:
    issues = {_stringify(value) for value in model_validation.get("issues", [])}
    qualifiers = claim_bundle_before.get("qualifiers", {})
    qualifier_keys = {_stringify(key) for key in qualifiers} if isinstance(qualifiers, Mapping) else set()
    if "multi_year_range" in issues:
        return "multi_year_range"
    if "partial_time_range" in issues:
        return "partial_time_range"
    if "multiple_point_in_time_years" in issues:
        return "conflicting_years"
    if "P585" in qualifier_keys:
        return "single_reporting_period"
    if "P580" in qualifier_keys or "P582" in qualifier_keys:
        return "single_interval_period" if _stringify(model_validation.get("resolved_year")).strip() else "fiscal_year"
    return "unresolved"


def _scope_resolution_for_candidate(
    *,
    model_validation: Mapping[str, Any],
) -> str:
    issues = {_stringify(value) for value in model_validation.get("issues", [])}
    if "multiple_scope_values" in issues:
        return "conflicting_scope"
    resolved_scope = _stringify(model_validation.get("resolved_scope"))
    if resolved_scope and resolved_scope != "TOTAL":
        return "explicit_scope"
    if resolved_scope == "TOTAL":
        return "total_unscoped"
    return "unresolved"


def _method_resolution_for_candidate(
    *,
    model_validation: Mapping[str, Any],
) -> str:
    issues = {_stringify(value) for value in model_validation.get("issues", [])}
    method_values = [_stringify(value) for value in model_validation.get("determination_method_values", []) if _stringify(value).strip()]
    if "missing_determination_method" in issues:
        return "missing_but_inferable"
    if "non_ghg_protocol_method" in issues:
        return "recognized_non_ghg_method"
    if method_values:
        return "recognized_method"
    return "unresolved"


def _build_phase2_method_inference(
    *,
    method_resolution: str,
) -> dict[str, Any]:
    if method_resolution == "missing_but_inferable":
        return {
            "status": "pending",
            "method_family": "unspecified_reporting_method",
            "confidence": 0.0,
            "evidence": [],
            "rule_id": "meth.inference_pending.v0_1",
        }
    if method_resolution == "recognized_method":
        return {
            "status": "not_needed",
            "method_family": "direct_reported",
            "confidence": 1.0,
            "evidence": ["explicit_method_qualifier"],
            "rule_id": "meth.explicit_qualifier.v0_1",
        }
    return {
        "status": "not_applicable",
        "method_family": "not_resolved",
        "confidence": 0.0,
        "evidence": [],
        "rule_id": None,
    }


def _build_phase2_scope_inference(
    *,
    scope_resolution: str,
    model_validation: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_scope = _stringify(model_validation.get("resolved_scope"))
    if scope_resolution == "explicit_scope":
        return {
            "status": "not_needed",
            "resolved_scope": resolved_scope.lower(),
            "confidence": 1.0,
            "evidence": ["explicit_scope_qualifier"],
            "rule_id": "scope.explicit_qualifier.v0_1",
        }
    if scope_resolution == "total_unscoped":
        return {
            "status": "not_needed",
            "resolved_scope": "total_unspecified",
            "confidence": 1.0,
            "evidence": ["no_scope_qualifier_present"],
            "rule_id": "scope.total_unscoped.v0_1",
        }
    return {
        "status": "pending",
        "resolved_scope": "not_resolved",
        "confidence": 0.0,
        "evidence": [],
        "rule_id": "scope.inference_pending.v0_1",
    }


def _build_phase2_fiscal_normalization(
    *,
    reporting_period_kind: str,
    model_validation: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_year = _stringify(model_validation.get("resolved_year"))
    if reporting_period_kind == "single_reporting_period":
        return {
            "status": "not_needed",
            "source_period": resolved_year,
            "normalized_year": resolved_year,
            "year_semantics": "calendar_year",
            "confidence": 1.0,
            "rule_id": "fiscal.point_in_time_to_calendar_year.v0_1",
        }
    if reporting_period_kind == "single_interval_period":
        return {
            "status": "normalized",
            "source_period": resolved_year,
            "normalized_year": resolved_year,
            "year_semantics": "fiscal_year_end",
            "confidence": 0.95,
            "rule_id": "fiscal.date_range_to_year_end.v0_1",
        }
    return {
        "status": "pending",
        "source_period": resolved_year or "",
        "normalized_year": resolved_year or None,
        "year_semantics": "unresolved",
        "confidence": 0.0,
        "rule_id": "fiscal.inference_pending.v0_1",
    }


def _build_candidate_family_classifier(
    *,
    source_property: str,
    target_property: str,
    classification: str,
    requires_review: bool,
    reasons: Sequence[str],
    model_validation: Mapping[str, Any],
    claim_bundle_before: Mapping[str, Any],
    subject_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    signals: list[str] = []
    blocking_signals: list[str] = []
    phase2_actions: list[str] = []
    issues = {_stringify(value) for value in model_validation.get("issues", []) if _stringify(value).strip()}
    subject_family = _subject_family_for_candidate(subject_resolution=subject_resolution)
    ghg_semantic_family = _ghg_semantic_family_for_candidate(model_validation=model_validation)
    reporting_period_kind = _reporting_period_kind_for_candidate(
        claim_bundle_before=claim_bundle_before,
        model_validation=model_validation,
    )
    scope_resolution = _scope_resolution_for_candidate(model_validation=model_validation)
    method_resolution = _method_resolution_for_candidate(model_validation=model_validation)

    climate_lane = source_property in CLIMATE_MODEL_SOURCE_PROPERTIES and target_property in CLIMATE_MODEL_TARGET_PROPERTIES
    if climate_lane:
        signals.append("ghg_property_family")
    if _stringify(model_validation.get("resolved_year")).strip():
        signals.append("single_reporting_period")
    if scope_resolution == "explicit_scope":
        signals.append("recognized_scope")
    elif scope_resolution == "total_unscoped":
        signals.append("total_unscoped")
    if method_resolution == "recognized_method":
        signals.append("recognized_method")
    if _stringify(model_validation.get("resolved_unit_qid")).strip():
        signals.append("recognized_unit")
    if classification == "safe_with_reference_transfer":
        signals.append("reference_transfer_safe")
    if classification == "split_required":
        signals.append("deterministic_split_surface")

    if method_resolution == "missing_but_inferable":
        phase2_actions.append("infer_method")
    if scope_resolution == "unresolved":
        phase2_actions.append("infer_scope")
    if reporting_period_kind == "fiscal_year":
        phase2_actions.append("normalize_fiscal_year")
    if not _stringify(model_validation.get("resolved_unit_qid")).strip():
        phase2_actions.append("normalize_unit")

    hard_blocking_issues = {"multi_year_range", "partial_time_range", "multiple_point_in_time_years", "non_climate_unit"}
    ontology_mismatch_issues = {"non_ghg_protocol_method", "multiple_determination_methods", "multiple_scope_values"}
    blocking_signals.extend(sorted(hard_blocking_issues & issues))
    blocking_signals.extend(sorted(ontology_mismatch_issues & issues))
    if classification in {"abstain", "non_equivalent"}:
        blocking_signals.append(f"classification:{classification}")

    if not climate_lane:
        bucket = "E"
        bucket_label = "blocked"
        confidence = 1.0
        explanation = "candidate is outside the bounded GHG migration lane"
    elif hard_blocking_issues & issues or classification == "abstain":
        bucket = "E"
        bucket_label = "blocked"
        confidence = 0.98
        explanation = "hard blocker prevents safe migration or deterministic normalization"
    elif classification in {"ambiguous_semantics", "needs_human_review", "non_equivalent", "qualifier_drift", "reference_drift"} or ontology_mismatch_issues & issues:
        bucket = "D"
        bucket_label = "ontology_mismatch"
        confidence = 0.9
        explanation = "row does not cleanly align to the target GHG ontology without semantic review"
    elif (
        subject_family == "company"
        and (
            classification == "split_required"
            or _stringify(model_validation.get("status")) == "model_safe_with_split"
        )
    ):
        bucket = "B"
        bucket_label = "deterministic_split"
        confidence = 0.9
        explanation = "row is structurally valid but requires deterministic decomposition before promotion"
    elif (
        subject_family == "company"
        and (
        classification in {"safe_equivalent", "safe_with_reference_transfer"}
        and not requires_review
        and _stringify(model_validation.get("status")) == "model_safe"
        and method_resolution == "recognized_method"
        and _stringify(model_validation.get("resolved_unit_qid")).strip()
        and reporting_period_kind in {"single_reporting_period", "single_interval_period"}
        )
    ):
        bucket = "A"
        bucket_label = "clean_direct"
        confidence = 0.97 if classification == "safe_equivalent" else 0.93
        explanation = "single-period GHG row with stable target mapping and no unresolved ontology defect"
    else:
        bucket = "C"
        bucket_label = "phase2_normalizable"
        confidence = 0.82
        explanation = "row is likely salvageable by deterministic normalization rules but is not promotion-safe yet"

    normalization_contract = {
        "phase1_status": "structurally_classified",
        "phase2_eligible": bucket == "C",
        "required_rules": phase2_actions,
        "hard_blockers": sorted(set(blocking_signals)) if bucket == "E" else [],
        "soft_blockers": sorted(set(blocking_signals)) if bucket in {"C", "D"} else [],
    }
    return {
        "schema_version": "sl.ghg_family_classifier.v0_1",
        "bucket": bucket,
        "bucket_label": bucket_label,
        "confidence": round(confidence, 6),
        "signals": sorted(set(signals)),
        "blocking_signals": sorted(set(blocking_signals)),
        "normalization_phase": "phase2" if phase2_actions else "phase1",
        "phase2_needed": bool(phase2_actions),
        "explanation": explanation,
        "subject_resolution": dict(subject_resolution),
        "subject_family": subject_family,
        "ghg_semantic_family": ghg_semantic_family,
        "reporting_period_kind": reporting_period_kind,
        "scope_resolution": scope_resolution,
        "method_resolution": method_resolution,
        "phase2_actions": phase2_actions,
        "normalization_contract": normalization_contract,
        "phase2_method_inference": _build_phase2_method_inference(method_resolution=method_resolution),
        "phase2_scope_inference": _build_phase2_scope_inference(
            scope_resolution=scope_resolution,
            model_validation=model_validation,
        ),
        "phase2_fiscal_normalization": _build_phase2_fiscal_normalization(
            reporting_period_kind=reporting_period_kind,
            model_validation=model_validation,
        ),
    }


def _build_candidate_promotion_gate(
    *,
    classification: str,
    requires_review: bool,
    pressure: str | None,
    pressure_confidence: float | None,
    pressure_summary: str | None,
    model_validation: Mapping[str, Any],
    execution_hints: Mapping[str, Any],
    subject_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    model_status = _stringify(model_validation.get("status"))
    model_valid = bool(model_validation.get("valid"))
    execution_ready = bool(model_validation.get("execution_ready") or execution_hints.get("execution_ready"))
    subject_family = _subject_family_for_candidate(subject_resolution=subject_resolution)
    instance_of_allowed = subject_family == "company"

    if not instance_of_allowed:
        promotion_class = "review_only"
        reason = f"hard_defect:subject_family:{subject_family or 'unknown'}"
    elif not model_valid:
        promotion_class = "review_only"
        reason = "hard_defect:model_validation_invalid"
    elif not execution_ready:
        promotion_class = "review_only"
        reason = "soft_defect:execution_not_ready"
    elif requires_review:
        promotion_class = "review_only"
        reason = f"soft_defect:review_required:{classification}"
    elif classification == "safe_with_reference_transfer":
        promotion_class = "semi_auto"
        reason = "soft_defect:reference_transfer_only"
    elif classification == "safe_equivalent":
        if pressure is None:
            promotion_class = "full_auto"
            reason = "ready:direct_safe_execution"
        else:
            promotion_class = "semi_auto"
            reason = f"soft_defect:pressure:{pressure}"
    else:
        promotion_class = "review_only"
        reason = f"soft_defect:classification:{classification}"

    eligibility = {
        "eligible": promotion_class != "review_only",
        "review_only": promotion_class == "review_only",
        "semi_auto": promotion_class in {"semi_auto", "full_auto"},
        "full_auto": promotion_class == "full_auto",
        "instance_of_allowed": instance_of_allowed,
        "reason": reason,
    }
    return {
        "schema_version": CANDIDATE_PROMOTION_GATE_SCHEMA_VERSION,
        "decision": promotion_class,
        "reason": reason,
        "eligibility": eligibility,
        "evidence": {
            "classification": classification,
            "model_classification": model_status,
            "model_validation_valid": model_valid,
            "execution_ready": execution_ready,
            "requires_review": requires_review,
            "subject_family": subject_family,
            "instance_of_allowed": instance_of_allowed,
            "pressure": pressure,
            "pressure_confidence": pressure_confidence,
            "pressure_summary": pressure_summary,
            "execution_backend": _stringify(execution_hints.get("execution_backend")),
            "suggested_action": _stringify(execution_hints.get("suggested_action")),
        },
    }


def _candidate_defect_kind(candidate: Mapping[str, Any]) -> str:
    promotion_gate = candidate.get("promotion_gate", {})
    if not isinstance(promotion_gate, Mapping):
        promotion_gate = {}
    decision = _stringify(promotion_gate.get("decision"))
    reason = _stringify(promotion_gate.get("reason"))
    if decision == "full_auto":
        return "none"
    if reason.startswith("hard_defect:"):
        return "hard"
    return "soft"


def _build_migration_pack_pilot_surface(
    *,
    candidates: Sequence[Mapping[str, Any]],
    checked_safe_subset: Sequence[str],
    abstained: Sequence[str],
    ambiguous: Sequence[str],
    requires_review_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_count = len(candidates)
    promotion_class_counts: dict[str, int] = {}
    defect_kind_counts: dict[str, int] = {"hard": 0, "soft": 0, "none": 0}
    defect_candidate_ids: dict[str, list[str]] = {"hard": [], "soft": [], "none": []}
    execution_ready_candidate_count = 0
    ready_candidate_count = 0

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = _stringify(candidate.get("candidate_id"))
        promotion_class = _stringify(candidate.get("promotion_class"))
        promotion_class_counts[promotion_class] = promotion_class_counts.get(promotion_class, 0) + 1
        if bool(candidate.get("execution_ready")):
            execution_ready_candidate_count += 1
        if promotion_class == "full_auto":
            ready_candidate_count += 1
        defect_kind = _candidate_defect_kind(candidate)
        defect_kind_counts[defect_kind] = defect_kind_counts.get(defect_kind, 0) + 1
        defect_candidate_ids.setdefault(defect_kind, []).append(candidate_id)

    ready_state = "ready_subset" if ready_candidate_count > 0 else "review_first"
    hard_defect_count = defect_kind_counts.get("hard", 0)
    soft_defect_count = defect_kind_counts.get("soft", 0)
    safe_subset_count = len(checked_safe_subset)
    semi_auto_count = promotion_class_counts.get("semi_auto", 0)
    full_auto_count = promotion_class_counts.get("full_auto", 0)
    review_only_count = promotion_class_counts.get("review_only", 0)

    pilot_metrics = {
        "candidate_count": candidate_count,
        "checked_safe_candidate_count": safe_subset_count,
        "checked_safe_yield": safe_subset_count / candidate_count if candidate_count else 0.0,
        "execution_ready_candidate_count": execution_ready_candidate_count,
        "ready_candidate_count": ready_candidate_count,
        "ready_yield": ready_candidate_count / candidate_count if candidate_count else 0.0,
        "full_auto_candidate_count": full_auto_count,
        "full_auto_rate": full_auto_count / candidate_count if candidate_count else 0.0,
        "semi_auto_candidate_count": semi_auto_count,
        "semi_auto_rate": semi_auto_count / candidate_count if candidate_count else 0.0,
        "review_only_candidate_count": review_only_count,
        "review_only_rate": review_only_count / candidate_count if candidate_count else 0.0,
        "hard_defect_count": hard_defect_count,
        "hard_defect_rate": hard_defect_count / candidate_count if candidate_count else 0.0,
        "soft_defect_count": soft_defect_count,
        "soft_defect_rate": soft_defect_count / candidate_count if candidate_count else 0.0,
        "requires_review_count": requires_review_count,
    }
    readiness_surface = {
        "state": ready_state,
        "hard_defect_count": hard_defect_count,
        "soft_defect_count": soft_defect_count,
        "ready_candidate_count": ready_candidate_count,
        "checked_safe_candidate_count": safe_subset_count,
        "execution_ready_candidate_count": execution_ready_candidate_count,
        "review_only_candidate_count": review_only_count,
        "semi_auto_candidate_count": semi_auto_count,
        "full_auto_candidate_count": full_auto_count,
        "abstained_count": len(abstained),
        "ambiguous_count": len(ambiguous),
    }
    defect_surface = {
        "hard_defect_candidate_ids": defect_candidate_ids.get("hard", []),
        "soft_defect_candidate_ids": defect_candidate_ids.get("soft", []),
        "ready_candidate_ids": defect_candidate_ids.get("none", []),
    }
    return pilot_metrics, {
        "state": ready_state,
        "readiness": readiness_surface,
        "pilot_metrics": pilot_metrics,
        "defect_surface": defect_surface,
    }


def _claim_bundle_qualifier_map(raw: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    qualifiers = raw.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        return {}
    return { _stringify(prop): _normalize_value_list(value) for prop, value in qualifiers.items() }


def _resolve_claim_bundle_year(raw: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    qualifier_map = _claim_bundle_qualifier_map(raw)
    bundle = StatementBundle(
        subject=_stringify(raw.get("subject")),
        property=_stringify(raw.get("property")),
        value=raw.get("value"),
        rank=_stringify(raw.get("rank")),
        unit=_extract_claim_bundle_unit_id(raw),
        qualifiers=tuple(sorted(qualifier_map.items())),
        references=tuple(),
    )
    return _resolve_bundle_year(bundle)


def _extract_claim_bundle_scope_values(raw: Mapping[str, Any]) -> tuple[str, ...]:
    qualifier_map = _claim_bundle_qualifier_map(raw)
    values: set[str] = set()
    for property_id in GHG_SCOPE_PROPERTIES:
        values.update(_stringify(value) for value in qualifier_map.get(property_id, ()))
    return tuple(sorted(values))


def _extract_claim_bundle_method_values(raw: Mapping[str, Any]) -> tuple[str, ...]:
    qualifier_map = _claim_bundle_qualifier_map(raw)
    return tuple(sorted(_stringify(value) for value in qualifier_map.get(GHG_DETERMINATION_METHOD_PROPERTY, ())))


def _extract_claim_bundle_unit_id(raw: Mapping[str, Any]) -> str | None:
    unit = raw.get("unit")
    if unit is not None:
        return _extract_qid(_stringify(unit))
    value = raw.get("value")
    if isinstance(value, Mapping):
        unit = value.get("unit")
        if unit is not None:
            return _extract_qid(_stringify(unit))
    return None


def _build_split_execution_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    claim_after = candidate.get("claim_bundle_after", {})
    if not isinstance(claim_after, Mapping):
        claim_after = {}
    model_validation = candidate.get("model_validation", {})
    if not isinstance(model_validation, Mapping):
        model_validation = {}
    execution_hints = candidate.get("execution_hints", {})
    if not isinstance(execution_hints, Mapping) or not execution_hints:
        execution_hints = candidate.get("execution_profile", {})
    if not isinstance(execution_hints, Mapping):
        execution_hints = {}
    resolved_year, _ = _resolve_claim_bundle_year(claim_after)
    return {
        "candidate_id": _stringify(candidate.get("candidate_id")),
        "subject": _stringify(claim_after.get("subject")),
        "property": _stringify(claim_after.get("property")),
        "value": claim_after.get("value"),
        "rank": _stringify(claim_after.get("rank")),
        "resolved_year": execution_hints.get("resolved_year") or model_validation.get("resolved_year") or resolved_year,
        "scope_values": list(
            execution_hints.get("scope_values")
            or model_validation.get("scope_values")
            or _extract_claim_bundle_scope_values(claim_after)
        ),
        "determination_method_values": list(
            execution_hints.get("determination_method_values")
            or model_validation.get("determination_method_values")
            or _extract_claim_bundle_method_values(claim_after)
        ),
        "resolved_scope": execution_hints.get("resolved_scope") or model_validation.get("resolved_scope"),
        "resolved_unit_qid": execution_hints.get("resolved_unit_qid") or model_validation.get("resolved_unit_qid") or _extract_claim_bundle_unit_id(claim_after),
        "qualifiers": dict(claim_after.get("qualifiers", {})) if isinstance(claim_after.get("qualifiers"), Mapping) else {},
        "references": list(claim_after.get("references", [])) if isinstance(claim_after.get("references"), list) else [],
        "execution_ready": bool(execution_hints.get("execution_ready") or model_validation.get("execution_ready")),
    }


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


def _bundle_qualifier_values(bundle: StatementBundle, property_pid: str) -> tuple[str, ...]:
    qualifier_map = _bundle_qualifier_map(bundle)
    return qualifier_map.get(property_pid, tuple())


def _climate_bundle_years(bundle: StatementBundle) -> tuple[str, ...]:
    qualifier_map = _bundle_qualifier_map(bundle)
    years = set(_bridge_temporal_years(qualifier_map))
    if not years:
        for prop in TEMPORAL_QUALIFIER_PROPERTIES:
            years.update(_extract_property_ids(_stringify(qualifier_map.get(prop, ()))))
    return tuple(sorted(years))


def _climate_bundle_scope_values(bundle: StatementBundle) -> tuple[str, ...]:
    qualifier_map = _bundle_qualifier_map(bundle)
    values = set(_bridge_scope_values(qualifier_map))
    values.update(_stringify(value) for value in _bundle_qualifier_values(bundle, "P518"))
    return tuple(sorted(value for value in values if value))


def _climate_bundle_method_values(bundle: StatementBundle) -> tuple[str, ...]:
    return tuple(sorted(set(_bundle_qualifier_values(bundle, CLIMATE_MODEL_METHOD_PROPERTY))))


def _normalize_climate_unit(unit: str | None) -> str:
    normalized = _stringify(unit).strip()
    if not normalized or normalized == "null":
        return ""
    if normalized.startswith("http://www.wikidata.org/entity/"):
        normalized = normalized.rsplit("/", 1)[-1]
    return normalized.lower()


def _climate_bundle_model_profile(
    bundle: StatementBundle,
    *,
    slot_bundles: Sequence[StatementBundle],
) -> dict[str, Any]:
    has_climate_signal = bool(
        bundle.unit
        or _bundle_qualifier_values(bundle, "P459")
        or _bundle_qualifier_values(bundle, SCOPE_QUALIFIER_PROPERTY)
        or _bundle_qualifier_values(bundle, "P518")
        or _bundle_qualifier_values(bundle, "P580")
        or _bundle_qualifier_values(bundle, "P582")
        or _bundle_qualifier_values(bundle, "P585")
    )
    if not has_climate_signal:
        return {
            "status": "unknown",
            "reasons": [],
            "year_values": tuple(),
            "scope_values": tuple(),
            "method_values": tuple(),
            "unit": "",
            "unit_status": "unknown",
        }

    year_values = _climate_bundle_years(bundle)
    scope_values = _climate_bundle_scope_values(bundle)
    method_values = _climate_bundle_method_values(bundle)
    unit = _normalize_climate_unit(bundle.unit)
    unit_status = "unknown"
    if unit:
        unit_status = "recognized" if unit in CLIMATE_MODEL_ACCEPTED_UNITS else "unrecognized"

    slot_year_signatures = {
        _climate_bundle_years(sibling) for sibling in slot_bundles if _climate_bundle_years(sibling)
    }
    slot_scope_signatures = {
        _climate_bundle_scope_values(sibling) for sibling in slot_bundles if _climate_bundle_scope_values(sibling)
    }
    slot_method_signatures = {
        _climate_bundle_method_values(sibling) for sibling in slot_bundles if _climate_bundle_method_values(sibling)
    }

    reasons: list[str] = []
    status = "direct"
    if not year_values:
        status = "invalid"
        reasons.append("ghg_model_missing_year")
    elif len(year_values) > 1 or len(slot_year_signatures) > 1:
        status = "split"
        reasons.append(f"ghg_model_years={','.join(year_values)}")

    if not method_values:
        if status == "direct":
            status = "invalid"
        reasons.append("ghg_model_missing_determination_method")
    elif len(method_values) > 1 or len(slot_method_signatures) > 1:
        status = "split"
        reasons.append(f"ghg_model_methods={','.join(method_values)}")

    if len(scope_values) > 1 or len(slot_scope_signatures) > 1:
        status = "split"
        reasons.append(f"ghg_model_scopes={','.join(scope_values)}")

    if unit_status == "unrecognized":
        status = "invalid"
        reasons.append(f"ghg_model_unit={unit}")

    if status == "direct":
        reasons.append("ghg_model_direct")
    elif status == "split":
        reasons.append("ghg_model_split_required")
    else:
        reasons.append("ghg_model_invalid")

    return {
        "status": status,
        "reasons": sorted(set(reasons)),
        "year_values": year_values,
        "scope_values": scope_values,
        "method_values": method_values,
        "unit": unit,
        "unit_status": unit_status,
    }


def _climate_model_pressure(
    profile: Mapping[str, Any],
) -> tuple[str | None, float | None, str | None]:
    status = _stringify(profile.get("status"))
    if status == "direct":
        return "reinforce", 0.92, _climate_model_summary(profile)
    if status == "split":
        return "split_pressure", 0.84, _climate_model_summary(profile)
    if status == "invalid":
        return "abstain", 0.2, _climate_model_summary(profile)
    return None, None, None


def _climate_model_summary(profile: Mapping[str, Any]) -> str:
    unit = _stringify(profile.get("unit", "")).strip()
    year_values = ",".join(_stringify(value) for value in profile.get("year_values", []) if _stringify(value).strip())
    scope_values = ",".join(_stringify(value) for value in profile.get("scope_values", []) if _stringify(value).strip())
    method_values = ",".join(_stringify(value) for value in profile.get("method_values", []) if _stringify(value).strip())
    return (
        f"ghg_model={_stringify(profile.get('status'))}"
        f" year={year_values or 'unknown'}"
        f" scope={scope_values or 'none'}"
        f" method={method_values or 'none'}"
        f" unit={unit or 'unknown'}"
    )


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
    grounding_depth_row: Mapping[str, Any] | None = None,
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
    return_recommended_next_step = _stringify(
        split_plan.get("suggested_action", "review_only")
    )
    if grounding_depth_row is not None:
        grounding_gap_class = _stringify(grounding_depth_row.get("grounding_gap_class"))
        recommended_follow_target = _stringify(
            grounding_depth_row.get("recommended_follow_target")
        )
        if grounding_gap_class:
            uncertainty_flags.append(f"grounding_gap_class={grounding_gap_class}")
        if grounding_gap_class == "live_receipts_ready_for_review":
            uncertainty_flags.append("live_receipts_ready_for_review")
            if "review_live_follow_receipts" not in decision_focus:
                decision_focus.append("review_live_follow_receipts")
        if grounding_depth_row.get("live_follow_count"):
            uncertainty_flags.append(
                f"live_follow_receipts={int(grounding_depth_row.get('live_follow_count') or 0)}"
            )
        if recommended_follow_target and recommended_follow_target != _stringify(
            split_plan.get("suggested_action")
        ):
            return_recommended_next_step = recommended_follow_target
    return {
        "decision_focus": decision_focus,
        "uncertainty_flags": uncertainty_flags,
        "recommended_next_step": return_recommended_next_step,
    }


def _packet_grounding_depth_row(
    *,
    grounding_depth_summary: Mapping[str, Any] | None,
    qid: str,
    split_plan_id: str,
) -> dict[str, Any] | None:
    if not isinstance(grounding_depth_summary, Mapping):
        return None
    packets = grounding_depth_summary.get("packets")
    if not isinstance(packets, Sequence):
        return None
    def _normalize_key(value: Any) -> str:
        normalized = _stringify(value).strip()
        return "" if normalized.lower() in {"", "null"} else normalized

    match_qid = _normalize_key(qid)
    target_plan = _normalize_key(split_plan_id)
    for row in packets:
        if not isinstance(row, Mapping):
            continue
        plan_match = _normalize_key(row.get("split_plan_id"))
        if plan_match and target_plan and plan_match != target_plan:
            continue
        if match_qid and _stringify(row.get("qid")) != match_qid:
            continue
        grounding_row = dict(row)
        grounding_gap_class = _stringify(grounding_row.get("grounding_gap_class")).strip()
        if grounding_gap_class.lower() in {"", "null"}:
            grounding_gap_class = _derive_grounding_gap_class(grounding_row)
        if grounding_gap_class == "live_receipts_ready_for_review":
            grounding_row["recommended_follow_target"] = "review_live_follow_receipts"
        else:
            recommended_follow_target = _stringify(
                grounding_row.get("recommended_follow_target")
            ).strip()
            if recommended_follow_target.lower() in {"", "null"}:
                grounding_row["recommended_follow_target"] = (
                    "" if grounding_gap_class == "grounded" else _derive_grounding_recommended_target(
                        grounding_gap_class
                    )
                )
            else:
                grounding_row["recommended_follow_target"] = recommended_follow_target
        live_follow_receipts = grounding_row.get("live_follow_receipts")
        if isinstance(live_follow_receipts, Sequence):
            grounding_row["live_follow_count"] = len(live_follow_receipts)
        grounding_row["grounding_gap_class"] = grounding_gap_class
        return grounding_row
    return None


def _derive_grounding_gap_class(
    grounding_row: Mapping[str, Any],
) -> str:
    status = _stringify(grounding_row.get("grounding_status")).strip()
    if (
        status == "grounded"
        and _stringify(grounding_row.get("live_follow_status")) == "live_receipts_fetched"
        and grounding_row.get("live_follow_receipts")
    ):
        return "live_receipts_ready_for_review"
    if status == "grounded":
        return "grounded"
    evidence = grounding_row.get("revision_evidence")
    if not isinstance(evidence, Sequence):
        evidence = []
    evidence_count = len(evidence)
    if evidence_count == 0:
        return "no_revision_evidence"
    missing = {
        field
        for item in evidence
        if isinstance(item, Mapping)
        for field in item.get("missing_fields", [])
        if _stringify(field).strip()
    }
    if {"excerpt", "excerpt_summary"} <= missing:
        return "revision_evidence_missing"
    if missing:
        return "partial_revision_evidence"
    if (
        _stringify(grounding_row.get("live_follow_status")) == "live_receipts_fetched"
        and grounding_row.get("live_follow_receipts")
    ):
        return "live_receipts_ready_for_review"
    return "ungrounded_other"


def _derive_grounding_recommended_target(gap_class: str) -> str:
    if gap_class == "live_receipts_ready_for_review":
        return "review_live_follow_receipts"
    if gap_class == "no_revision_evidence":
        return "revision_locked_packet"
    if gap_class in {"revision_evidence_missing", "partial_revision_evidence"}:
        return "revision_locked_evidence"
    if gap_class == "grounded":
        return ""
    return "packet_review"


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
    grounding_depth_summary: Mapping[str, Any] | None = None,
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
    review_entity_qid = _stringify(split_plan.get("entity_qid"))
    grounding_depth_row = _packet_grounding_depth_row(
        grounding_depth_summary=grounding_depth_summary,
        qid=review_entity_qid,
        split_plan_id=_stringify(split_plan.get("split_plan_id")),
    )
    packet = {
        "schema_version": WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "review_entity_qid": review_entity_qid,
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
            grounding_depth_row=grounding_depth_row,
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


def build_nat_cohort_c_operator_packet(
    scan_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if _stringify(scan_payload.get("cohort_id")) != "non_ghg_protocol_or_missing_p459":
        raise ValueError("Cohort C operator packet requires the Cohort C payload")
    summary = scan_payload.get("summary")
    summary_payload = summary if isinstance(summary, Mapping) else {}
    sample_candidates = [
        {
            "qid": _stringify(candidate.get("qid")),
            "label": _stringify(candidate.get("label")),
            "p459_status": _stringify(candidate.get("p459_status")),
            "qualifier_snippet": _stringify(candidate.get("qualifier_snippet")),
            "policy_note": _stringify(candidate.get("policy_note")),
        }
        for candidate in scan_payload.get("sample_candidates", [])
        if isinstance(candidate, Mapping)
    ]
    scan_status = _stringify(scan_payload.get("scan_status"))
    unavailable = scan_status == "live_population_scan_unavailable"
    if unavailable:
        decision_text = "hold"
        triage_prompts = [
            "Live query was unavailable; retry later before any cohort claim.",
            "Do not infer migration readiness from an unavailable preview.",
        ]
    else:
        decision_text = "review"
        triage_prompts = [
            "Review the candidate P459 status split before any cohort claim.",
            "Check whether the missing vs non-GHG protocol buckets need different handling.",
            "Keep the lane review-first and fail-closed.",
        ]
    packet_id = hashlib.sha1(
        json.dumps(
            {
                "cohort_id": scan_payload.get("cohort_id"),
                "scan_status": scan_status,
                "candidate_count": len(sample_candidates),
                "candidate_qids": [candidate["qid"] for candidate in sample_candidates],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION,
        "packet_id": f"operator-packet:{packet_id}",
        "lane_id": _stringify(scan_payload.get("lane_id")),
        "cohort_id": _stringify(scan_payload.get("cohort_id")),
        "scan_status": scan_status or "unknown",
        "decision": decision_text,
        "triage_prompts": triage_prompts,
        "sample_candidates": sample_candidates,
        "summary": {
            "candidate_count": len(sample_candidates),
            "p459_status_counts": dict(summary_payload.get("p459_status_counts", {})),
            "review_first": True,
            "policy_risk": "high",
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "live_query_unavailable": unavailable,
        },
        "notes": list(scan_payload.get("notes", []))
        if isinstance(scan_payload.get("notes"), list)
        else [],
    }


def build_nat_cohort_c_operator_packet(
    scan_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if _stringify(scan_payload.get("cohort_id")) != "non_ghg_protocol_or_missing_p459":
        raise ValueError("Cohort C operator packet requires the Cohort C payload")
    sample_candidates = [
        {
            "qid": _stringify(candidate.get("qid")),
            "label": _stringify(candidate.get("label")),
            "p459_status": _stringify(candidate.get("p459_status")),
            "qualifier_snippet": _stringify(candidate.get("qualifier_snippet")),
            "policy_note": _stringify(candidate.get("policy_note")),
        }
        for candidate in scan_payload.get("sample_candidates", [])
        if isinstance(candidate, Mapping)
    ]
    scan_status = _stringify(scan_payload.get("scan_status"))
    unavailable = scan_status == "live_population_scan_unavailable"
    if unavailable:
        decision_text = "hold"
        triage_prompts = [
            "Live query was unavailable; retry later before any cohort claim.",
            "Do not infer migration readiness from an unavailable preview.",
        ]
    else:
        decision_text = "review"
        triage_prompts = [
            "Review the candidate P459 status split before any cohort claim.",
            "Check whether the missing vs non-GHG protocol buckets need different handling.",
            "Keep the lane review-first and fail-closed.",
        ]
    packet_id = hashlib.sha1(
        json.dumps(
            {
                "cohort_id": scan_payload.get("cohort_id"),
                "scan_status": scan_status,
                "candidate_count": len(sample_candidates),
                "candidate_qids": [candidate["qid"] for candidate in sample_candidates],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": WIKIDATA_REVIEW_PACKET_SCHEMA_VERSION,
        "packet_id": f"operator-packet:{packet_id}",
        "lane_id": _stringify(scan_payload.get("lane_id")),
        "cohort_id": _stringify(scan_payload.get("cohort_id")),
        "scan_status": scan_status or "unknown",
        "decision": decision_text,
        "triage_prompts": triage_prompts,
        "sample_candidates": sample_candidates,
        "summary": {
            "candidate_count": len(sample_candidates),
            "p459_status_counts": dict(scan_payload.get("summary", {}).get("p459_status_counts", {}))
            if isinstance(scan_payload.get("summary"), Mapping)
            else {},
            "review_first": True,
            "policy_risk": "high",
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "live_query_unavailable": unavailable,
        },
        "notes": list(scan_payload.get("notes", []))
        if isinstance(scan_payload.get("notes"), list)
        else [],
    }


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


def _normalize_string_list(values: Any) -> list[str]:
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
        result: list[str] = []
        for value in values:
            text = _stringify(value).strip()
            if text:
                result.append(text)
        return result
    return []


def _select_demonstrator_candidates(
    enriched_pack: Mapping[str, Any],
    *,
    review_packet: Mapping[str, Any] | None = None,
    entity_qid: str | None = None,
    candidate_ids: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    candidates = enriched_pack.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("migration pack candidates must be a list")

    packet_candidate_ids = (
        _normalize_string_list(
            ((review_packet or {}).get("split_review_context") or {}).get("source_candidate_ids")
        )
        if isinstance(review_packet, Mapping)
        else []
    )
    explicit_candidate_ids = _normalize_string_list(candidate_ids or [])
    selected_candidate_ids = explicit_candidate_ids or packet_candidate_ids

    resolved_entity_qid = str(entity_qid).strip() if entity_qid is not None else ""
    if not resolved_entity_qid and isinstance(review_packet, Mapping):
        resolved_entity_qid = _stringify(review_packet.get("review_entity_qid", "")).strip()

    selected: list[dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        row_candidate_id = _stringify(row.get("candidate_id", "")).strip()
        row_entity_qid = _stringify(row.get("entity_qid", "")).strip()
        if selected_candidate_ids and row_candidate_id not in selected_candidate_ids:
            continue
        if resolved_entity_qid and row_entity_qid != resolved_entity_qid:
            continue
        selected.append(row)

    if not selected:
        raise ValueError("no candidates matched the requested review packet / entity / candidate ids")
    if not resolved_entity_qid:
        resolved_entity_qid = _stringify(selected[0].get("entity_qid", "")).strip()

    packet_context = {
        "packet_id": _stringify((review_packet or {}).get("packet_id", "")).strip() or None,
        "review_entity_qid": _stringify((review_packet or {}).get("review_entity_qid", "")).strip() or None,
        "split_plan_id": _stringify(
            ((review_packet or {}).get("split_review_context") or {}).get("split_plan_id", "")
        ).strip()
        or None,
        "source_candidate_ids": selected_candidate_ids,
    }
    return selected, packet_context, resolved_entity_qid


def _derive_demonstrator_candidate_disposition(
    candidate: Mapping[str, Any],
    *,
    bridge_case: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    classification = _stringify(candidate.get("classification", "")).strip()
    action = _stringify(candidate.get("action", "")).strip()
    pressure = _stringify(candidate.get("pressure", "")).strip()
    if not pressure and isinstance(bridge_case, Mapping):
        pressure = _stringify(bridge_case.get("pressure", "")).strip()
    promotion_gate = candidate.get("promotion_gate")
    gate_decision = (
        _stringify(promotion_gate.get("decision", "")).strip()
        if isinstance(promotion_gate, Mapping)
        else ""
    )

    state = "held"
    disposition = "held_review"
    rationale: list[str] = []

    if classification == "split_required" or pressure == "split_pressure":
        disposition = "held_split_review"
        rationale.extend(
            [text for text in (classification, pressure or "split_pressure") if text]
        )
    elif pressure == "contradiction":
        disposition = "held_conflict"
        rationale.append("contradiction")
    elif classification in {"reference_drift", "qualifier_drift"}:
        disposition = "held_repair_review"
        rationale.append(classification)
    elif gate_decision == "promote":
        state = "promotable"
        disposition = "promotable"
        rationale.append("promotion_gate:promote")
    elif (
        classification in {"safe_equivalent", "safe_with_reference_transfer"}
        and pressure in {"", "reinforce"}
        and gate_decision not in {"review_only", "abstain"}
    ):
        state = "promotable"
        disposition = "promotable"
        rationale.extend([classification, pressure or "no_bridge_pressure"])
    else:
        rationale.extend(
            [text for text in (classification or "unclassified", pressure or gate_decision or "held") if text]
        )

    return {
        "candidate_id": _stringify(candidate.get("candidate_id", "")).strip(),
        "classification": classification,
        "action": action,
        "pressure": pressure or None,
        "promotion_gate_decision": gate_decision or None,
        "review_stage": "reviewable",
        "final_state": state,
        "disposition": disposition,
        "rationale": rationale,
    }


def build_wikidata_climate_review_demonstrator(
    migration_pack: Mapping[str, Any],
    *,
    climate_text_payload: Mapping[str, Any],
    review_packet: Mapping[str, Any] | None = None,
    entity_qid: str | None = None,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    enriched_pack, observation_claim_payload = attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(
        migration_pack,
        climate_text_payload=climate_text_payload,
    )
    selected_candidates, packet_context, resolved_entity_qid = _select_demonstrator_candidates(
        enriched_pack,
        review_packet=review_packet,
        entity_qid=entity_qid,
        candidate_ids=candidate_ids,
    )
    selected_candidate_ids = [
        _stringify(candidate.get("candidate_id", "")).strip()
        for candidate in selected_candidates
    ]
    bridge_case_map = {
        _stringify(case.get("candidate_id", "")).strip(): case
        for case in enriched_pack.get("bridge_cases", [])
        if isinstance(case, Mapping)
    }
    selected_bridge_cases = [
        deepcopy(bridge_case_map[candidate_id])
        for candidate_id in selected_candidate_ids
        if candidate_id in bridge_case_map
    ]

    filtered_claims = [
        deepcopy(row)
        for row in observation_claim_payload.get("claims", [])
        if isinstance(row, Mapping)
        and _stringify(row.get("subject_id", "")).strip() == resolved_entity_qid
    ]
    observation_ids = {
        _stringify(row.get("observation_id", "")).strip()
        for row in filtered_claims
        if _stringify(row.get("observation_id", "")).strip()
    }
    filtered_observations = [
        deepcopy(row)
        for row in observation_claim_payload.get("observations", [])
        if isinstance(row, Mapping)
        and _stringify(row.get("observation_id", "")).strip() in observation_ids
    ]
    claim_ids = {
        _stringify(row.get("claim_id", "")).strip()
        for row in filtered_claims
        if _stringify(row.get("claim_id", "")).strip()
    }
    filtered_evidence_links = [
        deepcopy(row)
        for row in observation_claim_payload.get("evidence_links", [])
        if isinstance(row, Mapping)
        and (
            _stringify(row.get("observation_id", "")).strip() in observation_ids
            or _stringify(row.get("claim_id", "")).strip() in claim_ids
        )
    ]

    pressure_counts: dict[str, int] = {}
    candidate_dispositions: list[dict[str, Any]] = []
    for candidate in selected_candidates:
        candidate_id = _stringify(candidate.get("candidate_id", "")).strip()
        bridge_case = bridge_case_map.get(candidate_id)
        if isinstance(bridge_case, Mapping):
            pressure_key = _stringify(bridge_case.get("pressure", "")).strip() or "unclassified"
            pressure_counts[pressure_key] = pressure_counts.get(pressure_key, 0) + 1
        candidate_dispositions.append(
            _derive_demonstrator_candidate_disposition(candidate, bridge_case=bridge_case)
        )

    held_count = sum(1 for row in candidate_dispositions if row["final_state"] == "held")
    promotable_count = sum(1 for row in candidate_dispositions if row["final_state"] == "promotable")
    final_state = (
        "promotable"
        if promotable_count and held_count == 0
        else "held"
        if held_count and promotable_count == 0
        else "mixed"
    )
    selected_candidate_rows = [
        {
            "candidate_id": _stringify(candidate.get("candidate_id", "")).strip(),
            "entity_qid": _stringify(candidate.get("entity_qid", "")).strip(),
            "slot_id": _stringify(candidate.get("slot_id", "")).strip(),
            "statement_index": int(candidate.get("statement_index", 0)),
            "classification": _stringify(candidate.get("classification", "")).strip(),
            "action": _stringify(candidate.get("action", "")).strip(),
            "requires_review": bool(candidate.get("requires_review", False)),
            "reasons": deepcopy(candidate.get("reasons", [])),
            "split_axes": deepcopy(candidate.get("split_axes", [])),
            "claim_bundle_before": deepcopy(candidate.get("claim_bundle_before", {})),
            "claim_bundle_after": deepcopy(candidate.get("claim_bundle_after", {})),
        }
        for candidate in selected_candidates
    ]

    return {
        "schema_version": WIKIDATA_CLIMATE_REVIEW_DEMONSTRATOR_SCHEMA_VERSION,
        "inputs": {
            "source_property": _stringify(migration_pack.get("source_property", "")).strip(),
            "target_property": _stringify(migration_pack.get("target_property", "")).strip(),
            "entity_qid": resolved_entity_qid,
            "candidate_ids": selected_candidate_ids,
            "packet_context": packet_context,
        },
        "candidate_change_surface": {
            "candidate_stage": "candidate_only",
            "review_stage": "reviewable",
            "candidate_count": len(selected_candidate_rows),
            "candidates": selected_candidate_rows,
        },
        "text_side_predicate_carrier": {
            "payload_version": _stringify(observation_claim_payload.get("payload_version", "")).strip(),
            "observation_count": len(filtered_observations),
            "claim_count": len(filtered_claims),
            "evidence_link_count": len(filtered_evidence_links),
            "observations": filtered_observations,
            "claims": filtered_claims,
            "evidence_links": filtered_evidence_links,
        },
        "residual_completeness_surface": {
            "bridge_case_count": len(selected_bridge_cases),
            "pressure_counts": pressure_counts,
            "bridge_cases": selected_bridge_cases,
        },
        "review_disposition": {
            "reviewable": bool(selected_candidate_rows),
            "final_state": final_state,
            "held_candidate_count": held_count,
            "promotable_candidate_count": promotable_count,
            "candidate_dispositions": candidate_dispositions,
            "summary": (
                "All selected candidates remain held."
                if final_state == "held"
                else "All selected candidates are promotable."
                if final_state == "promotable"
                else "Selected candidates are mixed across held and promotable states."
            ),
        },
    }


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


def _extract_bundle_unit(raw: Mapping[str, Any]) -> str | None:
    unit = raw.get("unit")
    if unit is None and isinstance(raw.get("value"), Mapping):
        unit = raw.get("value", {}).get("unit")
    if unit is None and isinstance(raw.get("mainsnak"), Mapping):
        mainsnak = raw.get("mainsnak")
        if isinstance(mainsnak, Mapping) and isinstance(mainsnak.get("datavalue"), Mapping):
            unit = mainsnak.get("datavalue", {}).get("value", {}).get("unit")
    if unit is None:
        return None
    normalized = _stringify(unit).strip()
    return normalized or None


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
        unit=_extract_bundle_unit(raw),
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
                                "unit": _extract_bundle_unit(statement),
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
        **({"unit": bundle.unit} if bundle.unit else {}),
        "qualifiers": {prop: list(values) for prop, values in bundle.qualifiers},
        "references": [{prop: list(values) for prop, values in block} for block in bundle.references],
        "window_id": window_id,
    }


def _climate_split_model_axis(slot_candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    year_signatures: set[str] = set()
    scope_signatures: set[tuple[str, ...]] = set()
    method_signatures: set[tuple[str, ...]] = set()
    for candidate in slot_candidates:
        before = candidate.get("claim_bundle_before")
        if not isinstance(before, Mapping):
            continue
        year, _ = _resolve_claim_bundle_year(before)
        scopes = _extract_claim_bundle_scope_values(before)
        methods = _extract_claim_bundle_method_values(before)
        if year:
            year_signatures.add(year)
        if scopes:
            scope_signatures.add(tuple(scopes))
        if methods:
            method_signatures.add(tuple(methods))

    if not any((year_signatures, scope_signatures, method_signatures)):
        return None
    reason_bits: list[str] = []
    if len(year_signatures) > 1:
        reason_bits.append(
            "years="
            + "|".join(sorted(year_signatures))
        )
    if len(scope_signatures) > 1:
        reason_bits.append(
            "scopes="
            + "|".join(",".join(signature) for signature in sorted(scope_signatures))
        )
    if len(method_signatures) > 1:
        reason_bits.append(
            "methods="
            + "|".join(",".join(signature) for signature in sorted(method_signatures))
        )
    if not reason_bits:
        return None
    return {
        "property": "__ghg_model__",
        "source": "slot",
        "reason": "ghg_model_split_required;" + ";".join(reason_bits),
        "cardinality": max(len(year_signatures), len(scope_signatures), len(method_signatures), 1),
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
    current_full_window = windows[-1]

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
    family_summary: dict[str, int] = {bucket: 0 for bucket in ("A", "B", "C", "D", "E")}
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
            pressure: str | None = None
            pressure_confidence: float | None = None
            pressure_summary: str | None = None
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
            model_validation = _build_candidate_model_validation(
                bundle,
                source_property=source_property,
                target_property=target_property,
                split_reasons=split_reasons,
            )
            execution_hints = _build_candidate_execution_hints(
                bundle,
                target_property=target_property,
                model_validation=model_validation,
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
            if source_property in CLIMATE_MODEL_SOURCE_PROPERTIES and target_property in CLIMATE_MODEL_TARGET_PROPERTIES:
                model_status = _stringify(model_validation.get("status"))
                if model_status in {"model_safe", "model_safe_with_split"}:
                    model_year = _stringify(model_validation.get("resolved_year"))
                    model_scope = ",".join(
                        _stringify(value)
                        for value in model_validation.get("scope_values", [])
                        if _stringify(value).strip()
                    )
                    model_methods = ",".join(
                        _stringify(value)
                        for value in model_validation.get("determination_method_values", [])
                        if _stringify(value).strip()
                    )
                    model_unit = _stringify(model_validation.get("resolved_unit_qid"))
                    reasons.append(model_status)
                    if model_status == "model_safe":
                        pressure = "reinforce"
                        pressure_confidence = 0.92
                        pressure_summary = (
                            f"{model_status}; year={model_year or 'unknown'}; "
                            f"scope={model_scope or 'none'}; method={model_methods or 'none'}; "
                            f"unit={model_unit or 'unknown'}; execution_ready="
                            f"{bool(model_validation.get('execution_ready'))}"
                        )
                    elif model_scope:
                        pressure = "split_pressure"
                        pressure_confidence = 0.84
                        pressure_summary = (
                            f"{model_status}; year={model_year or 'unknown'}; "
                            f"scope={model_scope}; method={model_methods or 'none'}; "
                            f"unit={model_unit or 'unknown'}; execution_ready="
                            f"{bool(model_validation.get('execution_ready'))}"
                        )
                    if model_status == "model_safe_with_split" and classification in {"safe_equivalent", "safe_with_reference_transfer"}:
                        classification = "split_required"
                        confidence = 0.35
                        requires_review = True

            candidate_id = f"{slot_id}|{index}"
            action = _suggest_migration_action(classification=classification)
            claim_bundle_before = _bundle_to_claim_bundle(bundle, window_id=current_window.window_id)
            claim_bundle_after = _bundle_to_claim_bundle(
                bundle,
                window_id=current_window.window_id,
                property_override=target_property,
            )
            subject_resolution = _build_subject_resolution(
                entity_qid=bundle.subject,
                window=current_full_window,
            )
            family_classifier = _build_candidate_family_classifier(
                source_property=source_property,
                target_property=target_property,
                classification=classification,
                requires_review=requires_review,
                reasons=reasons,
                model_validation=model_validation,
                claim_bundle_before=claim_bundle_before,
                subject_resolution=subject_resolution,
            )
            promotion_gate = _build_candidate_promotion_gate(
                classification=classification,
                requires_review=requires_review,
                pressure=pressure,
                pressure_confidence=pressure_confidence,
                pressure_summary=pressure_summary,
                model_validation=model_validation,
                execution_hints=execution_hints,
                subject_resolution=subject_resolution,
            )
            counts_by_bucket[classification] = counts_by_bucket.get(classification, 0) + 1
            family_summary[family_classifier["bucket"]] = family_summary.get(family_classifier["bucket"], 0) + 1
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
                    "claim_bundle_before": claim_bundle_before,
                    "claim_bundle_after": claim_bundle_after,
                    "pressure": pressure,
                    "pressure_confidence": pressure_confidence,
                    "pressure_summary": pressure_summary,
                    "model_classification": _stringify(model_validation.get("status")),
                    "execution_ready": bool(model_validation.get("execution_ready")),
                    "model_validation": model_validation,
                    "execution_hints": execution_hints,
                    "execution_profile": execution_hints,
                    "promotion_class": promotion_gate["decision"],
                    "promotion_eligibility": promotion_gate["eligibility"],
                    "promotion_gate": promotion_gate,
                    "family_classifier": family_classifier,
                    "family_bucket": family_classifier["bucket"],
                    "family_confidence": family_classifier["confidence"],
                    "subject_resolution": subject_resolution,
                    "subject_family": family_classifier["subject_family"],
                    "ghg_semantic_family": family_classifier["ghg_semantic_family"],
                    "reporting_period_kind": family_classifier["reporting_period_kind"],
                    "scope_resolution": family_classifier["scope_resolution"],
                    "method_resolution": family_classifier["method_resolution"],
                    "phase2_actions": family_classifier["phase2_actions"],
                    "normalization_contract": family_classifier["normalization_contract"],
                    "phase2_method_inference": family_classifier["phase2_method_inference"],
                    "phase2_scope_inference": family_classifier["phase2_scope_inference"],
                    "phase2_fiscal_normalization": family_classifier["phase2_fiscal_normalization"],
                    "qualifier_diff": qualifier_diff,
                    "reference_diff": reference_diff,
                }
            )

    candidates.sort(key=lambda item: (item["entity_qid"], item["statement_index"], item["candidate_id"]))
    migration_pack = {
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
            "family_summary": family_summary,
            "checked_safe_subset": checked_safe_subset,
            "abstained": abstained,
            "ambiguous": ambiguous,
            "requires_review_count": sum(1 for item in candidates if item["requires_review"]),
        },
    }
    pilot_metrics, readiness_surface = _build_migration_pack_pilot_surface(
        candidates=candidates,
        checked_safe_subset=checked_safe_subset,
        abstained=abstained,
        ambiguous=ambiguous,
        requires_review_count=migration_pack["summary"]["requires_review_count"],
    )
    migration_pack["compiler_contract"] = build_wikidata_migration_pack_contract(migration_pack)
    if isinstance(migration_pack["compiler_contract"], dict):
        migration_pack["compiler_contract"]["pilot_metrics"] = pilot_metrics
        migration_pack["compiler_contract"]["readiness_surface"] = readiness_surface
    migration_pack["promotion_gate"] = build_product_gate(
        lane="wikidata_nat",
        product_ref="wikidata_migration_pack",
        compiler_contract=migration_pack["compiler_contract"],
    )
    if isinstance(migration_pack["promotion_gate"], dict):
        migration_pack["promotion_gate"]["pilot_metrics"] = pilot_metrics
        migration_pack["promotion_gate"]["readiness_surface"] = readiness_surface
    return migration_pack


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
        execution_rows: list[dict[str, Any]] = []
        seen_bundle_signatures: set[str] = set()
        exact_reference_preservation = True
        exact_qualifier_preservation = True
        all_split_actions = True
        merged_axes: dict[tuple[str, str, str], dict[str, Any]] = {}
        execution_ready = True
        resolved_years: set[str] = set()
        resolved_scopes: set[str] = set()
        resolved_units: set[str] = set()
        execution_backends: set[str] = set()

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

            execution_row = _build_split_execution_row(candidate)
            execution_rows.append(execution_row)
            execution_ready = execution_ready and bool(execution_row.get("execution_ready"))
            resolved_year = _stringify(execution_row.get("resolved_year")).strip()
            if resolved_year:
                resolved_years.add(resolved_year)
            for scope_value in execution_row.get("scope_values", []):
                scope_text = _stringify(scope_value).strip()
                if scope_text:
                    resolved_scopes.add(scope_text)
            resolved_unit = _stringify(execution_row.get("resolved_unit_qid")).strip()
            if resolved_unit:
                resolved_units.add(resolved_unit)
            execution_backend = "qs3" if _stringify(execution_row.get("rank")) in {"preferred", "deprecated"} else "openrefine"
            execution_backends.add(execution_backend)

            model_classification = _stringify(candidate.get("model_classification")).strip()
            if model_classification == "model_safe_with_split":
                key = ("__ghg_model__", "model", "ontology_validated_split")
                merged_axes[key] = {
                    "property": key[0],
                    "source": key[1],
                    "reason": key[2],
                    "cardinality": len(slot_candidates),
                }

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

        climate_model_axis = None
        if (
            _stringify(migration_pack.get("source_property")) in CLIMATE_MODEL_SOURCE_PROPERTIES
            and _stringify(migration_pack.get("target_property")) in CLIMATE_MODEL_TARGET_PROPERTIES
        ):
            climate_model_axis = _climate_split_model_axis(slot_candidates)
        if climate_model_axis is not None:
            key = (
                _stringify(climate_model_axis.get("property")),
                _stringify(climate_model_axis.get("source")),
                _stringify(climate_model_axis.get("reason")),
            )
            merged_axes[key] = climate_model_axis

        structurally_decomposable = (
            all_split_actions
            and len(proposed_target_bundles) >= 2
            and len(proposed_target_bundles) == len(slot_candidates)
            and bool(merged_axes)
        )
        proposed_target_bundles = sorted(
            proposed_target_bundles,
            key=_claim_bundle_signature,
        )
        resolved_scope = None
        if len(resolved_scopes) == 1:
            resolved_scope = next(iter(resolved_scopes))
        elif not resolved_scopes and execution_rows:
            resolved_scope = "TOTAL"
        resolved_year = next(iter(resolved_years)) if len(resolved_years) == 1 else None
        resolved_unit_qid = next(iter(resolved_units)) if len(resolved_units) == 1 else None
        execution_backend = next(iter(execution_backends)) if len(execution_backends) == 1 else ""
        plan_execution_ready = bool(
            structurally_decomposable
            and execution_ready
            and resolved_scope is not None
            and resolved_unit_qid is not None
            and exact_reference_preservation
            and exact_qualifier_preservation
        )
        if plan_execution_ready:
            status = "execution_ready"
        else:
            status = "structurally_decomposable" if structurally_decomposable else "review_only"
        counts_by_status[status] = counts_by_status.get(status, 0) + 1

        plans.append(
            {
                "split_plan_id": f"split://{slot_id}",
                "entity_qid": _stringify(slot_candidates[0].get("entity_qid")),
                "source_slot_id": slot_id,
                "source_candidate_ids": source_candidate_ids,
                "status": status,
                "review_required": status != "execution_ready",
                "execution_ready": plan_execution_ready,
                "merged_split_axes": sorted(
                    merged_axes.values(),
                    key=lambda item: (item["property"], item["source"], item["reason"]),
                ),
                "proposed_target_bundles": proposed_target_bundles,
                "split_execution_rows": execution_rows,
                "proposed_bundle_count": len(proposed_target_bundles),
                "reference_propagation": "exact" if exact_reference_preservation else "review_required",
                "qualifier_propagation": "exact" if exact_qualifier_preservation else "review_required",
                "resolved_year": resolved_year,
                "resolved_scope": resolved_scope,
                "resolved_unit_qid": resolved_unit_qid,
                "execution_backend": execution_backend,
                "suggested_action": "migrate_with_split" if status == "execution_ready" else "review_structured_split" if structurally_decomposable else "review_only",
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
    "build_nat_cohort_c_operator_packet",
    "build_observation_claim_payload_from_source_units",
    "build_observation_claim_payload_from_revision_locked_climate_text_sources",
    "build_wikidata_climate_review_demonstrator",
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
