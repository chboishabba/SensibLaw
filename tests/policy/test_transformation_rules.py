from __future__ import annotations

import pytest

from src.policy.transformation_rules import (
    build_cumulative_rule_coverage_report,
    build_rule_coverage_report,
    build_rule_detector_result,
    build_transformation_rule,
)


def _rule(*, state: str = "candidate") -> dict[str, object]:
    return build_transformation_rule(
        domain_contract_ref="policy:climate-ghg:v1",
        structural_family_ref="family:atomic-annual-total",
        detector_ref="detector:atomic-annual-total:v1",
        transformation_contract_ref="transform:P5991-to-P14143:preserve-bundle",
        rule_state=state,
        evidence_refs=["review:positive-1"],
        near_miss_refs=["review:negative-1"],
        reviewer_approval_ref="review:rule-approval"
        if state == "review_approved"
        else None,
    )


def test_dry_run_coverage_requires_approved_rule_for_exact_match() -> None:
    candidate_rule = _rule()
    approved_rule = _rule(state="review_approved")
    report = build_rule_coverage_report(
        rules=[candidate_rule, approved_rule],
        source_snapshot_ref="wikidata:P5991-page@revision",
        candidate_evaluations=[
            {
                "candidate_ref": "candidate:1",
                "coverage_state": "observed",
                "matching_rule_refs": [candidate_rule["rule_ref"]],
            },
            {
                "candidate_ref": "candidate:2",
                "coverage_state": "observed",
                "matching_rule_refs": [approved_rule["rule_ref"]],
            },
            {
                "candidate_ref": "candidate:3",
                "coverage_state": "incomplete",
                "matching_rule_refs": [approved_rule["rule_ref"]],
            },
        ],
    )

    assert [row["outcome"] for row in report["candidate_rows"]] == [
        "review_or_repair_rule",
        "exactly_one_rule",
        "incomplete_coverage",
    ]
    assert all(row["execution_effect"] == "none" for row in report["candidate_rows"])
    assert report["execution_effect"] == "none"


def test_coverage_rejects_unknown_rule_reference() -> None:
    with pytest.raises(ValueError, match="unknown rule"):
        build_rule_coverage_report(
            rules=[_rule()],
            source_snapshot_ref="wikidata:P5991-page@revision",
            candidate_evaluations=[
                {
                    "candidate_ref": "candidate:1",
                    "coverage_state": "observed",
                    "matching_rule_refs": ["transformation-rule:unknown"],
                }
            ],
        )


def test_detector_results_preserve_reasons_and_abstain_on_unknown_evidence() -> None:
    rule = _rule()
    result = build_rule_detector_result(
        rule=rule,
        candidate_ref="candidate:1",
        dependency_group_ref="family:1",
        predicate_results=[
            {
                "predicate_ref": "subject.company",
                "state": "satisfied",
                "reason_code": "company_observed",
                "observed": "company",
            },
            {
                "predicate_ref": "family.coverage",
                "state": "unresolved",
                "reason_code": "siblings_not_supplied",
                "observed": "incomplete",
                "incomplete_evidence_kind": "recoverable_retrieval",
            },
        ],
    )

    assert result["outcome"] == "abstained"
    assert result["execution_effect"] == "none"
    report = build_rule_coverage_report(
        rules=[rule],
        source_snapshot_ref="snapshot:1",
        candidate_evaluations=[
            {
                "candidate_ref": "candidate:1",
                "dependency_group_ref": "family:1",
                "coverage_state": "observed",
                "target_domain_state": "in_scope",
                "detector_results": [result],
            }
        ],
    )
    assert report["candidate_rows"][0]["outcome"] == "incomplete_coverage"
    assert (
        report["candidate_rows"][0]["detector_results"][0]["predicate_results"][1][
            "reason_code"
        ]
        == "company_observed"
    )
    assert report["incomplete_reason_counts"]["siblings_not_supplied"] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }
    assert report["incomplete_evidence_kind_counts"]["recoverable_retrieval"] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }


def test_explicit_out_of_domain_is_separate_from_no_rule() -> None:
    rule = _rule()
    result = build_rule_detector_result(
        rule=rule,
        candidate_ref="candidate:product",
        dependency_group_ref="family:product",
        target_domain_state="excluded",
        predicate_results=[
            {
                "predicate_ref": "subject.company",
                "state": "failed",
                "reason_code": "product_subject",
                "observed": "product",
            }
        ],
    )
    report = build_rule_coverage_report(
        rules=[rule],
        source_snapshot_ref="snapshot:1",
        candidate_evaluations=[
            {
                "candidate_ref": "candidate:product",
                "dependency_group_ref": "family:product",
                "coverage_state": "observed",
                "target_domain_state": "excluded",
                "exclusion_reasons": ["X1_different_subject_domain"],
                "detector_results": [result],
            }
        ],
    )
    assert report["candidate_rows"][0]["outcome"] == ("explicitly_out_of_target_domain")
    assert report["explicit_exclusion_counts"]["X1_different_subject_domain"] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }


def test_no_rule_reason_counts_deduplicate_predicates_across_detectors() -> None:
    first = _rule()
    second = build_transformation_rule(
        domain_contract_ref="policy:climate-ghg:v1",
        structural_family_ref="family:scoped-component",
        detector_ref="detector:scoped-component:v1",
        transformation_contract_ref="transform:P5991-to-P14143:preserve-bundle",
    )
    failed = {
        "predicate_ref": "family.no-overlap",
        "state": "failed",
        "reason_code": "family_scope_overlap",
        "observed": "overlapping",
    }
    results = [
        build_rule_detector_result(
            rule=rule,
            candidate_ref="candidate:1",
            dependency_group_ref="family:1",
            predicate_results=[failed],
        )
        for rule in (first, second)
    ]
    report = build_rule_coverage_report(
        rules=[first, second],
        source_snapshot_ref="snapshot:1",
        candidate_evaluations=[
            {
                "candidate_ref": "candidate:1",
                "dependency_group_ref": "family:1",
                "coverage_state": "observed",
                "target_domain_state": "in_scope",
                "detector_results": results,
            }
        ],
    )
    assert report["candidate_rows"][0]["outcome"] == "no_rule"
    assert report["no_rule_reason_counts"]["family_scope_overlap"] == {
        "candidate_count": 1,
        "dependency_group_count": 1,
    }


def test_coverage_collapses_profile_group_assessment_to_one_inventory_row() -> None:
    rule = _rule()
    shared = {
        "primary_obstruction": "F4_scope_overlap",
        "secondary_obstructions": ["duplicate_scope"],
        "candidate_action": "hold_scope_partition",
        "affected_member_refs": ["Q1$a", "Q1$b"],
        "geometry": {"scope_partition_state": "overlapping"},
    }
    report = build_rule_coverage_report(
        rules=[rule],
        source_snapshot_ref="snapshot:family-geometry",
        candidate_evaluations=[
            {
                "candidate_ref": "candidate:1",
                "dependency_group_ref": "family:1",
                "coverage_state": "observed",
                "dependency_group_assessment": shared,
                "detector_results": [
                    build_rule_detector_result(
                        rule=rule,
                        candidate_ref="candidate:1",
                        dependency_group_ref="family:1",
                        predicate_results=[
                            {
                                "predicate_ref": "family.no-overlap",
                                "state": "failed",
                                "reason_code": "family_scope_overlap",
                            }
                        ],
                    )
                ],
            },
            {
                "candidate_ref": "candidate:2",
                "dependency_group_ref": "family:1",
                "coverage_state": "observed",
                "dependency_group_assessment": shared,
                "detector_results": [
                    build_rule_detector_result(
                        rule=rule,
                        candidate_ref="candidate:2",
                        dependency_group_ref="family:1",
                        predicate_results=[
                            {
                                "predicate_ref": "family.no-overlap",
                                "state": "failed",
                                "reason_code": "family_scope_overlap",
                            }
                        ],
                    )
                ],
            },
        ],
    )

    assert report["dependency_group_primary_obstruction_counts"] == {
        "F4_scope_overlap": 1
    }
    assert report["dependency_group_inventory"] == [
        {
            "dependency_group_ref": "family:1",
            "candidate_refs": ["candidate:1", "candidate:2"],
            "candidate_count": 2,
            **shared,
            "authority": "diagnostic_group_inventory_only",
            "execution_effect": "none",
        }
    ]


def test_cumulative_coverage_requires_contiguous_composite_cursors() -> None:
    rule = _rule()

    def page(candidate: str) -> dict[str, object]:
        return build_rule_coverage_report(
            rules=[rule],
            source_snapshot_ref=f"snapshot:{candidate}",
            candidate_evaluations=[
                {
                    "candidate_ref": candidate,
                    "dependency_group_ref": candidate.split(":")[0],
                    "coverage_state": "observed",
                    "matching_rule_refs": [rule["rule_ref"]],
                }
            ],
        )

    cursor = {"subject_qid": "Q1", "statement_id": "Q1$one"}
    report = build_cumulative_rule_coverage_report(
        page_reports=[page("family1:one"), page("family2:two")],
        page_boundaries=[
            {"cursor": None, "next_cursor": cursor},
            {
                "cursor": cursor,
                "next_cursor": {
                    "subject_qid": "Q2",
                    "statement_id": "Q2$two",
                },
            },
        ],
    )
    assert report["candidate_count"] == 2
    assert report["page_count"] == 2
    assert report["population_exhausted"] is False
    assert report["execution_effect"] == "none"

    with pytest.raises(ValueError, match="exhaustion evidence"):
        build_cumulative_rule_coverage_report(
            page_reports=[page("family1:one")],
            page_boundaries=[{"cursor": None, "next_cursor": cursor}],
            population_exhausted=True,
        )

    with pytest.raises(ValueError, match="cursor gap"):
        build_cumulative_rule_coverage_report(
            page_reports=[page("family1:one"), page("family2:two")],
            page_boundaries=[
                {"cursor": None, "next_cursor": cursor},
                {
                    "cursor": {
                        "subject_qid": "Q9",
                        "statement_id": "Q9$gap",
                    },
                    "next_cursor": None,
                },
            ],
        )
