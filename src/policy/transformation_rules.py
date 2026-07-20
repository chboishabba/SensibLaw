"""Generic, non-executing coverage for reviewed transformation rules.

Domain profiles supply structural contracts and deterministic detector outcomes.
This module records versioned rules and whole-population coverage without
interpreting a domain, retrieving source data, or authorizing a transformation.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


TRANSFORMATION_RULE_SCHEMA_VERSION = "sl.transformation_rule.v0_1"
RULE_COVERAGE_REPORT_SCHEMA_VERSION = "sl.rule_coverage_report.v0_1"
CUMULATIVE_RULE_COVERAGE_REPORT_SCHEMA_VERSION = (
    "sl.cumulative_rule_coverage_report.v0_1"
)

RULE_STATES = frozenset({"candidate", "review_approved", "suspended"})
DETECTOR_PREDICATE_STATES = frozenset(
    {"satisfied", "failed", "unresolved", "not_applicable"}
)
DETECTOR_OUTCOMES = frozenset({"matched", "not_matched", "abstained"})
INCOMPLETE_EVIDENCE_KINDS = frozenset(
    {
        "recoverable_retrieval",
        "bounded_inspection",
        "source_data",
        "policy_evidence",
    }
)
COVERAGE_OUTCOMES = frozenset(
    {
        "exactly_one_rule",
        "review_or_repair_rule",
        "conflicting_rules",
        "no_rule",
        "incomplete_coverage",
        "explicitly_out_of_target_domain",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _digest(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dependency_group_assessment(value: Any) -> dict[str, Any] | None:
    """Normalize profile-supplied group geometry without interpreting it.

    A profile decides which residual/action vocabulary applies.  The generic
    coverage layer only requires a stable primary obstruction and preserves
    the evidence needed to describe one dependency group rather than treating
    each member row as an independent pathology.
    """

    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("dependency group assessment must be a mapping")
    primary = _text(value.get("primary_obstruction"))
    action = _text(value.get("candidate_action"))
    if not primary or not action:
        raise ValueError(
            "dependency group assessment requires primary_obstruction and candidate_action"
        )
    geometry = value.get("geometry") or {}
    if not isinstance(geometry, Mapping):
        raise ValueError("dependency group assessment geometry must be a mapping")
    payload: dict[str, Any] = {
        "primary_obstruction": primary,
        "secondary_obstructions": _strings(value.get("secondary_obstructions") or ()),
        "candidate_action": action,
        "affected_member_refs": _strings(value.get("affected_member_refs") or ()),
        "geometry": {
            _text(key): supplied
            for key, supplied in sorted(geometry.items())
            if _text(key)
        },
    }
    for extra_key in ("transition_receipt",):
        extra = value.get(extra_key)
        if extra is not None:
            payload[extra_key] = extra
    return payload


def _dependency_group_inventory(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group consistent profile assessments without imposing domain semantics."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        group_ref = _text(row.get("dependency_group_ref"))
        assessment = row.get("dependency_group_assessment")
        if not group_ref or not isinstance(assessment, Mapping):
            continue
        grouped.setdefault(group_ref, []).append(row)

    inventory: list[dict[str, Any]] = []
    for group_ref, members in sorted(grouped.items()):
        assessments = {
            json.dumps(
                assessment, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            for member in members
            if isinstance((assessment := member.get("dependency_group_assessment")), Mapping)
        }
        if len(assessments) != 1:
            raise ValueError("dependency group members require one shared assessment")
        assessment = json.loads(next(iter(assessments)))
        inventory.append(
            {
                "dependency_group_ref": group_ref,
                "candidate_refs": sorted(
                    {_text(member.get("candidate_ref")) for member in members}
                    - {""}
                ),
                "candidate_count": len(members),
                **assessment,
                "authority": "diagnostic_group_inventory_only",
                "execution_effect": "none",
            }
        )
    return inventory


def _dependency_group_assessment_counts(
    inventory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    family_statement_counts: Counter[str] = Counter()
    f4_family_subtypes: Counter[str] = Counter()
    f4_statement_subtypes: Counter[str] = Counter()
    f5_family_subtypes: Counter[str] = Counter()
    f5_statement_subtypes: Counter[str] = Counter()
    for row in inventory:
        obstruction = _text(row.get("primary_obstruction"))
        statement_count = row.get("candidate_count") or 0
        family_counts[obstruction] += 1
        family_statement_counts[obstruction] += statement_count
        secondary = row.get("secondary_obstructions") or ()
        geometry = row.get("geometry") or {}
        partition = _text(geometry.get("scope_partition_state"))
        total_rel = _text(geometry.get("total_component_relation"))
        period_geo = _text(geometry.get("period_geometry"))
        member_count = geometry.get("member_count") or 0

        if obstruction.startswith("F4"):
            subtype = _classify_f4_subtype(
                partition=partition,
                secondary=secondary,
                total_rel=total_rel,
                period_geo=period_geo,
                member_count=member_count,
            )
            f4_family_subtypes[subtype] += 1
            f4_statement_subtypes[subtype] += statement_count
        elif obstruction.startswith("F5"):
            subtype = _classify_f5_subtype(
                total_rel=total_rel,
                secondary=secondary,
                period_geo=period_geo,
                member_count=member_count,
            )
            f5_family_subtypes[subtype] += 1
            f5_statement_subtypes[subtype] += statement_count

    result: dict[str, Any] = {
        "family_counts": dict(sorted(family_counts.items())),
        "statement_counts": dict(sorted(family_statement_counts.items())),
    }
    if f4_family_subtypes:
        result["f4_family_subtype_counts"] = dict(sorted(f4_family_subtypes.items()))
        result["f4_statement_counts_by_subtype"] = dict(
            sorted(f4_statement_subtypes.items())
        )
    if f5_family_subtypes:
        result["f5_family_subtype_counts"] = dict(sorted(f5_family_subtypes.items()))
        result["f5_statement_counts_by_subtype"] = dict(
            sorted(f5_statement_subtypes.items())
        )
    return result


def _classify_f4_subtype(
    *,
    partition: str,
    secondary: Sequence[str],
    total_rel: str,
    period_geo: str,
    member_count: int,
) -> str:
    secondary_set = set(secondary)
    if "genuinely_overloaded_guid" in secondary_set:
        return "genuinely_overloaded_single_guid"
    if "duplicate_semantic_slot" in secondary_set:
        return "duplicate_semantic_slot"
    if "scope_not_partitioned" in secondary_set:
        return "overlapping_scope_definitions"
    if "scope_overlap" in secondary_set:
        if total_rel in {"exact_reconciliation", "incomplete_reconciliation"}:
            return "valid_multi_scope_multi_year_matrix"
        if total_rel == "contradiction":
            return "total_plus_components"
        if any("period_geometry" in s for s in secondary):
            return "valid_multi_scope_multi_year_matrix"
        return "overlapping_scope_definitions"
    if partition == "unknown":
        return "overlapping_scope_definitions"
    return "valid_multi_scope_multi_year_matrix"


def _classify_f5_subtype(
    *,
    total_rel: str,
    secondary: Sequence[str],
    period_geo: str,
    member_count: int,
) -> str:
    secondary_set = set(secondary)
    if "component_total_mismatch" in secondary_set:
        if member_count == 2:
            return "exact_contradiction"
        return "components_not_exhaustive"
    if "scope_overlap" in secondary_set:
        return "incomparable_scope_basis"
    if "duplicate_semantic_slot" in secondary_set:
        return "mixed_year_method_unit"
    if any("period_geometry" in s for s in secondary):
        return "mixed_year_method_unit"
    if total_rel == "no_total":
        return "total_absent"
    if member_count > 2:
        return "multiple_candidate_totals"
    return "exact_contradiction"


def build_transformation_rule(
    *,
    domain_contract_ref: str,
    structural_family_ref: str,
    detector_ref: str,
    transformation_contract_ref: str,
    rule_state: str = "candidate",
    evidence_refs: Sequence[str] = (),
    near_miss_refs: Sequence[str] = (),
    reviewer_approval_ref: str | None = None,
) -> dict[str, Any]:
    """Build a versioned rule description without granting execution authority."""

    state = _text(rule_state)
    required = {
        "domain_contract_ref": _text(domain_contract_ref),
        "structural_family_ref": _text(structural_family_ref),
        "detector_ref": _text(detector_ref),
        "transformation_contract_ref": _text(transformation_contract_ref),
    }
    missing = sorted(name for name, value in required.items() if not value)
    if missing:
        raise ValueError("transformation rule requires " + ", ".join(missing))
    if state not in RULE_STATES:
        raise ValueError("transformation rule has unsupported rule_state")
    approval_ref = _text(reviewer_approval_ref)
    if state == "review_approved" and not approval_ref:
        raise ValueError("review-approved rule requires reviewer_approval_ref")
    payload = {
        "schema_version": TRANSFORMATION_RULE_SCHEMA_VERSION,
        **required,
        "rule_state": state,
        "evidence_refs": _strings(evidence_refs),
        "near_miss_refs": _strings(near_miss_refs),
        "reviewer_approval_ref": approval_ref or None,
        "authority": "rule_description_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "execution_effect": "none",
    }
    payload["rule_ref"] = "transformation-rule:" + _digest(payload)
    return payload


def build_rule_detector_result(
    *,
    rule: Mapping[str, Any],
    candidate_ref: str,
    dependency_group_ref: str,
    predicate_results: Sequence[Mapping[str, Any]],
    coverage_state: str = "observed",
    target_domain_state: str = "in_scope",
    strata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one explainable, non-executing applicability result.

    Profiles own predicate meaning. The generic carrier validates that every
    predicate has an explicit state and preserves failed/unresolved evidence so
    a classifier label or similarity score cannot stand in for a contract.
    """

    if _text(rule.get("schema_version")) != TRANSFORMATION_RULE_SCHEMA_VERSION:
        raise ValueError("detector result requires a transformation rule")
    rule_ref = _text(rule.get("rule_ref"))
    candidate = _text(candidate_ref)
    dependency = _text(dependency_group_ref)
    if not rule_ref or not candidate or not dependency:
        raise ValueError(
            "detector result requires rule, candidate, and dependency group refs"
        )
    normalized: list[dict[str, Any]] = []
    seen_predicates: set[str] = set()
    for result in predicate_results:
        predicate_ref = _text(result.get("predicate_ref"))
        state = _text(result.get("state"))
        reason_code = _text(result.get("reason_code"))
        incomplete_evidence_kind = _text(result.get("incomplete_evidence_kind"))
        if not predicate_ref or predicate_ref in seen_predicates:
            raise ValueError("detector predicates require unique predicate refs")
        if state not in DETECTOR_PREDICATE_STATES:
            raise ValueError("detector predicate has unsupported state")
        if not reason_code:
            raise ValueError("detector predicate requires reason_code")
        if incomplete_evidence_kind and incomplete_evidence_kind not in INCOMPLETE_EVIDENCE_KINDS:
            raise ValueError("detector predicate has unsupported incomplete evidence kind")
        if state != "unresolved" and incomplete_evidence_kind:
            raise ValueError("only unresolved predicates may name incomplete evidence")
        seen_predicates.add(predicate_ref)
        normalized.append(
            {
                "predicate_ref": predicate_ref,
                "state": state,
                "reason_code": reason_code,
                "incomplete_evidence_kind": incomplete_evidence_kind or None,
                "observed": result.get("observed"),
                "evidence_refs": _strings(result.get("evidence_refs") or ()),
            }
        )
    if not normalized:
        raise ValueError("detector result requires predicate results")
    normalized.sort(key=lambda item: item["predicate_ref"])
    coverage = _text(coverage_state) or "unknown"
    domain_state = _text(target_domain_state) or "unknown"
    states = {item["state"] for item in normalized}
    if domain_state == "excluded" or "failed" in states:
        outcome = "not_matched"
    elif coverage != "observed" or "unresolved" in states:
        outcome = "abstained"
    elif all(state in {"satisfied", "not_applicable"} for state in states):
        outcome = "matched"
    else:
        outcome = "abstained"
    payload = {
        "rule_ref": rule_ref,
        "candidate_ref": candidate,
        "dependency_group_ref": dependency,
        "coverage_state": coverage,
        "target_domain_state": domain_state,
        "predicate_results": normalized,
        "outcome": outcome,
        "strata": {
            _text(key): value
            for key, value in sorted((strata or {}).items())
            if _text(key)
        },
        "authority": "detector_evidence_only",
        "execution_effect": "none",
    }
    payload["detector_result_ref"] = "rule-detector-result:" + _digest(payload)
    return payload


def build_rule_coverage_report(
    *,
    rules: Sequence[Mapping[str, Any]],
    candidate_evaluations: Sequence[Mapping[str, Any]],
    source_snapshot_ref: str,
) -> dict[str, Any]:
    """Classify caller-supplied rule matches for a bounded dry-run population.

    Evaluation outcomes are intentionally supplied by the profile-owned detector.
    The generic layer validates rule references and reports coverage; it never
    substitutes similarity for a detector match or creates executable edits.
    """

    snapshot_ref = _text(source_snapshot_ref)
    if not snapshot_ref:
        raise ValueError("rule coverage report requires source_snapshot_ref")
    rule_by_ref: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if _text(rule.get("schema_version")) != TRANSFORMATION_RULE_SCHEMA_VERSION:
            raise ValueError("rule coverage report requires transformation rules")
        rule_ref = _text(rule.get("rule_ref"))
        if not rule_ref or rule_ref in rule_by_ref:
            raise ValueError("rule coverage report requires unique rule refs")
        rule_by_ref[rule_ref] = dict(rule)
    if not rule_by_ref:
        raise ValueError("rule coverage report requires at least one rule")

    rows: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for evaluation in candidate_evaluations:
        candidate_ref = _text(evaluation.get("candidate_ref"))
        if not candidate_ref or candidate_ref in seen_candidates:
            raise ValueError("rule coverage report requires unique candidate refs")
        seen_candidates.add(candidate_ref)
        coverage_state = _text(evaluation.get("coverage_state"))
        detector_results = [
            dict(result) for result in evaluation.get("detector_results") or ()
        ]
        matching_rules = _strings(evaluation.get("matching_rule_refs") or ())
        if detector_results:
            for result in detector_results:
                if _text(result.get("candidate_ref")) != candidate_ref:
                    raise ValueError("detector result candidate does not match row")
                if _text(result.get("rule_ref")) not in rule_by_ref:
                    raise ValueError("rule coverage references unknown detector rule")
                if _text(result.get("outcome")) not in DETECTOR_OUTCOMES:
                    raise ValueError("rule coverage has unsupported detector outcome")
            matching_rules = _strings(
                result.get("rule_ref")
                for result in detector_results
                if result.get("outcome") == "matched"
            )
        unknown_rules = sorted(set(matching_rules) - set(rule_by_ref))
        if unknown_rules:
            raise ValueError(
                "rule coverage references unknown rule " + unknown_rules[0]
            )
        target_domain_state = _text(evaluation.get("target_domain_state"))
        exclusion_reasons = _strings(evaluation.get("exclusion_reasons") or ())
        has_abstention = any(
            result.get("outcome") == "abstained" for result in detector_results
        )
        if target_domain_state == "excluded":
            outcome = "explicitly_out_of_target_domain"
        elif coverage_state != "observed":
            outcome = "incomplete_coverage"
        elif len(matching_rules) > 1:
            outcome = "conflicting_rules"
        elif not matching_rules and has_abstention:
            outcome = "incomplete_coverage"
        elif not matching_rules:
            outcome = "no_rule"
        elif rule_by_ref[matching_rules[0]]["rule_state"] == "review_approved":
            outcome = "exactly_one_rule"
        else:
            outcome = "review_or_repair_rule"
        rows.append(
            {
                "candidate_ref": candidate_ref,
                "coverage_state": coverage_state or "unknown",
                "target_domain_state": target_domain_state or "unknown",
                "dependency_group_ref": _text(evaluation.get("dependency_group_ref"))
                or None,
                "matching_rule_refs": matching_rules,
                "detector_results": detector_results,
                "strata": dict(evaluation.get("strata") or {}),
                "exclusion_reasons": exclusion_reasons,
                "dependency_group_assessment": _dependency_group_assessment(
                    evaluation.get("dependency_group_assessment")
                ),
                "outcome": outcome,
                "execution_effect": "none",
            }
        )
    rows.sort(key=lambda row: row["candidate_ref"])
    dependency_group_inventory = _dependency_group_inventory(rows)
    counts = Counter(row["outcome"] for row in rows)
    rule_match_counts: dict[str, dict[str, Any]] = {}
    for rule_ref in sorted(rule_by_ref):
        matching_rows = [row for row in rows if rule_ref in row["matching_rule_refs"]]
        rule_match_counts[rule_ref] = {
            "candidate_count": len(matching_rows),
            "dependency_group_count": len(
                {
                    row["dependency_group_ref"]
                    for row in matching_rows
                    if row["dependency_group_ref"]
                }
            ),
        }
    strata_counts: dict[str, dict[str, dict[str, int]]] = {}
    incomplete_reason_rows: dict[str, set[str]] = {}
    incomplete_reason_groups: dict[str, set[str]] = {}
    incomplete_kind_rows: dict[str, set[str]] = {}
    incomplete_kind_groups: dict[str, set[str]] = {}
    exclusion_rows: dict[str, set[str]] = {}
    exclusion_groups: dict[str, set[str]] = {}
    no_rule_reason_rows: dict[str, set[str]] = {}
    no_rule_reason_groups: dict[str, set[str]] = {}
    for row in rows:
        for dimension, value in sorted(row["strata"].items()):
            name = _text(dimension)
            member = _text(value) or "unknown"
            if not name:
                continue
            outcome_counts = strata_counts.setdefault(name, {}).setdefault(member, {})
            outcome = row["outcome"]
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        candidate_ref = _text(row["candidate_ref"])
        dependency_group = _text(row.get("dependency_group_ref"))
        if row["outcome"] == "incomplete_coverage":
            unresolved = {
                (
                    _text(predicate.get("reason_code")),
                    _text(predicate.get("incomplete_evidence_kind")),
                )
                for result in row["detector_results"]
                for predicate in result.get("predicate_results") or ()
                if _text(predicate.get("state")) == "unresolved"
            }
            for reason_code, evidence_kind in unresolved:
                if not reason_code:
                    continue
                incomplete_reason_rows.setdefault(reason_code, set()).add(candidate_ref)
                if dependency_group:
                    incomplete_reason_groups.setdefault(reason_code, set()).add(
                        dependency_group
                    )
                if evidence_kind:
                    incomplete_kind_rows.setdefault(evidence_kind, set()).add(candidate_ref)
                    if dependency_group:
                        incomplete_kind_groups.setdefault(evidence_kind, set()).add(
                            dependency_group
                        )
        if row["outcome"] == "explicitly_out_of_target_domain":
            for reason in row["exclusion_reasons"]:
                exclusion_rows.setdefault(reason, set()).add(candidate_ref)
                if dependency_group:
                    exclusion_groups.setdefault(reason, set()).add(dependency_group)
        if row["outcome"] == "no_rule":
            failed_reasons = {
                _text(predicate.get("reason_code"))
                for result in row["detector_results"]
                for predicate in result.get("predicate_results") or ()
                if _text(predicate.get("state")) == "failed"
            }
            for reason in failed_reasons:
                if not reason:
                    continue
                no_rule_reason_rows.setdefault(reason, set()).add(candidate_ref)
                if dependency_group:
                    no_rule_reason_groups.setdefault(reason, set()).add(
                        dependency_group
                    )
    payload = {
        "schema_version": RULE_COVERAGE_REPORT_SCHEMA_VERSION,
        "source_snapshot_ref": snapshot_ref,
        "rule_refs": sorted(rule_by_ref),
        "candidate_rows": rows,
        "outcome_counts": {
            outcome: counts[outcome] for outcome in sorted(COVERAGE_OUTCOMES)
        },
        "rule_match_counts": rule_match_counts,
        "strata_outcome_counts": strata_counts,
        "incomplete_reason_counts": {
            reason: {
                "candidate_count": len(incomplete_reason_rows[reason]),
                "dependency_group_count": len(incomplete_reason_groups.get(reason, set())),
            }
            for reason in sorted(incomplete_reason_rows)
        },
        "incomplete_evidence_kind_counts": {
            kind: {
                "candidate_count": len(incomplete_kind_rows[kind]),
                "dependency_group_count": len(incomplete_kind_groups.get(kind, set())),
            }
            for kind in sorted(incomplete_kind_rows)
        },
        "explicit_exclusion_counts": {
            reason: {
                "candidate_count": len(exclusion_rows[reason]),
                "dependency_group_count": len(exclusion_groups.get(reason, set())),
            }
            for reason in sorted(exclusion_rows)
        },
        "no_rule_reason_counts": {
            reason: {
                "candidate_count": len(no_rule_reason_rows[reason]),
                "dependency_group_count": len(no_rule_reason_groups.get(reason, set())),
            }
            for reason in sorted(no_rule_reason_rows)
        },
        "dependency_group_inventory": dependency_group_inventory,
        "dependency_group_primary_obstruction_counts": _dependency_group_assessment_counts(
            dependency_group_inventory
        ),
        "dependency_group_count": len(
            {row["dependency_group_ref"] for row in rows if row["dependency_group_ref"]}
        ),
        "authority": "dry_run_coverage_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "execution_effect": "none",
    }
    payload["report_ref"] = "rule-coverage:" + _digest(payload)
    return payload


def _cursor(value: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not value:
        return None
    subject = _text(value.get("subject_qid"))
    statement = _text(value.get("statement_id"))
    if not subject or not statement:
        raise ValueError("composite cursor requires subject_qid and statement_id")
    return {"subject_qid": subject, "statement_id": statement}


def build_cumulative_rule_coverage_report(
    *,
    page_reports: Sequence[Mapping[str, Any]],
    page_boundaries: Sequence[Mapping[str, Any]],
    population_exhausted: bool = False,
    population_exhaustion_ref: str | None = None,
) -> dict[str, Any]:
    """Combine contiguous dry-run pages without hiding gaps or overlaps."""

    if not page_reports or len(page_reports) != len(page_boundaries):
        raise ValueError("cumulative coverage requires paired pages and boundaries")
    exhaustion_ref = _text(population_exhaustion_ref)
    if population_exhausted and not exhaustion_ref:
        raise ValueError("exhausted population requires an exhaustion evidence ref")
    expected_rule_refs: list[str] | None = None
    rows: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    page_refs: list[str] = []
    normalized_boundaries: list[dict[str, Any]] = []
    previous_next: dict[str, str] | None = None
    for index, (report, boundary) in enumerate(
        zip(page_reports, page_boundaries, strict=True)
    ):
        if _text(report.get("schema_version")) != RULE_COVERAGE_REPORT_SCHEMA_VERSION:
            raise ValueError("cumulative coverage requires rule coverage pages")
        rule_refs = _strings(report.get("rule_refs") or ())
        if expected_rule_refs is None:
            expected_rule_refs = rule_refs
        elif rule_refs != expected_rule_refs:
            raise ValueError("cumulative coverage pages use different rule catalogues")
        current_cursor = _cursor(boundary.get("cursor"))
        next_cursor = _cursor(boundary.get("next_cursor"))
        if index and current_cursor != previous_next:
            raise ValueError("cumulative coverage has a composite cursor gap")
        previous_next = next_cursor
        normalized_boundaries.append(
            {"cursor": current_cursor, "next_cursor": next_cursor}
        )
        report_ref = _text(report.get("report_ref"))
        if not report_ref:
            raise ValueError("cumulative coverage page requires report_ref")
        page_refs.append(report_ref)
        for supplied_row in report.get("candidate_rows") or ():
            row = dict(supplied_row)
            candidate_ref = _text(row.get("candidate_ref"))
            if not candidate_ref or candidate_ref in seen_candidates:
                raise ValueError("cumulative coverage has duplicate candidate refs")
            seen_candidates.add(candidate_ref)
            row["page_report_ref"] = report_ref
            rows.append(row)
    rows.sort(key=lambda row: row["candidate_ref"])
    dependency_group_inventory = _dependency_group_inventory(rows)
    counts = Counter(_text(row.get("outcome")) for row in rows)
    rule_match_counts: dict[str, dict[str, int]] = {}
    for rule_ref in expected_rule_refs or ():
        matching_rows = [row for row in rows if rule_ref in row["matching_rule_refs"]]
        rule_match_counts[rule_ref] = {
            "candidate_count": len(matching_rows),
            "dependency_group_count": len(
                {
                    _text(row.get("dependency_group_ref"))
                    for row in matching_rows
                    if _text(row.get("dependency_group_ref"))
                }
            ),
        }
    strata_counts: dict[str, dict[str, dict[str, int]]] = {}
    incomplete_reason_rows: dict[str, set[str]] = {}
    incomplete_reason_groups: dict[str, set[str]] = {}
    incomplete_kind_rows: dict[str, set[str]] = {}
    incomplete_kind_groups: dict[str, set[str]] = {}
    exclusion_rows: dict[str, set[str]] = {}
    exclusion_groups: dict[str, set[str]] = {}
    no_rule_reason_rows: dict[str, set[str]] = {}
    no_rule_reason_groups: dict[str, set[str]] = {}
    for row in rows:
        candidate_ref = _text(row.get("candidate_ref"))
        dependency_group = _text(row.get("dependency_group_ref"))
        for dimension, value in sorted((row.get("strata") or {}).items()):
            name = _text(dimension)
            member = _text(value) or "unknown"
            if name:
                outcome_counts = strata_counts.setdefault(name, {}).setdefault(member, {})
                outcome = _text(row.get("outcome"))
                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        if _text(row.get("outcome")) == "incomplete_coverage":
            unresolved = {
                (
                    _text(predicate.get("reason_code")),
                    _text(predicate.get("incomplete_evidence_kind")),
                )
                for result in row.get("detector_results") or ()
                for predicate in result.get("predicate_results") or ()
                if _text(predicate.get("state")) == "unresolved"
            }
            for reason_code, evidence_kind in unresolved:
                if not reason_code:
                    continue
                incomplete_reason_rows.setdefault(reason_code, set()).add(candidate_ref)
                if dependency_group:
                    incomplete_reason_groups.setdefault(reason_code, set()).add(
                        dependency_group
                    )
                if evidence_kind:
                    incomplete_kind_rows.setdefault(evidence_kind, set()).add(candidate_ref)
                    if dependency_group:
                        incomplete_kind_groups.setdefault(evidence_kind, set()).add(
                            dependency_group
                        )
        if _text(row.get("outcome")) == "explicitly_out_of_target_domain":
            for reason in row.get("exclusion_reasons") or ():
                reason_text = _text(reason)
                if not reason_text:
                    continue
                exclusion_rows.setdefault(reason_text, set()).add(candidate_ref)
                if dependency_group:
                    exclusion_groups.setdefault(reason_text, set()).add(dependency_group)
        if _text(row.get("outcome")) == "no_rule":
            failed_reasons = {
                _text(predicate.get("reason_code"))
                for result in row.get("detector_results") or ()
                for predicate in result.get("predicate_results") or ()
                if _text(predicate.get("state")) == "failed"
            }
            for reason in failed_reasons:
                if not reason:
                    continue
                no_rule_reason_rows.setdefault(reason, set()).add(candidate_ref)
                if dependency_group:
                    no_rule_reason_groups.setdefault(reason, set()).add(
                        dependency_group
                    )
    payload = {
        "schema_version": CUMULATIVE_RULE_COVERAGE_REPORT_SCHEMA_VERSION,
        "rule_refs": expected_rule_refs or [],
        "page_report_refs": page_refs,
        "page_boundaries": normalized_boundaries,
        "page_count": len(page_reports),
        "candidate_count": len(rows),
        "dependency_group_count": len(
            {
                _text(row.get("dependency_group_ref"))
                for row in rows
                if _text(row.get("dependency_group_ref"))
            }
        ),
        "population_exhausted": bool(population_exhausted),
        "population_exhaustion_ref": exhaustion_ref or None,
        "candidate_rows": rows,
        "outcome_counts": {
            outcome: counts[outcome] for outcome in sorted(COVERAGE_OUTCOMES)
        },
        "rule_match_counts": rule_match_counts,
        "strata_outcome_counts": strata_counts,
        "incomplete_reason_counts": {
            reason: {
                "candidate_count": len(incomplete_reason_rows[reason]),
                "dependency_group_count": len(incomplete_reason_groups.get(reason, set())),
            }
            for reason in sorted(incomplete_reason_rows)
        },
        "incomplete_evidence_kind_counts": {
            kind: {
                "candidate_count": len(incomplete_kind_rows[kind]),
                "dependency_group_count": len(incomplete_kind_groups.get(kind, set())),
            }
            for kind in sorted(incomplete_kind_rows)
        },
        "explicit_exclusion_counts": {
            reason: {
                "candidate_count": len(exclusion_rows[reason]),
                "dependency_group_count": len(exclusion_groups.get(reason, set())),
            }
            for reason in sorted(exclusion_rows)
        },
        "no_rule_reason_counts": {
            reason: {
                "candidate_count": len(no_rule_reason_rows[reason]),
                "dependency_group_count": len(no_rule_reason_groups.get(reason, set())),
            }
            for reason in sorted(no_rule_reason_rows)
        },
        "dependency_group_inventory": dependency_group_inventory,
        "dependency_group_primary_obstruction_counts": _dependency_group_assessment_counts(
            dependency_group_inventory
        ),
        "authority": "cumulative_dry_run_coverage_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "execution_effect": "none",
    }
    payload["report_ref"] = "cumulative-rule-coverage:" + _digest(payload)
    return payload


__all__ = [
    "COVERAGE_OUTCOMES",
    "CUMULATIVE_RULE_COVERAGE_REPORT_SCHEMA_VERSION",
    "DETECTOR_OUTCOMES",
    "DETECTOR_PREDICATE_STATES",
    "INCOMPLETE_EVIDENCE_KINDS",
    "RULE_COVERAGE_REPORT_SCHEMA_VERSION",
    "RULE_STATES",
    "TRANSFORMATION_RULE_SCHEMA_VERSION",
    "build_cumulative_rule_coverage_report",
    "build_rule_coverage_report",
    "build_rule_detector_result",
    "build_transformation_rule",
]
