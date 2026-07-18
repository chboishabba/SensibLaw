"""Derived evidence and governance reports for the climate-GHG V2 assessment."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from typing import Any, Mapping

from .orthogonal_assessment import validate_review_adjudications


_PRIMARY_REASON_ORDER = (
    "unresolved_semantic_slot",
    "unresolved_enterprise_subject",
    "unresolved_reference_adequacy",
    "unresolved_annual_period",
    "target_semantics_not_established",
    "other_unsupported_or_incompatible",
)
_REVIEW_FIELDS = (
    "v2_outcome_correct",
    "semantic_subtype_correct",
    "target_semantics_appropriate",
    "qualifiers_preserved",
    "qualifier_repair_needed",
    "different_target_required",
    "hold_reason_correct",
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _reasons(row: Mapping[str, Any]) -> list[str]:
    axes = row.get("axes") or {}
    predicates = row.get("eligibility_predicates") or {}
    reasons: set[str] = set()
    if (
        axes.get("slot_integrity") == "collided"
        or predicates.get("unique_semantic_slot") == "false"
    ):
        reasons.add("semantic_slot_collision")
    elif (
        axes.get("slot_integrity") == "unresolved"
        or predicates.get("unique_semantic_slot") == "unresolved"
    ):
        reasons.add("unresolved_semantic_slot")
    if predicates.get("enterprise_subject") == "unresolved":
        reasons.add("unresolved_enterprise_subject")
    if predicates.get("structurally_adequate_reference") == "unresolved":
        reasons.add("unresolved_reference_adequacy")
    if predicates.get("exact_annual_period") == "unresolved":
        reasons.add("unresolved_annual_period")
    if predicates.get("target_semantics_fit") != "true":
        reasons.add("target_semantics_not_established")
    if predicates.get("no_target_collision") == "false":
        reasons.add("target_collision")
    if predicates.get("supported_statement_shape") != "true":
        reasons.add("unsupported_statement_shape")
    if predicates.get("compatible_method") != "true":
        reasons.add("incompatible_method")
    if predicates.get("compatible_unit") != "true":
        reasons.add("incompatible_unit")
    return sorted(reasons)


def build_hold_reason_inventory(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Return exclusive primary and overlapping hold reasons."""

    primary = Counter()
    overlapping = Counter()
    rows: list[dict[str, Any]] = []
    for row in assessment.get("statements") or ():
        if (row.get("axes") or {}).get("execution_outcome") != "hold":
            continue
        reasons = _reasons(row)
        if not reasons:
            reasons = ["other_unsupported_or_incompatible"]
        primary_reason = next(
            (reason for reason in _PRIMARY_REASON_ORDER if reason in reasons),
            "other_unsupported_or_incompatible",
        )
        primary[primary_reason] += 1
        overlapping.update(reasons)
        rows.append(
            {
                "statement_ref": row["statement_ref"],
                "family_ref": row["family_ref"],
                "primary_reason": primary_reason,
                "overlapping_reasons": reasons,
            }
        )
    return {
        "schema_version": "sl.climate_ghg_hold_reason_inventory.v1",
        "authority": "diagnostic_aggregation_only",
        "execution_effect": "none",
        "hold_statement_count": len(rows),
        "primary_reason_counts": dict(sorted(primary.items())),
        "overlapping_reason_counts": dict(sorted(overlapping.items())),
        "rows": sorted(rows, key=lambda row: row["statement_ref"]),
    }


def build_coverage_reason_inventory(
    assessment: Mapping[str, Any], migration_pack: Mapping[str, Any]
) -> dict[str, Any]:
    """Explain unknown family coverage from the pinned family evidence."""

    family_rows: dict[str, Mapping[str, Any]] = {}
    for candidate in migration_pack.get("candidates") or ():
        context = candidate.get("statement_family_context") or {}
        family_ref = str(context.get("family_id") or "")
        if family_ref:
            family_rows.setdefault(family_ref, context)
    unknown = {
        str(row["family_ref"]): row
        for row in assessment.get("families") or ()
        if row.get("component_coverage") == "unknown"
    }
    counts = Counter()
    rows: list[dict[str, Any]] = []
    for family_ref, family in sorted(unknown.items()):
        members = [
            row
            for row in assessment.get("statements") or ()
            if row["family_ref"] == family_ref
        ]
        context = family_rows.get(family_ref, {})
        relation = str(context.get("total_component_relation") or "")
        if relation == "no_total" or not any(
            row.get("semantic_subtype")
            in {"organisation_wide_total", "unresolved_total_basis"}
            for row in members
        ):
            reason = "no_total_present"
        elif relation == "not_comparable":
            reason = "total_and_components_not_comparable"
        elif str(context.get("scope_partition_state") or "") == "unknown":
            reason = "component_boundary_unresolved"
        elif str(context.get("split_requirement") or "") == "manual_reconstruction":
            reason = "arithmetic_evidence_unavailable"
        else:
            reason = "source_does_not_assert_exhaustiveness"
        counts[reason] += 1
        rows.append(
            {
                "family_ref": family_ref,
                "member_count": family["member_count"],
                "reason": reason,
                "total_component_relation": relation or None,
                "scope_partition_state": context.get("scope_partition_state"),
                "split_requirement": context.get("split_requirement"),
            }
        )
    return {
        "schema_version": "sl.climate_ghg_coverage_reason_inventory.v1",
        "authority": "diagnostic_aggregation_only",
        "execution_effect": "none",
        "unknown_family_count": len(rows),
        "reason_counts": dict(sorted(counts.items())),
        "rows": rows,
    }


def build_a4_attrition_explanation(
    assessment: Mapping[str, Any], rule_coverage: Mapping[str, Any]
) -> dict[str, Any]:
    """Explain why legacy-primary A4 families missed strict A4 matches."""

    rules = {row.get("rule_ref"): row for row in rule_coverage.get("rules") or ()}
    coverage = rule_coverage.get("coverage") or {}
    legacy = {
        str(row.get("dependency_group_ref")): row
        for row in coverage.get("dependency_group_inventory") or ()
        if row.get("primary_obstruction") == "A4_coherent_multidimensional_matrix"
    }
    strict: set[str] = set()
    failures: dict[str, Counter[str]] = defaultdict(Counter)
    for row in coverage.get("candidate_rows") or ():
        family_ref = str(row.get("dependency_group_ref") or "")
        for result in row.get("detector_results") or ():
            rule = rules.get(result.get("rule_ref"), {})
            if ":A4:" not in str(rule.get("structural_family_ref") or ""):
                continue
            if result.get("outcome") == "matched":
                strict.add(family_ref)
            else:
                for predicate in result.get("predicate_results") or ():
                    state = predicate.get("state")
                    if state in {"failed", "abstained", "unresolved"}:
                        failures[family_ref][
                            str(
                                predicate.get("reason_code")
                                or predicate.get("predicate_ref")
                                or "unknown"
                            )
                        ] += 1
    v2_by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for statement in assessment.get("statements") or ():
        v2_by_family[statement["family_ref"]][
            (statement.get("axes") or {}).get("execution_outcome", "unknown")
        ] += 1
    rows = []
    for family_ref in sorted(set(legacy) - strict):
        rows.append(
            {
                "family_ref": family_ref,
                "member_count": int(legacy[family_ref].get("candidate_count") or 0),
                "failed_or_unresolved_predicates": dict(
                    sorted(failures[family_ref].items())
                ),
                "v2_outcome_counts": dict(sorted(v2_by_family[family_ref].items())),
            }
        )
    return {
        "schema_version": "sl.climate_ghg_a4_attrition_explanation.v1",
        "authority": "diagnostic_comparison_only",
        "execution_effect": "none",
        "lost_family_count": len(rows),
        "lost_statement_count": sum(row["member_count"] for row in rows),
        "rows": rows,
    }


def _review_template(
    assessment: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    rows = []
    for family in manifest.get("families") or ():
        for statement in family.get("statements") or ():
            rows.append(
                {
                    "family_ref": family["family_ref"],
                    "statement_ref": statement["statement_ref"],
                    **{field: None for field in _REVIEW_FIELDS},
                    "notes": "",
                }
            )
    return {
        "schema_version": "sl.orthogonal_review_adjudications.v1",
        "status": "pending",
        "assessment_ref": assessment["assessment_ref"],
        "provenance": dict(assessment.get("provenance") or {}),
        "selected_family_refs": manifest.get("selected_family_refs") or [],
        "statements": rows,
    }


def build_contract_proposal(
    assessment: Mapping[str, Any],
    adjudications: Mapping[str, Any],
    candidate_metadata: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate a first subtype contract from completed human adjudications."""

    by_ref = {row["statement_ref"]: row for row in assessment.get("statements") or ()}
    metrics: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    for review in adjudications.get("statements") or ():
        statement = by_ref.get(review.get("statement_ref"))
        if not statement or review.get("v2_outcome_correct") is not True:
            continue
        subtype = str(statement.get("semantic_subtype") or "unresolved")
        metrics[subtype]["reviewed"] += 1
        if statement["axes"]["execution_outcome"] == "eligible":
            eligible_ok = (
                all(
                    review.get(field) is True
                    for field in (
                        "semantic_subtype_correct",
                        "target_semantics_appropriate",
                        "qualifiers_preserved",
                    )
                )
                and review.get("different_target_required") is not True
            )
            metrics[subtype]["eligible_reviewed"] += 1
            if eligible_ok:
                metrics[subtype]["eligible_correct"] += 1
            if not eligible_ok:
                metrics[subtype]["critical_miss"] += int(
                    review.get("target_semantics_appropriate") is False
                    or review.get("qualifiers_preserved") is False
                    or review.get("different_target_required") is True
                )
    corpus = Counter(
        str(row.get("semantic_subtype") or "unresolved")
        for row in assessment.get("statements") or ()
        if (row.get("axes") or {}).get("execution_outcome") == "eligible"
    )
    candidates = []
    for subtype, values in sorted(metrics.items()):
        eligible_reviewed = values.get("eligible_reviewed", 0)
        precision = (
            values.get("eligible_correct", 0) / eligible_reviewed
            if eligible_reviewed
            else None
        )
        qualified = (
            eligible_reviewed >= 5
            and precision is not None
            and precision >= 0.95
            and values.get("critical_miss", 0) == 0
        )
        candidates.append(
            {
                "semantic_subtype": subtype,
                "eligible_population": corpus.get(subtype, 0),
                "eligible_reviewed": eligible_reviewed,
                "eligible_correct": values.get("eligible_correct", 0),
                "precision": precision,
                "critical_miss_count": values.get("critical_miss", 0),
                "qualified": qualified,
            }
        )
    priority = {
        name: index
        for index, name in enumerate(
            (
                "organisation_wide_total",
                "scope_1",
                "scope_2_aggregate",
                "scope_2_location",
                "scope_2_market",
                "scope_3_aggregate",
                "scope_3_named_category",
            )
        )
    }
    qualified = [row for row in candidates if row["qualified"]]
    selected = (
        min(
            qualified,
            key=lambda row: (
                -row["eligible_population"],
                priority.get(row["semantic_subtype"], 99),
                row["semantic_subtype"],
            ),
        )
        if qualified
        else None
    )
    canary_refs: list[str] = []
    if selected:
        by_feature: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for row in assessment.get("statements") or ():
            if (
                row.get("semantic_subtype") == selected["semantic_subtype"]
                and (row.get("axes") or {}).get("execution_outcome") == "eligible"
            ):
                ref = str(row["statement_ref"])
                metadata = (candidate_metadata or {}).get(ref, {})
                feature = (
                    str(row["family_ref"]),
                    str(metadata.get("rank") or "unknown"),
                    str(metadata.get("reference_signature") or "unknown"),
                )
                by_feature[feature].append(ref)
        for refs in by_feature.values():
            refs.sort()
        while len(canary_refs) < 25:
            added = False
            for feature in sorted(by_feature):
                if by_feature[feature]:
                    canary_refs.append(by_feature[feature].pop(0))
                    added = True
                    if len(canary_refs) == 25:
                        break
            if not added:
                break
    result = {
        "schema_version": "sl.climate_ghg_contract_proposal.v1",
        "authority": "candidate_review_only",
        "execution_effect": "none",
        "promotion_effect": "none",
        "gate": {
            "minimum_reviewed_eligible": 5,
            "minimum_precision": 0.95,
            "maximum_critical_misses": 0,
        },
        "subtype_metrics": candidates,
        "selected_subtype": selected["semantic_subtype"] if selected else None,
        "contract_status": "proposed" if selected else "diagnostic_only",
        "canary": {
            "maximum_statement_count": 25,
            "selection_strategy": "round_robin_family_rank_reference_then_statement_ref",
            "statement_refs": canary_refs,
        },
    }
    result["report_hash"] = _digest(result)
    return result


def build_evidence_outputs(
    *,
    assessment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    migration_pack: Mapping[str, Any],
    rule_coverage: Mapping[str, Any],
    adjudications: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    review = validate_review_adjudications(
        assessment=assessment,
        manifest=manifest,
        adjudications=adjudications or _review_template(assessment, manifest),
    )
    outputs = {
        "review_adjudications.json": review,
        "hold_reason_inventory.json": build_hold_reason_inventory(assessment),
        "coverage_reason_inventory.json": build_coverage_reason_inventory(
            assessment, migration_pack
        ),
        "a4_attrition_explanation.json": build_a4_attrition_explanation(
            assessment, rule_coverage
        ),
        "contract_proposal.json": build_contract_proposal(
            assessment,
            review,
            candidate_metadata={
                str(candidate.get("source_statement_id") or ""): {
                    "rank": (candidate.get("claim_bundle_before") or {}).get("rank"),
                    "reference_signature": ",".join(
                        sorted(
                            str(
                                reference.get("hash")
                                or reference.get("snaks-order")
                                or ""
                            )
                            for reference in (
                                candidate.get("claim_bundle_before") or {}
                            ).get("references")
                            or ()
                        )
                    ),
                }
                for candidate in migration_pack.get("candidates") or ()
            },
        ),
    }
    outputs["evidence_governance_manifest.json"] = {
        "schema_version": "sl.climate_ghg_evidence_governance_manifest.v1",
        "authority": "diagnostic_aggregation_only",
        "execution_effect": "none",
        "assessment_ref": assessment.get("assessment_ref"),
        "provenance": dict(assessment.get("provenance") or {}),
        "output_files": sorted((*outputs, "evidence_governance_manifest.json")),
        "output_hashes": {
            name: _digest(payload) for name, payload in sorted(outputs.items())
        },
    }
    return outputs


__all__ = [
    "build_a4_attrition_explanation",
    "build_contract_proposal",
    "build_coverage_reason_inventory",
    "build_evidence_outputs",
    "build_hold_reason_inventory",
]
