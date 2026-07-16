"""Climate-GHG profile over generic transformation-rule contracts.

The module supplies bounded P5991-to-P14143 policy predicates. It does not
retrieve Wikidata, approve rules, create edit manifests, or treat an A-E
classifier label as an applicability decision.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .statement_family_context import build_statement_family_member_evidence
from .transformation_rules import (
    build_rule_coverage_report,
    build_rule_detector_result,
    build_transformation_rule,
)


DOMAIN_CONTRACT_REF = "wikidata:climate_ghg_p5991_to_p14143:v0_1"
TRANSFORMATION_CONTRACT_REF = "transform:P5991-to-P14143:preserve-statement-bundle"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _predicate(
    predicate_ref: str,
    condition: bool | None,
    *,
    reason_code: str,
    observed: Any,
    evidence_refs: Sequence[str] = (),
    incomplete_evidence_kind: str | None = None,
) -> dict[str, Any]:
    state = (
        "unresolved" if condition is None else "satisfied" if condition else "failed"
    )
    return {
        "predicate_ref": predicate_ref,
        "state": state,
        "reason_code": reason_code,
        "observed": observed,
        "evidence_refs": list(evidence_refs),
        "incomplete_evidence_kind": incomplete_evidence_kind,
    }


def build_rules() -> list[dict[str, Any]]:
    """Return the initial candidate-only A1/A2/A3 rule catalogue."""

    common = {
        "domain_contract_ref": DOMAIN_CONTRACT_REF,
        "transformation_contract_ref": TRANSFORMATION_CONTRACT_REF,
        "rule_state": "candidate",
    }
    return [
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A1:atomic-annual-total:v0_1",
            detector_ref="detector:atomic-annual-total:v0_1",
            near_miss_refs=["residual:scope-overlap", "residual:period-mismatch"],
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A2:atomic-scoped-component:v0_1",
            detector_ref="detector:atomic-scoped-component:v0_1",
            evidence_refs=[
                "review-confirmation:Q101416961$FA70FC6A-B0CD-4838-8475-375506C8B6FB"
            ],
            near_miss_refs=[
                "residual:scope-overlap",
                "residual:component-total-contradiction",
            ],
        ),
        build_transformation_rule(
            **common,
            structural_family_ref="climate-ghg:A3:already-separated-annual-series:v0_1",
            detector_ref="detector:already-separated-annual-series:v0_1",
            near_miss_refs=["residual:period-overlap", "residual:multi-year-range"],
        ),
    ]


def _common_predicates(
    candidate: Mapping[str, Any], *, target_collision_state: str
) -> list[dict[str, Any]]:
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    bundle = candidate.get("claim_bundle_before") or {}
    family = candidate.get("statement_family_context") or {}
    statement_ref = _text(candidate.get("source_statement_id"))
    subject_family = _text(classifier.get("subject_family"))
    reporting_period = _text(classifier.get("reporting_period_kind"))
    unit = _text(validation.get("resolved_unit_qid"))
    method = _text(classifier.get("method_resolution"))
    references = bundle.get("references")
    collision = _text(target_collision_state) or "unknown"
    return [
        _predicate(
            "subject.enterprise-compatible",
            True
            if subject_family == "company"
            else False
            if subject_family == "non_company"
            else None,
            reason_code="subject_company"
            if subject_family == "company"
            else "subject_not_company_or_unresolved",
            observed=subject_family or "unknown",
            evidence_refs=classifier.get("subject_resolution", {}).get(
                "matched_type_qids", ()
            ),
            incomplete_evidence_kind=(
                "bounded_inspection" if subject_family not in {"company", "non_company"} else None
            ),
        ),
        _predicate(
            "statement.target-model-safe",
            _text(validation.get("status")) == "model_safe",
            reason_code="model_safe"
            if _text(validation.get("status")) == "model_safe"
            else "model_not_safe",
            observed=_text(validation.get("status")) or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.atomic-substitution-shape",
            _text(candidate.get("classification"))
            in {"safe_equivalent", "safe_with_reference_transfer"},
            reason_code="atomic_substitution_shape"
            if _text(candidate.get("classification"))
            in {"safe_equivalent", "safe_with_reference_transfer"}
            else "statement_requires_other_disposition",
            observed=_text(candidate.get("classification")) or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.annual-period",
            reporting_period in {"single_reporting_period", "single_interval_period"},
            reason_code="annual_period_resolved"
            if reporting_period in {"single_reporting_period", "single_interval_period"}
            else "annual_period_unresolved_or_overloaded",
            observed=reporting_period or "unknown",
            evidence_refs=[statement_ref],
        ),
        _predicate(
            "statement.compatible-unit",
            True if unit else None,
            reason_code="unit_resolved" if unit else "unit_unresolved",
            observed=unit or "unknown",
            evidence_refs=[unit] if unit else (),
            incomplete_evidence_kind="source_data" if not unit else None,
        ),
        _predicate(
            "statement.recognized-method",
            True
            if method == "recognized_method"
            else None
            if method in {"", "missing_but_inferable"}
            else False,
            reason_code="method_recognized"
            if method == "recognized_method"
            else "method_unresolved_or_incompatible",
            observed=method or "unknown",
            evidence_refs=validation.get("determination_method_values", ()),
            incomplete_evidence_kind=(
                "source_data" if method in {"", "missing_but_inferable"} else None
            ),
        ),
        _predicate(
            "statement.transferable-reference",
            True
            if isinstance(references, Sequence)
            and not isinstance(references, (str, bytes))
            and bool(references)
            else None,
            reason_code="reference_present"
            if references
            else "reference_transfer_unresolved",
            observed={
                "reference_count": len(references)
                if isinstance(references, list)
                else 0
            },
            evidence_refs=[statement_ref],
            incomplete_evidence_kind="source_data" if not references else None,
        ),
        _predicate(
            "family.complete-coverage",
            True if family.get("coverage_complete") is True else None,
            reason_code="family_coverage_complete"
            if family.get("coverage_complete") is True
            else "family_coverage_incomplete",
            observed=bool(family.get("coverage_complete")),
            evidence_refs=family.get("member_statement_ids", ()),
            incomplete_evidence_kind=(
                "recoverable_retrieval" if not family.get("coverage_complete") else None
            ),
        ),
        _predicate(
            "entity.target-property-absent",
            True
            if collision == "absent"
            else False
            if collision == "present"
            else None,
            reason_code="target_property_absent"
            if collision == "absent"
            else "target_property_present_or_unresolved",
            observed=collision,
            incomplete_evidence_kind="recoverable_retrieval" if collision == "unknown" else None,
        ),
    ]


def _family_conflict_predicate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    family = candidate.get("statement_family_context") or {}
    partition = _text(family.get("scope_partition_state"))
    total_relation = _text(family.get("total_component_relation"))
    conflicting = (
        partition in {"overlapping", "overloaded"} or total_relation == "contradiction"
    )
    unresolved = partition in {"", "incomplete"} or total_relation == "not_comparable"
    return _predicate(
        "family.no-conflict",
        None if unresolved and not conflicting else not conflicting,
        reason_code="family_coherent"
        if not conflicting and not unresolved
        else "family_conflict"
        if conflicting
        else "family_coherence_unresolved",
        observed={
            "scope_partition_state": partition,
            "total_component_relation": total_relation,
        },
        evidence_refs=family.get("member_statement_ids", ()),
        incomplete_evidence_kind="bounded_inspection" if unresolved and not conflicting else None,
    )


def _target_domain(candidate: Mapping[str, Any], *, target_collision_state: str) -> tuple[str, list[str]]:
    """Classify explicit target-domain exclusions without inventing a migration rule."""

    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    subject_family = _text(classifier.get("subject_family"))
    issues = {_text(value) for value in validation.get("issues") or ()}
    collision = _text(target_collision_state) or "unknown"
    reasons: list[str] = []
    if subject_family == "non_company":
        reasons.append("X1_different_subject_domain")
    if "non_climate_unit" in issues:
        reasons.append("X5_incompatible_quantity_semantics")
    if "non_ghg_protocol_method" in issues:
        reasons.append("X5_incompatible_quantity_semantics")
    if collision == "present":
        reasons.append("X6_target_property_collision")
    if reasons:
        return "excluded", sorted(set(reasons))
    return ("in_scope" if subject_family == "company" else "unknown"), []


def _member_evidence(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Emit profile-configured member evidence for the generic family carrier."""

    family = candidate.get("statement_family_context") or {}
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    period_kind = _text(classifier.get("reporting_period_kind"))
    resolved_year = _text(validation.get("resolved_year"))
    period_observed = period_kind in {
        "single_reporting_period",
        "single_interval_period",
    } and bool(resolved_year)
    period_shape = {
        "single_reporting_period": "point_in_time_year",
        "single_interval_period": "same_year_interval",
        "multi_year_range": "multi_year_interval",
    }.get(period_kind, "absent" if not period_kind else "unparsable")
    references = (candidate.get("claim_bundle_before") or {}).get("references")
    unresolved_inputs = (
        _text(classifier.get("subject_family")) not in {"company", "non_company"}
        or not period_observed
        or not bool(_text(validation.get("resolved_unit_qid")))
        or _text(classifier.get("method_resolution"))
        in {"", "missing_but_inferable", "unresolved"}
        or not isinstance(references, Sequence)
        or isinstance(references, (str, bytes))
        or not bool(references)
    )
    direct_conformant = (
        _text(classifier.get("subject_family")) == "company"
        and _text(validation.get("status")) == "model_safe"
        and not candidate.get("split_axes")
        and period_observed
        and bool(_text(validation.get("resolved_unit_qid")))
        and _text(classifier.get("method_resolution")) == "recognized_method"
        and isinstance(references, Sequence)
        and not isinstance(references, (str, bytes))
        and bool(references)
    )
    return {
        "family_id": _text(family.get("family_id")),
        "statement_id": _text(candidate.get("source_statement_id")),
        "period_values": [resolved_year] if period_observed else [],
        "period_coverage_state": "observed" if period_observed else "unresolved",
        "period_shape": period_shape if period_observed else "unresolved",
        "conformance_state": (
            "unresolved"
            if unresolved_inputs
            else "conformant"
            if direct_conformant
            else "nonconformant"
        ),
    }


def _dependency_group_assessment(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Supply climate-family geometry for generic dependency-group inventory.

    This is a diagnostic action proposal, not a transformation decision. It
    names the strongest observed obstruction while retaining overlapping
    secondary geometry for later rule discovery and review.
    """

    family = candidate.get("statement_family_context") or {}
    member_ids = [
        _text(statement_id)
        for statement_id in family.get("member_statement_ids") or ()
        if _text(statement_id)
    ]
    partition = _text(family.get("scope_partition_state")) or "unknown"
    total_relation = _text(family.get("total_component_relation")) or "unknown"
    period_geometry = _text(family.get("period_geometry")) or "unresolved"
    period_partition = _text(family.get("period_partition_state")) or "unresolved"
    member_conformance = _text(family.get("member_conformance_state")) or "unresolved"
    member_states = family.get("member_conformance_states") or {}
    nonconforming_members = sorted(
        statement_id
        for statement_id, state in member_states.items()
        if _text(state) == "nonconformant"
    )
    conformant_members = sorted(
        statement_id
        for statement_id, state in member_states.items()
        if _text(state) == "conformant"
    )
    secondary: list[str] = []
    if total_relation == "contradiction":
        secondary.append("component_total_mismatch")
    if partition == "overlapping":
        secondary.append("scope_overlap")
    elif partition == "overloaded":
        secondary.append("scope_not_partitioned")
    if period_geometry in {
        "multi_year_interval",
        "mixed_period_representation",
        "duplicate_or_overlapping_period",
        "period_absent",
        "period_unparsable",
        "unresolved",
        "incomplete",
    }:
        secondary.append("period_geometry:" + period_geometry)
    if member_conformance == "member_conflict":
        secondary.append("mixed_member_conformance")
    elif member_conformance in {"unresolved", "incomplete"}:
        secondary.append("sibling_semantics_unresolved")

    if partition == "already_partitioned" and total_relation == "exact_reconciliation":
        primary, action, affected = (
            "F1_coherent_atomic_total_component_family",
            "preserve_existing_partition",
            member_ids,
        )
    elif total_relation == "contradiction":
        primary, action, affected = (
            "F5_contradictory_or_nonreconciling_total",
            "hold_total_reconciliation",
            member_ids,
        )
    elif partition == "overlapping":
        primary, action, affected = (
            "F4_overlapping_or_nonpartitioned_scopes",
            "hold_scope_partition",
            member_ids,
        )
    elif partition == "overloaded":
        primary, action, affected = (
            "F4_overlapping_or_nonpartitioned_scopes",
            "review_overloaded_source_statement",
            member_ids,
        )
    elif period_geometry in {
        "multi_year_interval",
        "mixed_period_representation",
        "duplicate_or_overlapping_period",
        "period_absent",
        "period_unparsable",
        "unresolved",
        "incomplete",
    }:
        primary, action, affected = (
            "F3_unresolved_or_nonannual_period_representation",
            "hold_period_geometry",
            member_ids,
        )
    elif member_conformance == "member_conflict" and conformant_members:
        primary, action, affected = (
            "F7_conformant_member_blocked_by_sibling_dependency",
            "review_member_independence",
            nonconforming_members or member_ids,
        )
    elif member_conformance == "member_conflict":
        primary, action, affected = (
            "F6_mixed_statement_semantics",
            "separate_member_semantics",
            nonconforming_members or member_ids,
        )
    elif period_partition == "distinct_non_overlapping" and member_conformance == "all_conform":
        primary, action, affected = (
            "F2_coherent_multi_year_annual_series",
            "evaluate_already_separated_series",
            member_ids,
        )
    else:
        primary, action, affected = (
            "F8_malformed_or_legacy_reconstruction_family",
            "review_family_reconstruction",
            member_ids,
        )
    return {
        "primary_obstruction": primary,
        "secondary_obstructions": secondary,
        "candidate_action": action,
        "affected_member_refs": affected,
        "geometry": {
            "scope_partition_state": partition,
            "total_component_relation": total_relation,
            "period_partition_state": period_partition,
            "period_geometry": period_geometry,
            "member_conformance_state": member_conformance,
            "member_count": len(member_ids),
        },
    }


def _hydrate_family_evidence(
    candidates: Sequence[Mapping[str, Any]],
    family_member_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    contexts: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        family = candidate.get("statement_family_context") or {}
        family_id = _text(family.get("family_id"))
        if family_id:
            contexts[family_id] = family
    evidence = [
        _member_evidence(candidate)
        for candidate in family_member_candidates
        if _text((candidate.get("statement_family_context") or {}).get("family_id"))
        in contexts
    ]
    hydrated = build_statement_family_member_evidence(contexts, evidence)
    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        copied = dict(candidate)
        family = candidate.get("statement_family_context") or {}
        copied["statement_family_context"] = dict(
            hydrated[_text(family.get("family_id"))]
        )
        enriched.append(copied)
    return enriched


def evaluate_candidate(
    candidate: Mapping[str, Any],
    *,
    rules: Sequence[Mapping[str, Any]],
    target_collision_state: str = "unknown",
) -> dict[str, Any]:
    """Evaluate one supplied candidate against the A1/A2/A3 contracts."""

    candidate_ref = _text(candidate.get("candidate_id"))
    family = candidate.get("statement_family_context") or {}
    dependency_group_ref = _text(family.get("family_id"))
    if not candidate_ref or not dependency_group_ref:
        raise ValueError("profile evaluation requires candidate and family refs")
    classifier = candidate.get("family_classifier") or {}
    validation = candidate.get("model_validation") or {}
    scope_resolution = _text(classifier.get("scope_resolution"))
    subject_family = _text(classifier.get("subject_family"))
    target_domain_state, exclusion_reasons = _target_domain(
        candidate, target_collision_state=target_collision_state
    )
    common = _common_predicates(
        candidate, target_collision_state=target_collision_state
    )
    results: list[dict[str, Any]] = []
    for rule in rules:
        family_ref = _text(rule.get("structural_family_ref"))
        predicates = list(common)
        if ":A1:" in family_ref:
            period_partition = _text(family.get("period_partition_state"))
            predicates.extend(
                [
                    _predicate(
                        "statement.entity-level-total",
                        scope_resolution == "total_unscoped",
                        reason_code="total_unscoped"
                        if scope_resolution == "total_unscoped"
                        else "not_entity_level_total",
                        observed=scope_resolution or "unknown",
                    ),
                    _predicate(
                        "family.not-distinct-annual-series",
                        period_partition != "distinct_non_overlapping",
                        reason_code="not_distinct_annual_series"
                        if period_partition != "distinct_non_overlapping"
                        else "distinct_annual_series_requires_A3",
                        observed=period_partition or "not_inspected",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _family_conflict_predicate(candidate),
                ]
            )
        elif ":A2:" in family_ref:
            partition = _text(family.get("scope_partition_state"))
            total_relation = _text(family.get("total_component_relation"))
            period_partition = _text(family.get("period_partition_state"))
            predicates.extend(
                [
                    _predicate(
                        "statement.explicit-scope",
                        scope_resolution == "explicit_scope",
                        reason_code="scope_explicit"
                        if scope_resolution == "explicit_scope"
                        else "scope_not_explicit",
                        observed=scope_resolution or "unknown",
                    ),
                    _predicate(
                        "family.non-overlapping-partition",
                        partition == "already_partitioned",
                        reason_code="partition_already_separated"
                        if partition == "already_partitioned"
                        else "partition_not_proven_non_overlapping",
                        observed=partition or "unknown",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _predicate(
                        "family.coherent-total-relation",
                        True
                        if total_relation in {"exact_reconciliation", "no_total"}
                        else False
                        if total_relation == "contradiction"
                        else None,
                        reason_code="total_relation_coherent"
                        if total_relation in {"exact_reconciliation", "no_total"}
                        else "total_relation_contradictory_or_unresolved",
                        observed=total_relation or "unknown",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                    _predicate(
                        "family.not-distinct-annual-series",
                        period_partition != "distinct_non_overlapping",
                        reason_code="not_distinct_annual_series"
                        if period_partition != "distinct_non_overlapping"
                        else "distinct_annual_series_requires_A3",
                        observed=period_partition or "not_inspected",
                        evidence_refs=family.get("member_statement_ids", ()),
                    ),
                ]
            )
        elif ":A3:" in family_ref:
            period_partition = _text(family.get("period_partition_state"))
            member_conformance = _text(family.get("member_conformance_state"))
            predicates.extend(
                [
                    _predicate(
                        "family.distinct-annual-periods",
                        True
                        if period_partition == "distinct_non_overlapping"
                        else False
                        if period_partition == "overlapping"
                        else None,
                        reason_code="annual_periods_distinct"
                        if period_partition == "distinct_non_overlapping"
                        else "annual_period_partition_unresolved",
                        observed=period_partition or "not_inspected",
                        incomplete_evidence_kind=(
                            "recoverable_retrieval"
                            if period_partition in {"incomplete", "not_inspected"}
                            else "source_data"
                            if period_partition == "unresolved"
                            else None
                        ),
                    ),
                    _predicate(
                        "family.members-independently-conform",
                        True
                        if member_conformance == "all_conform"
                        else False
                        if member_conformance == "member_conflict"
                        else None,
                        reason_code="members_independently_conform"
                        if member_conformance == "all_conform"
                        else "member_conformance_unresolved",
                        observed=member_conformance or "not_inspected",
                        incomplete_evidence_kind=(
                            "recoverable_retrieval"
                            if member_conformance in {"incomplete", "not_inspected"}
                            else "bounded_inspection"
                            if member_conformance == "unresolved"
                            else None
                        ),
                    ),
                    _family_conflict_predicate(candidate),
                ]
            )
        else:
            raise ValueError("unsupported climate transformation rule")
        results.append(
            build_rule_detector_result(
                rule=rule,
                candidate_ref=candidate_ref,
                dependency_group_ref=dependency_group_ref,
                predicate_results=predicates,
                coverage_state="observed"
                if family.get("coverage_complete")
                else "incomplete",
                target_domain_state=target_domain_state,
                strata={
                    "subject_family": subject_family or "unknown",
                    "family_shape": _text(family.get("scope_partition_state"))
                    or "unknown",
                    "reporting_period_kind": _text(
                        classifier.get("reporting_period_kind")
                    )
                    or "unknown",
                    "period_geometry": _text(family.get("period_geometry"))
                    or "unresolved",
                    "method_resolution": _text(classifier.get("method_resolution"))
                    or "unknown",
                    "scope_resolution": scope_resolution or "unknown",
                    "unit": _text(validation.get("resolved_unit_qid")) or "unknown",
                    "legacy_bucket": _text(classifier.get("bucket")) or "unknown",
                },
            )
        )
    return {
        "candidate_ref": candidate_ref,
        "dependency_group_ref": dependency_group_ref,
        "coverage_state": "observed"
        if family.get("coverage_complete")
        else "incomplete",
        "target_domain_state": target_domain_state,
        "exclusion_reasons": exclusion_reasons,
        "dependency_group_assessment": _dependency_group_assessment(candidate),
        "detector_results": results,
        "strata": results[0]["strata"] if results else {},
    }


def build_coverage_report(
    migration_pack: Mapping[str, Any],
    *,
    source_snapshot_ref: str,
    target_collision_state: str = "unknown",
    family_member_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate a bounded supplied pack and return generic dry-run coverage."""

    rules = build_rules()
    candidates = [
        dict(candidate) for candidate in migration_pack.get("candidates") or ()
    ]
    if family_member_candidates is not None:
        candidates = _hydrate_family_evidence(candidates, family_member_candidates)
    evaluations = [
        evaluate_candidate(
            candidate,
            rules=rules,
            target_collision_state=target_collision_state,
        )
        for candidate in candidates
    ]
    report = build_rule_coverage_report(
        rules=rules,
        candidate_evaluations=evaluations,
        source_snapshot_ref=source_snapshot_ref,
    )
    return {"rules": rules, "coverage": report}


__all__ = ["build_coverage_report", "build_rules", "evaluate_candidate"]
