from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

from .wikidata import project_wikidata_payload
from .wikidata_disjointness import project_wikidata_disjointness_payload


CHANGE_REVIEW_PACKET_SCHEMA_VERSION = "sl.wikidata_change_review_packet.v0_1"
CHANGE_REVIEW_REPORT_SCHEMA_VERSION = "sl.wikidata_change_review_report.v0_1"

REVIEW_ONLY_AUTHORITY_POLICY = "review_only"
SUPPORTED_PACKET_SCHEMA_VERSIONS = {CHANGE_REVIEW_PACKET_SCHEMA_VERSION}
TEMPORAL_QUALIFIER_PROPERTIES = frozenset({"P580", "P582", "P585"})
DEFAULT_TEMPORAL_EXCLUSIVE_PROPERTIES = ("P361", "P17", "P131", "P14143")
NON_EXCLUSIVE_MEREOLOGY_PROPERTIES = frozenset({"P527"})
PRESSURE_COMPONENTS = (
    "local_statement_pressure",
    "upstream_inheritance_pressure",
    "upstream_constraint_pressure",
    "sibling_shape_pressure",
    "downstream_dependency_pressure",
    "temporal_mereology_pressure",
    "metaclass_order_pressure",
    "disjointness_pressure",
)
PRESSURE_SURFACE_BY_COMPONENT = {
    "local_statement_pressure": "local",
    "upstream_inheritance_pressure": "upstream",
    "upstream_constraint_pressure": "upstream",
    "sibling_shape_pressure": "sibling",
    "downstream_dependency_pressure": "downstream",
    "temporal_mereology_pressure": "temporal_mereology",
    "metaclass_order_pressure": "metaclass_order",
    "disjointness_pressure": "disjointness",
}
SUPPORTED_DISPOSITIONS = (
    "checked_safe_reviewable",
    "held",
    "contradictory",
    "insufficiently_supported",
)
OBLIGATION_OPERATIONS = frozenset(
    {
        "split_class_obligation",
        "new_class_obligation",
        "new_property_obligation",
        "relation_family_correction",
        "upstream_repair_obligation",
        "sibling_normalization_obligation",
    }
)
PNF_INDEX_COMPONENTS = (
    "receipt_index",
    "predicate_pnf_index",
    "structural_signature_index",
    "constraint_pnf_index",
    "shape_pnf_index",
    "residual_index",
    "pressure_index",
    "candidate_index",
    "mutation_pnf_index",
    "disposition_index",
    "promotion_boundary",
)
WIKIDATA_GROUNDING_COMPONENTS = (
    "subject_qid_candidates",
    "object_qid_candidates",
    "pid_candidates",
    "qualifier_pid_candidates",
    "statement_shape_candidates",
    "constraint_surface_candidates",
    "abstract_q_obligations",
    "abstract_p_obligations",
    "grounding_residuals",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def load_change_review_packet(path: Path) -> dict[str, Any]:
    packet = _load_json(path)
    schema_version = packet.get("schema_version", CHANGE_REVIEW_PACKET_SCHEMA_VERSION)
    if schema_version not in SUPPORTED_PACKET_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported ChangeReviewPacket schema_version: {schema_version}")
    return packet


def _packet_base_dir(packet_path: Path | None) -> Path:
    if packet_path is None:
        return Path.cwd()
    return packet_path.resolve().parent


def _load_slice(packet: Mapping[str, Any], *, packet_path: Path | None = None) -> dict[str, Any]:
    inline = packet.get("bounded_slice")
    if isinstance(inline, Mapping):
        return deepcopy(dict(inline))

    slice_path = packet.get("bounded_slice_path") or packet.get("slice_path")
    if not isinstance(slice_path, str) or not slice_path.strip():
        raise ValueError("ChangeReviewPacket requires bounded_slice or bounded_slice_path")
    path = Path(slice_path)
    if not path.is_absolute():
        path = _packet_base_dir(packet_path) / path
    return _load_json(path)


def _property_scope(packet: Mapping[str, Any]) -> list[str]:
    raw = packet.get("property_scope")
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        values = [str(item) for item in raw if item is not None]
        if values:
            return values
    return ["P31", "P279"]


def _string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, Iterable) and not isinstance(raw, (bytes, Mapping)):
        return [str(item) for item in raw if item is not None and str(item)]
    return [str(raw)]


def _normalize_pressure_attribution(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for component in PRESSURE_COMPONENTS:
        value = raw.get(component)
        if value is None:
            continue
        if isinstance(value, Mapping):
            normalized[component] = dict(value)
        else:
            normalized[component] = {"status": value}
    for key, value in raw.items():
        component = str(key)
        if component in normalized:
            continue
        normalized[component] = dict(value) if isinstance(value, Mapping) else {"status": value}
    return normalized


def _pressure_attribution_surface(
    *,
    raw_surface: Any,
    pressure_attribution: Mapping[str, Any],
) -> list[str]:
    surface = set(_string_list(raw_surface))
    for component in pressure_attribution:
        surface.add(PRESSURE_SURFACE_BY_COMPONENT.get(component, component))
    return sorted(surface)


def _candidate_pressure_attribution(
    packet_pressure: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_pressure = _normalize_pressure_attribution(candidate.get("pressure_attribution"))
    if not packet_pressure:
        return candidate_pressure
    merged = deepcopy(dict(packet_pressure))
    for component, value in candidate_pressure.items():
        if component in merged and isinstance(merged[component], Mapping) and isinstance(value, Mapping):
            merged[component] = dict(merged[component]) | dict(value)
        else:
            merged[component] = value
    return merged


def _pressure_review_reasons(pressure_attribution: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for component, value in pressure_attribution.items():
        if not isinstance(value, Mapping):
            continue
        component_reasons = _string_list(value.get("review_reasons"))
        component_reasons.extend(_string_list(value.get("held_reasons")))
        reason = value.get("held_reason") or value.get("review_reason")
        if reason is not None:
            component_reasons.append(str(reason))
        if not component_reasons and str(value.get("status", "")).startswith("held_"):
            component_reasons.append(str(value["status"]))
        if component == "upstream_inheritance_pressure" and value.get("status") in {"present", "reduced", "unresolved"}:
            component_reasons.append("held_upstream_ontology_pressure")
        if component == "sibling_shape_pressure" and value.get("status") in {"present", "unresolved"}:
            component_reasons.append("held_same_depth_split_required")
        if component == "temporal_mereology_pressure" and value.get("status") in {"present", "unresolved"}:
            component_reasons.append("held_series_mereology_required")
        reasons.extend(component_reasons)
    return sorted(set(reasons))


def _candidate_review_reasons(
    *,
    candidate: Mapping[str, Any],
    disposition: str,
    diagnostic_delta: Mapping[str, int],
    pressure_attribution: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    review_reasons = set(_string_list(candidate.get("review_reasons")))
    review_reasons.update(_string_list(candidate.get("expected_review_reasons")))
    held_reasons = set(_string_list(candidate.get("held_reasons")))
    pressure_reasons = set(_pressure_review_reasons(pressure_attribution))
    review_reasons.update(pressure_reasons)
    if disposition == "held":
        held_reasons.update(reason for reason in pressure_reasons if reason.startswith("held_"))
        held_reasons.update(reason for reason in review_reasons if reason.startswith("held_"))
        if any(int(value) > 0 for value in diagnostic_delta.values()):
            held_reasons.add("held_family_regression")
        if not held_reasons:
            held_reasons.add("held_review_required")
    return sorted(held_reasons), sorted(review_reasons)


def _candidate_obligation(candidate: Mapping[str, Any], mutation_summary: Mapping[str, Any]) -> dict[str, Any] | None:
    operation = str(mutation_summary.get("operation") or candidate.get("operation") or "")
    raw_payload = candidate.get("obligation_payload")
    payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
    if operation not in OBLIGATION_OPERATIONS and not payload:
        return None
    raw_abstract_candidates = candidate.get("abstract_candidates")
    abstract_candidates: list[dict[str, Any]] = []
    if isinstance(raw_abstract_candidates, Iterable) and not isinstance(
        raw_abstract_candidates,
        (str, bytes, Mapping),
    ):
        abstract_candidates = [
            dict(row) if isinstance(row, Mapping) else {"id": str(row)}
            for row in raw_abstract_candidates
        ]
    return {
        "candidate_obligation": True,
        "obligation_type": str(candidate.get("obligation_type") or operation),
        "promotion_required": True,
        "promotion_boundary": "external_governance_receipt_required",
        "creates_wikidata_entity": False,
        "creates_wikidata_property": False,
        "obligation_payload": payload,
        "abstract_candidates": abstract_candidates,
    }


def _packet_pnf_index(packet: Mapping[str, Any]) -> dict[str, Any]:
    raw_index = packet.get("pnf_index")
    supplied = dict(raw_index) if isinstance(raw_index, Mapping) else {}
    index: dict[str, Any] = {}
    for component in PNF_INDEX_COMPONENTS:
        value = supplied.get(component)
        if isinstance(value, Mapping):
            index[component] = [dict(value)]
        elif isinstance(value, list):
            index[component] = [dict(row) if isinstance(row, Mapping) else {"status": str(row)} for row in value]
        elif value is not None:
            index[component] = [{"status": value}]
        else:
            index[component] = [{"status": "deferred_v0"}]
    index["receipt_index"] = index["receipt_index"] + [{"status": "diagnostic_only_no_pnf_emission_receipts"}]
    index["predicate_pnf_index"] = index["predicate_pnf_index"] + [{"status": "packet_metadata_only_no_pnf_compiler"}]
    index["pressure_index"] = index["pressure_index"] + [{"source": "diagnostic_counts_and_pressure_attribution"}]
    index["candidate_index"] = index["candidate_index"] + [{"source": "candidate_repairs"}]
    index["mutation_pnf_index"] = index["mutation_pnf_index"] + [{"source": "packet_supplied_mutation_pnf"}]
    index["disposition_index"] = index["disposition_index"] + [{"source": "change_review_disposition"}]
    index["promotion_boundary"] = {
        "status": "external_governance_required",
        "edit_authority": False,
        "no_fabricated_pnf_receipts": True,
    }
    return index


def _grounding_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        return [dict(raw)]
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        return [dict(row) if isinstance(row, Mapping) else {"id": str(row)} for row in raw]
    return [{"id": str(raw)}]


def _packet_wikidata_grounding(packet: Mapping[str, Any]) -> dict[str, Any]:
    raw_grounding = packet.get("wikidata_grounding") or packet.get("pnf_grounding")
    supplied = dict(raw_grounding) if isinstance(raw_grounding, Mapping) else {}
    raw_components = supplied.get("components")
    components_source = dict(raw_components) if isinstance(raw_components, Mapping) else supplied
    components = {
        component: _grounding_rows(components_source.get(component))
        for component in WIKIDATA_GROUNDING_COMPONENTS
    }
    return {
        "schema_version": str(supplied.get("schema_version") or "sl.wikidata_pnf_grounding.v0_1"),
        "direction": str(supplied.get("direction") or "PredicatePNF_to_Wikidata"),
        "authority_policy": REVIEW_ONLY_AUTHORITY_POLICY,
        "candidate_source_policy": "packet_supplied_candidates_only",
        "qid_pid_policy": "no_fabricated_qids_or_pids",
        "receipt_policy": "no_fabricated_PNFEmissionReceipt",
        "grounding_status": str(supplied.get("grounding_status") or "packet_supplied_candidates_only"),
        "receipt_status": str(supplied.get("receipt_status") or "diagnostic_only_no_pnf_emission_receipts"),
        "source_pnf": dict(supplied.get("source_pnf", {}))
        if isinstance(supplied.get("source_pnf"), Mapping)
        else {},
        "components": components,
        "no_fabricated_qids": True,
        "no_fabricated_pids": True,
        "no_fabricated_pnf_receipts": True,
        "edit_authority": False,
        "promotion_boundary": {
            "status": "external_governance_required",
            "abstract_qp_obligations_only": True,
            "edit_authority": False,
        },
    }


def _target_windows(candidate: Mapping[str, Any], slice_payload: Mapping[str, Any]) -> set[str] | None:
    raw = candidate.get("window_ids") or candidate.get("target_windows")
    if raw is None:
        return None
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Iterable):
        return {str(item) for item in raw if item is not None}
    windows = slice_payload.get("windows")
    if isinstance(windows, list):
        return {str(window.get("id")) for window in windows if isinstance(window, Mapping)}
    return None


def _matches_statement(statement: Mapping[str, Any], selector: Mapping[str, Any]) -> bool:
    for field in ("subject", "property", "value", "rank"):
        expected = selector.get(field)
        if expected is not None and statement.get(field) != expected:
            return False
    return True


def _candidate_selector(candidate: Mapping[str, Any]) -> dict[str, Any]:
    selector = candidate.get("match")
    if isinstance(selector, Mapping):
        return dict(selector)
    return {
        field: candidate[field]
        for field in ("subject", "property", "value", "rank")
        if field in candidate
    }


def _candidate_statement(candidate: Mapping[str, Any]) -> dict[str, Any]:
    statement = candidate.get("statement")
    if isinstance(statement, Mapping):
        return dict(statement)
    return {
        field: candidate[field]
        for field in ("subject", "property", "value", "rank", "qualifiers", "references")
        if field in candidate
    }


def _iter_windows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    windows = slice_payload.get("windows")
    if not isinstance(windows, list):
        raise ValueError("bounded slice must contain a windows list")
    return [window for window in windows if isinstance(window, dict)]


def _apply_candidate(slice_payload: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    mutated = deepcopy(dict(slice_payload))
    operation = str(candidate.get("operation") or candidate.get("action") or "hold")
    target_windows = _target_windows(candidate, mutated)
    mutation_summary: dict[str, Any] = {
        "operation": operation,
        "changed_statement_count": 0,
        "authority_effect": "none",
        "applied_in_memory_only": True,
    }
    if operation in {"keep_current", "hold", "review_hold"}:
        return mutated, mutation_summary
    if operation in OBLIGATION_OPERATIONS:
        mutation_summary["authority_effect"] = "review_obligation_only"
        mutation_summary["candidate_obligation"] = True
        mutation_summary["promotion_required"] = True
        return mutated, mutation_summary

    selector = _candidate_selector(candidate)
    windows = _iter_windows(mutated)
    for window in windows:
        window_id = str(window.get("id"))
        if target_windows is not None and window_id not in target_windows:
            continue
        bundles = window.get("statement_bundles")
        if not isinstance(bundles, list):
            continue

        if operation == "remove":
            kept = [
                statement
                for statement in bundles
                if not (isinstance(statement, Mapping) and _matches_statement(statement, selector))
            ]
            mutation_summary["changed_statement_count"] += len(bundles) - len(kept)
            window["statement_bundles"] = kept
            continue

        if operation == "add":
            statement = _candidate_statement(candidate)
            if statement:
                bundles.append(statement)
                mutation_summary["changed_statement_count"] += 1
            continue

        if operation in {"replace", "retype", "weaken"}:
            replacement_fields = candidate.get("replacement")
            if not isinstance(replacement_fields, Mapping):
                replacement_fields = {
                    "property": candidate.get("new_property", candidate.get("property")),
                    "value": candidate.get("new_value"),
                }
            for statement in bundles:
                if not isinstance(statement, dict) or not _matches_statement(statement, selector):
                    continue
                for key, value in replacement_fields.items():
                    if value is not None:
                        statement[key] = value
                mutation_summary["changed_statement_count"] += 1
            continue

        mutation_summary["unsupported_operation"] = operation
        return mutated, mutation_summary

    if mutation_summary["changed_statement_count"]:
        mutation_summary["authority_effect"] = "candidate_slice_only"
    return mutated, mutation_summary


def _diagnostic_counts(
    report: Mapping[str, Any],
    disjointness_report: Mapping[str, Any] | None = None,
    temporal_mereology_report: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    counts = {
        "p279_scc": 0,
        "mixed_order": 0,
        "metaclass": 0,
        "parthood_typing": 0,
        "unstable_slot": len(report.get("unstable_slots", [])) if isinstance(report.get("unstable_slots"), list) else 0,
        "qualifier_drift": len(report.get("qualifier_drift", [])) if isinstance(report.get("qualifier_drift"), list) else 0,
        "reference_drift": len(report.get("reference_drift", [])) if isinstance(report.get("reference_drift"), list) else 0,
        "disjointness_subclass": 0,
        "disjointness_instance": 0,
        "mereology_overlap": 0,
        "missing_temporal_qualifier": 0,
    }
    for window in report.get("windows", []):
        if not isinstance(window, Mapping):
            continue
        diagnostics = window.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        counts["p279_scc"] += len(diagnostics.get("p279_sccs", []))
        counts["mixed_order"] += len(diagnostics.get("mixed_order_nodes", []))
        counts["metaclass"] += len(diagnostics.get("metaclass_candidates", []))
        parthood = diagnostics.get("parthood_typing")
        if isinstance(parthood, Mapping):
            classifications = parthood.get("classifications")
            counts["parthood_typing"] += (
                len(classifications) if isinstance(classifications, list) else 0
            )
    if disjointness_report is not None:
        counts["disjointness_subclass"] = int(disjointness_report.get("subclass_violation_count", 0) or 0)
        counts["disjointness_instance"] = int(disjointness_report.get("instance_violation_count", 0) or 0)
    if temporal_mereology_report is not None:
        counts["mereology_overlap"] = int(temporal_mereology_report.get("mereology_overlap_count", 0) or 0)
        counts["missing_temporal_qualifier"] = int(
            temporal_mereology_report.get("missing_temporal_qualifier_count", 0) or 0
        )
    counts["mereology"] = counts["parthood_typing"]
    counts["temporal_exclusivity"] = counts["mereology_overlap"]
    return counts


def _qualifier_values(statement: Mapping[str, Any], property_id: str) -> list[str]:
    qualifiers = statement.get("qualifiers")
    if isinstance(qualifiers, Mapping):
        raw_values = qualifiers.get(property_id, [])
        if raw_values is None:
            return []
        if isinstance(raw_values, list):
            return [str(value) for value in raw_values if value is not None]
        return [str(raw_values)]
    if isinstance(qualifiers, list):
        values: list[str] = []
        for row in qualifiers:
            if not isinstance(row, Mapping):
                continue
            if row.get("property") != property_id:
                continue
            raw_value = row.get("value")
            if raw_value is not None:
                values.append(str(raw_value))
        return values
    return []


def _has_temporal_qualifier(statement: Mapping[str, Any]) -> bool:
    return any(_qualifier_values(statement, property_id) for property_id in TEMPORAL_QUALIFIER_PROPERTIES)


def _year_from_values(values: Iterable[str]) -> int | None:
    for value in values:
        digits = "".join(char for char in str(value) if char.isdigit())
        if len(digits) >= 4:
            year = int(digits[:4])
            if 1 <= year <= 9999:
                return year
    return None


def _statement_interval(statement: Mapping[str, Any]) -> tuple[int | None, int | None] | None:
    point = _year_from_values(_qualifier_values(statement, "P585"))
    if point is not None:
        return point, point
    start = _year_from_values(_qualifier_values(statement, "P580"))
    end = _year_from_values(_qualifier_values(statement, "P582"))
    if start is None and end is None:
        return None
    return start, end


def _intervals_overlap(
    left: tuple[int | None, int | None],
    right: tuple[int | None, int | None],
) -> bool:
    left_start, left_end = left
    right_start, right_end = right
    left_start_value = float("-inf") if left_start is None else left_start
    left_end_value = float("inf") if left_end is None else left_end
    right_start_value = float("-inf") if right_start is None else right_start
    right_end_value = float("inf") if right_end is None else right_end
    return left_start_value <= right_end_value and right_start_value <= left_end_value


def _temporal_policy(packet: Mapping[str, Any]) -> dict[str, Any]:
    raw_policy = packet.get("temporal_exclusivity_policy")
    if not isinstance(raw_policy, Mapping):
        check_family_policy = packet.get("check_family_policy")
        if isinstance(check_family_policy, Mapping):
            raw_policy = check_family_policy.get("temporal_exclusivity")
    policy = dict(raw_policy) if isinstance(raw_policy, Mapping) else {}
    raw_exclusive = policy.get("exclusive_properties", DEFAULT_TEMPORAL_EXCLUSIVE_PROPERTIES)
    if isinstance(raw_exclusive, Iterable) and not isinstance(raw_exclusive, (str, bytes, Mapping)):
        exclusive_properties = sorted({str(item) for item in raw_exclusive if item is not None})
    else:
        exclusive_properties = list(DEFAULT_TEMPORAL_EXCLUSIVE_PROPERTIES)
    raw_compatible = policy.get("compatible_wholes", [])
    compatible_pairs: set[tuple[str, str]] = set()
    if isinstance(raw_compatible, list):
        for row in raw_compatible:
            if not isinstance(row, Mapping):
                continue
            left = row.get("left") or row.get("source") or row.get("whole_a")
            right = row.get("right") or row.get("target") or row.get("whole_b")
            if left is None or right is None:
                continue
            pair = tuple(sorted((str(left), str(right))))
            compatible_pairs.add(pair)
    return {
        "exclusive_properties": exclusive_properties,
        "compatible_pairs": sorted({"|".join(pair) for pair in compatible_pairs}),
    }


def _temporal_mereology_report(slice_payload: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    exclusive_properties = set(policy.get("exclusive_properties", []))
    compatible_pairs = {
        tuple(item.split("|", 1))
        for item in policy.get("compatible_pairs", [])
        if isinstance(item, str) and "|" in item
    }
    missing_temporal: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []

    windows = slice_payload.get("windows")
    if not isinstance(windows, list):
        windows = []
    for window in windows:
        if not isinstance(window, Mapping):
            continue
        window_id = str(window.get("id"))
        bundles = [
            statement
            for statement in window.get("statement_bundles", [])
            if isinstance(statement, Mapping)
        ] if isinstance(window.get("statement_bundles"), list) else []

        by_slot: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for statement in bundles:
            subject = statement.get("subject")
            property_id = statement.get("property")
            if subject is None or property_id is None:
                continue
            by_slot.setdefault((str(subject), str(property_id)), []).append(statement)

        for (subject, property_id), statements in sorted(by_slot.items()):
            if property_id in NON_EXCLUSIVE_MEREOLOGY_PROPERTIES:
                continue
            temporal_family = any(_has_temporal_qualifier(statement) for statement in statements)
            if temporal_family:
                for statement in statements:
                    if not _has_temporal_qualifier(statement):
                        missing_temporal.append(
                            {
                                "window_id": window_id,
                                "subject": subject,
                                "property": property_id,
                                "value": str(statement.get("value")),
                                "reason": "missing_temporal_qualifier",
                            }
                        )

            if property_id not in exclusive_properties:
                continue
            for left_index, left in enumerate(statements):
                left_interval = _statement_interval(left)
                if left_interval is None:
                    continue
                for right in statements[left_index + 1:]:
                    if str(left.get("value")) == str(right.get("value")):
                        continue
                    pair = tuple(sorted((str(left.get("value")), str(right.get("value")))))
                    if pair in compatible_pairs:
                        continue
                    right_interval = _statement_interval(right)
                    if right_interval is None or not _intervals_overlap(left_interval, right_interval):
                        continue
                    overlaps.append(
                        {
                            "window_id": window_id,
                            "subject": subject,
                            "property": property_id,
                            "left_value": str(left.get("value")),
                            "right_value": str(right.get("value")),
                            "left_interval": list(left_interval),
                            "right_interval": list(right_interval),
                            "reason": "temporal_exclusive_overlap",
                        }
                    )

    return {
        "schema_version": "sl.wikidata_temporal_mereology_diagnostics.v0_1",
        "policy": {
            "exclusive_properties": sorted(exclusive_properties),
            "non_exclusive_properties": sorted(NON_EXCLUSIVE_MEREOLOGY_PROPERTIES),
        },
        "missing_temporal_qualifier": missing_temporal,
        "missing_temporal_qualifier_count": len(missing_temporal),
        "mereology_overlap": overlaps,
        "mereology_overlap_count": len(overlaps),
    }


def _blocker_total(counts: Mapping[str, int]) -> int:
    rollup_keys = {"mereology", "temporal_exclusivity"}
    return sum(int(value) for key, value in counts.items() if key not in rollup_keys)


def _project(slice_payload: Mapping[str, Any], property_scope: Iterable[str]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    report = project_wikidata_payload(slice_payload, property_filter=property_scope)
    disjointness_report = None
    scope = set(property_scope)
    if {"P2738", "P11260", "P279", "P31"}.issubset(scope):
        windows = slice_payload.get("windows")
        if isinstance(windows, list) and len(windows) == 1:
            disjointness_report = project_wikidata_disjointness_payload(slice_payload)
    return report, disjointness_report


def _check_coverage(
    *,
    requested_families: Any,
    property_scope: Iterable[str],
    slice_payload: Mapping[str, Any],
    disjointness_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    requested = [
        str(item)
        for item in requested_families
        if item is not None
    ] if isinstance(requested_families, Iterable) and not isinstance(requested_families, (str, bytes, Mapping)) else []
    scope = set(property_scope)
    windows = slice_payload.get("windows")
    window_count = len(windows) if isinstance(windows, list) else 0
    required_disjointness_scope = {"P2738", "P11260", "P279", "P31"}

    supported = {
        "subclass_consistency",
        "class_order_pressure",
        "metaclass_pressure",
        "disjointness",
        "mereology",
        "temporal_exclusivity",
    }
    deferred = {
        "downstream_use": "upstream-reference index intake is not implemented in v0",
        "minimality": "candidate minimality ranking is not implemented in v0",
    }
    run: list[str] = []
    omitted: list[dict[str, str]] = []
    deferred_rows: list[dict[str, str]] = []

    for family in requested:
        if family in {"subclass_consistency", "class_order_pressure", "metaclass_pressure"}:
            run.append(family)
            continue
        if family == "disjointness":
            if disjointness_report is not None:
                run.append(family)
                continue
            missing = sorted(required_disjointness_scope - scope)
            reason = "requires exactly one window" if window_count != 1 else "missing required property scope"
            if missing:
                reason = f"{reason}: {', '.join(missing)}"
            omitted.append({"family": family, "reason": reason})
            continue
        if family == "mereology":
            if scope & ({"P361", "P527", "P17", "P131"}):
                run.append(family)
                continue
            omitted.append({"family": family, "reason": "missing mereology property scope: P361, P527, P17, or P131"})
            continue
        if family == "temporal_exclusivity":
            if scope & set(DEFAULT_TEMPORAL_EXCLUSIVE_PROPERTIES):
                run.append(family)
                continue
            omitted.append({"family": family, "reason": "missing temporal exclusivity property scope"})
            continue
        if family in deferred:
            deferred_rows.append({"family": family, "reason": deferred[family]})
            continue
        if family not in supported:
            omitted.append({"family": family, "reason": "unknown check family"})

    return {
        "requested": requested,
        "run": run,
        "omitted": omitted,
        "deferred": deferred_rows,
        "status": "complete" if not omitted else "partial",
    }


def _disposition(
    *,
    authority_policy: str,
    candidate: Mapping[str, Any],
    baseline_total: int,
    candidate_total: int,
    mutation_summary: Mapping[str, Any],
    diagnostic_delta: Mapping[str, int],
) -> str:
    if authority_policy != REVIEW_ONLY_AUTHORITY_POLICY:
        return "insufficiently_supported"
    if mutation_summary.get("unsupported_operation"):
        return "insufficiently_supported"
    operation = str(mutation_summary.get("operation") or "")
    if operation in {"hold", "review_hold"}:
        return "held"
    if operation in OBLIGATION_OPERATIONS:
        return "held"
    if operation == "keep_current":
        return "held" if baseline_total else "checked_safe_reviewable"
    if candidate.get("expected_disposition") == "held":
        return "held"
    if any(int(value) > 0 for value in diagnostic_delta.values()):
        return "held"
    if candidate_total > baseline_total:
        return "contradictory"
    if int(mutation_summary.get("changed_statement_count", 0) or 0) == 0:
        return "insufficiently_supported"
    return "checked_safe_reviewable"


def build_change_review_report(packet: Mapping[str, Any], *, packet_path: Path | None = None) -> dict[str, Any]:
    authority_policy = str(packet.get("authority_policy") or REVIEW_ONLY_AUTHORITY_POLICY)
    property_scope = _property_scope(packet)
    temporal_policy = _temporal_policy(packet)
    packet_pressure = _normalize_pressure_attribution(packet.get("pressure_attribution"))
    pnf_index = _packet_pnf_index(packet)
    wikidata_grounding = _packet_wikidata_grounding(packet)
    pressure_surface = _pressure_attribution_surface(
        raw_surface=packet.get("pressure_attribution_surface"),
        pressure_attribution=packet_pressure,
    )
    slice_payload = _load_slice(packet, packet_path=packet_path)
    baseline_report, baseline_disjointness = _project(slice_payload, property_scope)
    baseline_temporal_mereology = _temporal_mereology_report(slice_payload, temporal_policy)
    baseline_counts = _diagnostic_counts(
        baseline_report,
        baseline_disjointness,
        baseline_temporal_mereology,
    )
    baseline_total = _blocker_total(baseline_counts)
    check_coverage = _check_coverage(
        requested_families=packet.get("check_families", []),
        property_scope=property_scope,
        slice_payload=slice_payload,
        disjointness_report=baseline_disjointness,
    )

    candidate_reports: list[dict[str, Any]] = []
    raw_candidates = packet.get("candidate_repairs")
    if not isinstance(raw_candidates, list):
        raise ValueError("ChangeReviewPacket requires candidate_repairs list")

    for index, raw_candidate in enumerate(raw_candidates):
        if not isinstance(raw_candidate, Mapping):
            raise ValueError(f"candidate_repairs[{index}] must be an object")
        candidate_id = str(raw_candidate.get("id") or f"candidate_{index + 1}")
        mutated_slice, mutation_summary = _apply_candidate(slice_payload, raw_candidate)
        candidate_report, candidate_disjointness = _project(mutated_slice, property_scope)
        candidate_temporal_mereology = _temporal_mereology_report(mutated_slice, temporal_policy)
        candidate_counts = _diagnostic_counts(
            candidate_report,
            candidate_disjointness,
            candidate_temporal_mereology,
        )
        candidate_total = _blocker_total(candidate_counts)
        diagnostic_delta = {
            key: candidate_counts.get(key, 0) - baseline_counts.get(key, 0)
            for key in sorted(set(baseline_counts) | set(candidate_counts))
        }
        disposition = _disposition(
            authority_policy=authority_policy,
            candidate=raw_candidate,
            baseline_total=baseline_total,
            candidate_total=candidate_total,
            mutation_summary=mutation_summary,
            diagnostic_delta=diagnostic_delta,
        )
        pressure_attribution = _candidate_pressure_attribution(packet_pressure, raw_candidate)
        held_reasons, review_reasons = _candidate_review_reasons(
            candidate=raw_candidate,
            disposition=disposition,
            diagnostic_delta=diagnostic_delta,
            pressure_attribution=pressure_attribution,
        )
        candidate_pressure_surface = _pressure_attribution_surface(
            raw_surface=raw_candidate.get("pressure_attribution_surface"),
            pressure_attribution=pressure_attribution,
        )
        obligation = _candidate_obligation(raw_candidate, mutation_summary)
        candidate_reports.append(
            {
                "candidate_id": candidate_id,
                "operation": mutation_summary["operation"],
                "disposition": disposition,
                "authority_policy": authority_policy,
                "edit_authority": False,
                "mutation_summary": mutation_summary,
                "diagnostic_delta": diagnostic_delta,
                "pressure_delta": dict(raw_candidate.get("pressure_delta", {}))
                if isinstance(raw_candidate.get("pressure_delta"), Mapping)
                else {},
                "pressure_attribution": pressure_attribution,
                "pressure_attribution_surface": candidate_pressure_surface,
                "held_reasons": held_reasons,
                "review_reasons": review_reasons,
                "candidate_obligation": obligation is not None,
                "promotion_required": bool(obligation and obligation["promotion_required"]),
                "obligation_type": obligation["obligation_type"] if obligation else None,
                "obligation_payload": obligation["obligation_payload"] if obligation else {},
                "abstract_candidates": obligation["abstract_candidates"] if obligation else [],
                "candidate_obligation_report": obligation,
                "mutation_pnf": dict(raw_candidate.get("mutation_pnf", {}))
                if isinstance(raw_candidate.get("mutation_pnf"), Mapping)
                else {},
                "grounding_delta": dict(raw_candidate.get("grounding_delta", {}))
                if isinstance(raw_candidate.get("grounding_delta"), Mapping)
                else {},
                "candidate_grounding": dict(raw_candidate.get("candidate_grounding", {}))
                if isinstance(raw_candidate.get("candidate_grounding"), Mapping)
                else {},
                "baseline_blocker_count": baseline_total,
                "candidate_blocker_count": candidate_total,
                "candidate_diagnostic_counts": candidate_counts,
                "projection": candidate_report,
                "disjointness_report": candidate_disjointness,
                "temporal_mereology_report": candidate_temporal_mereology,
            }
        )

    disposition_counts = {disposition: 0 for disposition in SUPPORTED_DISPOSITIONS}
    for item in candidate_reports:
        disposition = str(item["disposition"])
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1

    return {
        "schema_version": CHANGE_REVIEW_REPORT_SCHEMA_VERSION,
        "packet_schema_version": packet.get("schema_version", CHANGE_REVIEW_PACKET_SCHEMA_VERSION),
        "focus_item": packet.get("focus_item"),
        "authority_policy": authority_policy,
        "edit_authority": False,
        "property_scope": property_scope,
        "check_families": packet.get("check_families", []),
        "pressure_attribution_surface": pressure_surface,
        "check_coverage": check_coverage,
        "assumptions": {
            "review_only": authority_policy == REVIEW_ONLY_AUTHORITY_POLICY,
            "in_memory_candidate_mutation_only": True,
            "no_live_wikidata_write": True,
            "no_human_assigned_residual_labels": True,
            "no_fabricated_pnf_receipts": True,
            "no_labels_by_inspection": True,
            "monotonicity_filter_respecting_only": True,
            "temporal_exclusivity_policy_is_curated": True,
            "no_fabricated_qids": True,
            "no_fabricated_pids": True,
        },
        "temporal_exclusivity_policy": {
            "exclusive_properties": temporal_policy["exclusive_properties"],
        },
        "pressure_attribution": packet_pressure,
        "pnf_index": pnf_index,
        "wikidata_grounding": wikidata_grounding,
        "baseline": {
            "diagnostic_counts": baseline_counts,
            "blocker_count": baseline_total,
            "projection": baseline_report,
            "disjointness_report": baseline_disjointness,
            "temporal_mereology_report": baseline_temporal_mereology,
        },
        "candidate_reports": candidate_reports,
        "review_summary": {
            "candidate_count": len(candidate_reports),
            "disposition_counts": disposition_counts,
            "best_blocker_count": min(
                [baseline_total] + [int(item["candidate_blocker_count"]) for item in candidate_reports]
            ),
            "non_authoritative": True,
        },
    }


def build_change_review_report_from_path(packet_path: Path) -> dict[str, Any]:
    packet = load_change_review_packet(packet_path)
    return build_change_review_report(packet, packet_path=packet_path)


__all__ = [
    "CHANGE_REVIEW_PACKET_SCHEMA_VERSION",
    "CHANGE_REVIEW_REPORT_SCHEMA_VERSION",
    "build_change_review_report",
    "build_change_review_report_from_path",
    "load_change_review_packet",
]
