from __future__ import annotations

import json
from pathlib import Path

from src.fact_intake.fact_extraction_probe import build_fact_extraction_probe


def test_fact_extraction_probe_builds_receipt_backed_fact_statuses() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "fact_intake" / "fact_extraction_probe_v0_1.json"
    fixture = json.loads(fixture_path.read_text())

    probe = build_fact_extraction_probe(
        fact_cases=fixture["fact_cases"],
        source=fixture["source"],
    )

    expected = fixture["expected"]
    assert probe["schema_version"] == "sl.fact_extraction_probe.v0_1"
    assert probe["case_count"] == expected["case_count"]
    assert probe["summary"]["status_counts"] == expected["status_counts"]
    assert probe["summary"]["residual_counts"] == expected["residual_counts"]
    assert probe["summary"]["missing_receipt_cases"] == expected["missing_receipt_cases"]
    assert probe["summary"]["contested_cases"] == expected["contested_cases"]
    assert probe["summary"]["abstained_cases"] == expected["abstained_cases"]
    assert probe["authority_boundary"]["raw_sentence_as_fact"] is False
    assert probe["authority_boundary"]["facts_require_source_excerpt_statement_observation_receipts"] is True
    assert probe["authority_boundary"]["predicate_pnf_fibres_gate_comparison"] is True

    by_case = {case["case_id"]: case for case in probe["cases"]}

    ordinary = by_case["ordinary_observed_fact"]
    assert ordinary["fact_candidate"]["status"] == "promoted"
    assert ordinary["aggregate_residual"] == "exact"
    assert ordinary["promotion_gate"]["gate_status"] == "passed"

    uncertain = by_case["uncertain_fragment"]
    assert uncertain["fact_candidate"]["status"] == "candidate"
    assert uncertain["aggregate_residual"] == "partial"
    assert uncertain["evidence_comparisons"][0]["residual"]["missing_roles"] == ["certainty"]

    contradiction = by_case["contradictory_chronology"]
    assert contradiction["fact_candidate"]["status"] == "contested"
    assert contradiction["contradiction_count"] == 1
    assert contradiction["aggregate_residual"] == "contradiction"

    no_typed_meet = by_case["no_typed_meet"]
    assert no_typed_meet["fact_candidate"]["status"] == "abstained"
    assert no_typed_meet["aggregate_residual"] == "no_typed_meet"
    assert no_typed_meet["evidence_comparisons"][0]["residual"]["level"] == "no_typed_meet"

    missing = by_case["missing_receipt"]
    assert missing["fact_candidate"]["status"] == "blocked_missing_receipt"
    assert missing["missing_receipts"] == ["observation"]
    assert "missing_observation_receipt" in missing["promotion_gate"]["blockers"]


def test_fact_extraction_probe_pins_constraint_carrier_and_violation_boundary() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "fact_intake" / "fact_extraction_probe_v0_1.json"
    fixture = json.loads(fixture_path.read_text())
    probe = build_fact_extraction_probe(
        fact_cases=fixture["fact_cases"],
        source=fixture["source"],
    )
    by_case = {case["case_id"]: case for case in probe["cases"]}

    carrier = by_case["constraint_carrier"]
    assert carrier["lane"] == "constraint_fact"
    assert carrier["fact_candidate"]["status"] == "supported"
    assert carrier["aggregate_residual"] == "exact"
    assert carrier["promotion_gate"]["gate_status"] == "not_promoted"
    assert carrier["authority_policy"] == "review_only"

    violation = by_case["constraint_violation"]
    assert violation["fact_candidate"]["status"] == "contested"
    assert violation["aggregate_residual"] == "contradiction"
    assert violation["evidence_comparisons"][0]["residual"]["contradictions"] == ["polarity conflict"]
    assert violation["promotion_gate"]["blockers"] == ["constraint_violation"]
