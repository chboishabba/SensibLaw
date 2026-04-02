import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_cohort_b_review_bucket import (
    WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION,
    build_nat_cohort_b_review_bucket,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_nat_cohort_b_review_bucket_emits_review_rows_and_variance_flags() -> None:
    payload = _load_fixture("wikidata_nat_cohort_b_review_bucket_20260402.json")
    result = build_nat_cohort_b_review_bucket(payload)

    assert result["schema_version"] == WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION
    assert result["cohort_id"] == "cohort_b_reconciled_non_business"
    assert result["decision"] == "review_only"
    assert result["summary"]["input_candidate_count"] == 2
    assert result["summary"]["valid_review_row_count"] == 2
    assert result["summary"]["contract_violation_count"] == 0
    assert len(result["review_bucket_rows"]) == 2
    assert result["review_bucket_rows"][0]["instance_of_qid"] == "Q13442814"
    assert "missing_expected_reference_properties" in result["review_bucket_rows"][0]["variance_flags"]
    assert "unexpected_qualifier_properties" in result["review_bucket_rows"][1]["variance_flags"]
    assert "unexpected_reference_properties" in result["review_bucket_rows"][1]["variance_flags"]
    assert result["contract_violations"] == []


def test_build_nat_cohort_b_review_bucket_holds_when_payload_contains_out_of_lane_rows() -> None:
    payload = {
        "schema_version": WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION,
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "candidates": [
            {
                "row_id": "Q1|P5991|1",
                "entity_qid": "Q1",
                "instance_of_qid": "Q4830453",
                "reconciled_instance_of": True,
                "qualifier_properties": ["P459"],
                "reference_properties": ["P854"],
            },
            {
                "row_id": "Q2|P5991|1",
                "entity_qid": "Q2",
                "instance_of_qid": "Q13442814",
                "reconciled_instance_of": False,
                "qualifier_properties": ["P459"],
                "reference_properties": ["P854"],
            },
        ],
    }

    result = build_nat_cohort_b_review_bucket(payload)
    assert result["decision"] == "hold"
    assert result["review_bucket_rows"] == []
    assert result["summary"]["contract_violation_count"] == 2
    assert {item["violation"] for item in result["contract_violations"]} == {
        "business_family_instance_of_in_cohort_b_payload",
        "unreconciled_instance_of_in_cohort_b_payload",
    }


def test_build_nat_cohort_b_review_bucket_requires_schema_and_candidate_shape() -> None:
    with pytest.raises(ValueError, match="must use"):
        build_nat_cohort_b_review_bucket({"schema_version": "wrong", "candidates": []})
    with pytest.raises(ValueError, match="requires candidates list"):
        build_nat_cohort_b_review_bucket(
            {"schema_version": WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION}
        )
