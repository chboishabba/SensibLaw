from __future__ import annotations

from copy import deepcopy

from src.policy.climate_ghg_transformation_profile import (
    build_coverage_report,
    build_rules,
    evaluate_candidate,
)


def _candidate(*, scope: str = "explicit_scope") -> dict[str, object]:
    return {
        "candidate_id": "Q1|P5991|1",
        "source_statement_id": "Q1$statement-1",
        "classification": "safe_with_reference_transfer",
        "family_classifier": {
            "bucket": "A",
            "subject_family": "company",
            "reporting_period_kind": "single_interval_period",
            "scope_resolution": scope,
            "method_resolution": "recognized_method",
            "subject_resolution": {"matched_type_qids": ["Q783794"]},
        },
        "model_validation": {
            "status": "model_safe",
            "resolved_unit_qid": "Q57084755",
            "determination_method_values": ["Q56296245"],
        },
        "claim_bundle_before": {
            "references": [{"P854": ["https://example.test/report.pdf"]}]
        },
        "statement_family_context": {
            "family_id": "Q1|P5991",
            "coverage_complete": True,
            "member_statement_ids": ["Q1$statement-1", "Q1$total"],
            "scope_partition_state": "already_partitioned",
            "total_component_relation": "exact_reconciliation",
        },
    }


def test_a2_matches_coherent_scoped_component_without_approving_rule() -> None:
    rules = build_rules()
    evaluation = evaluate_candidate(
        _candidate(), rules=rules, target_collision_state="absent"
    )
    matched = [
        result
        for result in evaluation["detector_results"]
        if result["outcome"] == "matched"
    ]
    assert len(matched) == 1
    assert ":A2:" in next(
        rule["structural_family_ref"]
        for rule in rules
        if rule["rule_ref"] == matched[0]["rule_ref"]
    )

    report = build_coverage_report(
        {"candidates": [_candidate()]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
    )
    assert report["coverage"]["outcome_counts"]["review_or_repair_rule"] == 1
    matched_rule = report["coverage"]["candidate_rows"][0]["matching_rule_refs"][0]
    assert report["coverage"]["rule_match_counts"][matched_rule] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }
    assert report["coverage"]["strata_outcome_counts"]["legacy_bucket"]["A"] == {
        "review_or_repair_rule": 1
    }
    assert report["coverage"]["execution_effect"] == "none"


def test_legacy_a_label_does_not_override_family_overlap() -> None:
    candidate = _candidate()
    candidate["statement_family_context"]["scope_partition_state"] = "overlapping"
    candidate["statement_family_context"]["total_component_relation"] = "not_comparable"
    evaluation = evaluate_candidate(
        candidate, rules=build_rules(), target_collision_state="absent"
    )
    assert all(
        result["outcome"] != "matched" for result in evaluation["detector_results"]
    )


def test_a3_abstains_until_period_partition_and_member_conformance_are_observed() -> (
    None
):
    candidate = _candidate()
    evaluation = evaluate_candidate(
        candidate, rules=build_rules(), target_collision_state="absent"
    )
    a3 = next(
        result
        for result in evaluation["detector_results"]
        if any(
            predicate["predicate_ref"] == "family.distinct-annual-periods"
            for predicate in result["predicate_results"]
        )
    )
    assert a3["outcome"] == "abstained"

    observed = deepcopy(candidate)
    observed["statement_family_context"]["period_partition_state"] = (
        "distinct_non_overlapping"
    )
    observed["statement_family_context"]["member_conformance_state"] = "all_conform"
    observed_evaluation = evaluate_candidate(
        observed, rules=build_rules(), target_collision_state="absent"
    )
    observed_a3 = next(
        result
        for result in observed_evaluation["detector_results"]
        if any(
            predicate["predicate_ref"] == "family.distinct-annual-periods"
            for predicate in result["predicate_results"]
        )
    )
    assert observed_a3["outcome"] == "matched"


def test_family_member_hydration_allows_a3_only_with_complete_conforming_series() -> None:
    first = _candidate(scope="total_unscoped")
    first["candidate_id"] = "Q1|P5991|1"
    first["source_statement_id"] = "Q1$year-2023"
    first["model_validation"]["resolved_year"] = "2023"
    first["statement_family_context"] = {
        "family_id": "Q1|P5991",
        "coverage_complete": True,
        "member_statement_ids": ["Q1$year-2023", "Q1$year-2024"],
        "scope_partition_state": "unknown",
        "total_component_relation": "no_total",
    }
    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$year-2024"
    second["model_validation"]["resolved_year"] = "2024"

    report = build_coverage_report(
        {"candidates": [first]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )
    row = report["coverage"]["candidate_rows"][0]
    a3 = next(
        result
        for result in row["detector_results"]
        if any(
            predicate["predicate_ref"] == "family.distinct-annual-periods"
            for predicate in result["predicate_results"]
        )
    )
    assert a3["outcome"] == "matched"
    assert row["outcome"] == "review_or_repair_rule"


def test_explicit_target_domain_exclusion_is_not_no_rule() -> None:
    candidate = _candidate()
    candidate["family_classifier"]["subject_family"] = "non_company"
    candidate["family_classifier"]["subject_resolution"] = {}
    report = build_coverage_report(
        {"candidates": [candidate]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
    )
    coverage = report["coverage"]
    assert coverage["candidate_rows"][0]["outcome"] == "explicitly_out_of_target_domain"
    assert coverage["explicit_exclusion_counts"]["X1_different_subject_domain"] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }


def test_profile_emits_one_family_geometry_assessment_for_all_members() -> None:
    first = _candidate()
    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$total"
    first["statement_family_context"]["member_statement_ids"] = [
        "Q1$statement-1",
        "Q1$total",
    ]
    second["statement_family_context"] = deepcopy(first["statement_family_context"])
    report = build_coverage_report(
        {"candidates": [first, second]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
    )

    inventory = report["coverage"]["dependency_group_inventory"]
    assert len(inventory) == 1
    assert inventory[0]["primary_obstruction"] == (
        "F1_coherent_atomic_total_component_family"
    )
    assert inventory[0]["candidate_count"] == 2


def test_fiscal_year_p580_p582_resolves_canonical_year() -> None:
    from src.policy.climate_ghg_transformation_profile import GHGStatementSlot
    cand = _candidate()
    cand["claim_bundle_before"]["qualifiers"] = {
        "P580": ["2021-04-01"],
        "P582": ["2022-03-31"],
    }
    slot = GHGStatementSlot.from_candidate(cand)
    assert slot.year == "2022"
    assert slot.slot_identity_state == "fiscal_canonical"


def test_h4b_when_slot_identity_state_is_unresolved() -> None:
    first = _candidate()
    first["claim_bundle_before"]["value"] = "100"
    first["claim_bundle_before"]["qualifiers"] = {}
    first["model_validation"]["resolved_year"] = None
    first["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$statement-2"

    report = build_coverage_report(
        {"candidates": [first]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )

    inv = report["coverage"]["dependency_group_inventory"]
    assert len(inv) == 1
    assert inv[0]["primary_obstruction"] == "H4b_provisional_duplicate_unresolved_coordinate"
    assert inv[0]["candidate_action"] == "hold_provisional_collision"


def test_h4a_confirmed_when_year_exact() -> None:
    first = _candidate()
    first["claim_bundle_before"]["value"] = "100"
    first["claim_bundle_before"]["qualifiers"] = {
        "P585": ["2021-01-01"]
    }
    first["model_validation"]["resolved_year"] = "2021"
    first["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$statement-2"

    report = build_coverage_report(
        {"candidates": [first]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )

    inv = report["coverage"]["dependency_group_inventory"]
    assert len(inv) == 1
    assert inv[0]["primary_obstruction"] == "H4a_confirmed_duplicate_semantic_slot"
    assert inv[0]["candidate_action"] == "review_duplicate_slot"


def test_h4c_conflicting_value() -> None:
    first = _candidate()
    first["claim_bundle_before"]["value"] = "100"
    first["claim_bundle_before"]["qualifiers"] = {
        "P585": ["2021-01-01"]
    }
    first["model_validation"]["resolved_year"] = "2021"
    first["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$statement-2"
    second["claim_bundle_before"]["value"] = "200"

    report = build_coverage_report(
        {"candidates": [first]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )

    inv = report["coverage"]["dependency_group_inventory"]
    assert len(inv) == 1
    assert inv[0]["primary_obstruction"] == "H4c_conflicting_value_semantic_slot"
    assert inv[0]["candidate_action"] == "review_conflicting_values"


def test_h4d_rank_variant() -> None:
    first = _candidate()
    first["claim_bundle_before"]["value"] = "100"
    first["claim_bundle_before"]["rank"] = "normal"
    first["claim_bundle_before"]["qualifiers"] = {
        "P585": ["2021-01-01"]
    }
    first["model_validation"]["resolved_year"] = "2021"
    first["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    second = deepcopy(first)
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$statement-2"
    second["claim_bundle_before"]["rank"] = "preferred"

    report = build_coverage_report(
        {"candidates": [first]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )

    inv = report["coverage"]["dependency_group_inventory"]
    assert len(inv) == 1
    assert inv[0]["primary_obstruction"] == "H4d_rank_variant_semantic_slot"
    assert inv[0]["candidate_action"] == "review_rank_supersession"


def test_fiscal_fiscal_collision_dissolves_to_f1() -> None:
    first = _candidate()
    first["claim_bundle_before"]["value"] = "100"
    first["claim_bundle_before"]["qualifiers"] = {
        "P580": ["2021-04-01"],
        "P582": ["2022-03-31"],
    }
    first["model_validation"]["resolved_year"] = None
    first["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    second = _candidate()
    second["candidate_id"] = "Q1|P5991|2"
    second["source_statement_id"] = "Q1$statement-2"
    second["claim_bundle_before"]["value"] = "200"
    second["claim_bundle_before"]["qualifiers"] = {
        "P580": ["2022-04-01"],
        "P582": ["2023-03-31"],
    }
    second["model_validation"]["resolved_year"] = None
    second["statement_family_context"]["member_statement_ids"] = ["Q1$statement-1", "Q1$statement-2"]

    report = build_coverage_report(
        {"candidates": [first, second]},
        source_snapshot_ref="wdqs:page-1",
        target_collision_state="absent",
        family_member_candidates=[first, second],
    )

    inv = report["coverage"]["dependency_group_inventory"]
    assert len(inv) == 1
    assert inv[0]["primary_obstruction"] == "F1_coherent_atomic_total_component_family"
