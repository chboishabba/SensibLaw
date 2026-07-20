from __future__ import annotations

import pytest

from src.policy.statement_family_context import (
    build_statement_family_conformance_receipt,
    build_statement_family_context,
    build_statement_family_member_evidence,
)


def _context() -> dict[str, object]:
    return build_statement_family_context(
        [
            {
                "subject": "Q1",
                "property": "P1",
                "statement_id": "Q1$a",
                "value": "+2",
                "qualifiers": {"P3831": "scope-a"},
            },
            {
                "subject": "Q1",
                "property": "P1",
                "statement_id": "Q1$b",
                "value": "+3",
                "qualifiers": {"P3831": "scope-b"},
            },
            {
                "subject": "Q1",
                "property": "P1",
                "statement_id": "Q1$total",
                "value": "+5",
                "qualifiers": {},
            },
        ],
        scope_properties=["P3831"],
    )["Q1|P1"]


def test_receipt_binds_selected_statement_to_complete_reconciled_family() -> None:
    receipt = build_statement_family_conformance_receipt(
        family_context=_context(),
        selected_statement_ref="Q1$a",
        source_revision_ref="wikidata:Q1@123",
        alignment_observations={
            "period": "aligned",
            "method": "aligned",
            "unit": "aligned",
        },
        evidence_refs=["Q1$a", "Q1$b", "Q1$total"],
    )

    assert receipt["family_coverage"] == "complete"
    assert receipt["scope_partition_state"] == "already_partitioned"
    assert receipt["total_component_relation"] == "exact_reconciliation"
    assert receipt["selected_statement_ref"] == "Q1$a"
    assert receipt["conformance_context_ref"].startswith("family-conformance:")
    assert receipt["edit_effect"] == "none"


def test_receipt_rejects_statement_not_in_supplied_family() -> None:
    with pytest.raises(ValueError, match="member of the family"):
        build_statement_family_conformance_receipt(
            family_context=_context(),
            selected_statement_ref="Q1$missing",
            source_revision_ref="wikidata:Q1@123",
            alignment_observations={
                "period": "aligned",
                "method": "aligned",
                "unit": "aligned",
            },
        )


def test_member_evidence_derives_period_partition_and_conformance() -> None:
    context = _context()
    hydrated = build_statement_family_member_evidence(
        {"Q1|P1": context},
        [
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$a",
                "period_values": ["2022"],
                "period_coverage_state": "observed",
                "conformance_state": "conformant",
            },
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$b",
                "period_values": ["2023"],
                "period_coverage_state": "observed",
                "conformance_state": "conformant",
            },
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$total",
                "period_values": ["2024"],
                "period_coverage_state": "observed",
                "conformance_state": "conformant",
            },
        ],
    )["Q1|P1"]

    assert hydrated["member_evidence_coverage"] == "complete"
    assert hydrated["period_partition_state"] == "distinct_non_overlapping"
    assert hydrated["member_conformance_state"] == "all_conform"


def test_member_evidence_preserves_missing_member_as_incomplete() -> None:
    context = _context()
    hydrated = build_statement_family_member_evidence(
        {"Q1|P1": context},
        [
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$a",
                "period_values": ["2022"],
                "period_coverage_state": "observed",
                "conformance_state": "conformant",
            }
        ],
    )["Q1|P1"]

    assert hydrated["member_evidence_coverage"] == "incomplete"
    assert hydrated["period_partition_state"] == "incomplete"
    assert hydrated["member_conformance_state"] == "incomplete"


def test_member_evidence_preserves_profile_supplied_period_geometry() -> None:
    context = _context()
    hydrated = build_statement_family_member_evidence(
        {"Q1|P1": context},
        [
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$a",
                "period_values": ["2022"],
                "period_coverage_state": "observed",
                "period_shape": "point_in_time_year",
                "conformance_state": "conformant",
            },
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$b",
                "period_values": ["2023"],
                "period_coverage_state": "observed",
                "period_shape": "same_year_interval",
                "conformance_state": "conformant",
            },
            {
                "family_id": "Q1|P1",
                "statement_id": "Q1$total",
                "period_values": ["2024"],
                "period_coverage_state": "observed",
                "period_shape": "same_year_interval",
                "conformance_state": "conformant",
            },
        ],
    )["Q1|P1"]

    assert hydrated["period_geometry"] == "mixed_period_representation"
    assert hydrated["member_period_shapes"]["Q1$a"] == "point_in_time_year"


def test_reconciled_same_year_components_are_not_period_overlap() -> None:
    context = _context()
    hydrated = build_statement_family_member_evidence(
        {"Q1|P1": context},
        [
            {
                "family_id": "Q1|P1",
                "statement_id": statement_id,
                "period_values": ["2024"],
                "period_coverage_state": "observed",
                "period_shape": "same_year_interval",
                "conformance_state": "conformant",
            }
            for statement_id in context["member_statement_ids"]
        ],
    )["Q1|P1"]

    assert hydrated["period_partition_state"] == "overlapping"
    assert hydrated["period_geometry"] == "same_annual_period_component_partition"
