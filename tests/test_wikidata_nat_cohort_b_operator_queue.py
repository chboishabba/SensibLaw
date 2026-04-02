import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_b_operator_packet import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION,
    build_nat_cohort_b_operator_packet,
)
from src.ontology.wikidata_nat_cohort_b_operator_queue import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_QUEUE_SCHEMA_VERSION,
    build_nat_cohort_b_operator_queue,
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


def test_build_nat_cohort_b_operator_queue_matches_pinned_fixture() -> None:
    operator_packet = _load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json")

    queue = build_nat_cohort_b_operator_queue([operator_packet], max_queue_items=10)
    assert queue["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_QUEUE_SCHEMA_VERSION
    assert queue == expected


def test_build_nat_cohort_b_operator_queue_holds_when_any_input_packet_is_hold() -> None:
    review_bucket = build_nat_cohort_b_review_bucket(
        {
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
    )
    hold_packet = build_nat_cohort_b_operator_packet(review_bucket)
    review_packet = _load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json")

    queue = build_nat_cohort_b_operator_queue([review_packet, hold_packet])
    assert queue["queue_status"] == "hold"
    assert queue["queue_items"] == []
    assert queue["summary"]["hold_packet_count"] == 1
    assert queue["blocked_packets"][0]["packet_id"] == hold_packet["packet_id"]


def test_build_nat_cohort_b_operator_queue_holds_on_validation_errors() -> None:
    invalid_packet = {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION,
        "packet_id": "operator-packet:invalid",
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_c_wrong",
        "decision": "review",
        "selected_rows": [{"row_id": "r1"}],
    }

    queue = build_nat_cohort_b_operator_queue([invalid_packet])
    assert queue["queue_status"] == "hold"
    assert queue["queue_items"] == []
    assert queue["summary"]["validation_error_count"] == 1
    assert queue["validation_errors"][0]["error"] == "packet_not_cohort_b"
