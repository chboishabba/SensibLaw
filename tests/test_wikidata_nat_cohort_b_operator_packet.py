import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_cohort_b_operator_packet import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION,
    build_nat_cohort_b_operator_packet,
)
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


def test_build_nat_cohort_b_operator_packet_from_review_bucket_fixture() -> None:
    payload = _load_fixture("wikidata_nat_cohort_b_operator_packet_input_20260402.json")
    packet = build_nat_cohort_b_operator_packet(payload, max_rows=2)

    assert packet["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION
    assert packet["cohort_id"] == "cohort_b_reconciled_non_business"
    assert packet["decision"] == "review"
    assert packet["source_bucket_decision"] == "review_only"
    assert packet["summary"]["selected_row_count"] == 2
    assert packet["summary"]["source_review_row_count"] == 2
    assert packet["summary"]["contract_violation_count"] == 0
    assert "unexpected_qualifier_properties" in packet["summary"]["variance_flag_counts"]
    assert packet["governance"]["fail_closed"] is True
    assert packet["governance"]["automation_allowed"] is False
    assert packet["selected_rows"][0]["row_id"] == "Q8646|P5991|4"


def test_build_nat_cohort_b_operator_packet_matches_pinned_fixture() -> None:
    review_bucket = _load_fixture("wikidata_nat_cohort_b_operator_packet_input_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json")

    packet = build_nat_cohort_b_operator_packet(review_bucket, max_rows=2)
    assert packet == expected


def test_build_nat_cohort_b_operator_packet_holds_when_bucket_is_hold() -> None:
    bucket_payload = {
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
            }
        ],
    }
    review_bucket = build_nat_cohort_b_review_bucket(bucket_payload)
    packet = build_nat_cohort_b_operator_packet(review_bucket)

    assert review_bucket["decision"] == "hold"
    assert packet["decision"] == "hold"
    assert packet["selected_rows"] == []
    assert packet["summary"]["contract_violation_count"] == 1
    assert packet["contract_violations"][0]["violation"] == "business_family_instance_of_in_cohort_b_payload"
    assert packet["triage_prompts"][0].startswith("Payload violated the Cohort B contract")


def test_build_nat_cohort_b_operator_packet_requires_valid_cohort_shape() -> None:
    with pytest.raises(ValueError, match="requires cohort_b_reconciled_non_business payload"):
        build_nat_cohort_b_operator_packet({"cohort_id": "wrong"})

    with pytest.raises(ValueError, match="decision must be review_only or hold"):
        build_nat_cohort_b_operator_packet(
            {
                "cohort_id": "cohort_b_reconciled_non_business",
                "decision": "review",
                "review_bucket_rows": [],
            }
        )
