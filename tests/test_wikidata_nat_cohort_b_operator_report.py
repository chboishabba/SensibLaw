import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_b_operator_packet import (
    build_nat_cohort_b_operator_packet,
)
from src.ontology.wikidata_nat_cohort_b_operator_queue import (
    build_nat_cohort_b_operator_queue,
)
from src.ontology.wikidata_nat_cohort_b_operator_report import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_REPORT_SCHEMA_VERSION,
    build_nat_cohort_b_operator_report,
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


def test_build_nat_cohort_b_operator_report_matches_pinned_fixture() -> None:
    queue_payload = _load_fixture("wikidata_nat_cohort_b_operator_queue_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_report_20260402.json")

    report = build_nat_cohort_b_operator_report(queue_payload, max_examples=3)
    assert report["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_REPORT_SCHEMA_VERSION
    assert report == expected


def test_build_nat_cohort_b_operator_report_holds_when_queue_holds() -> None:
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
    queue_payload = build_nat_cohort_b_operator_queue([hold_packet])
    report = build_nat_cohort_b_operator_report(queue_payload)

    assert queue_payload["queue_status"] == "hold"
    assert report["report_status"] == "hold"
    assert report["examples"] == []
    assert report["summary"]["blocked_packet_count"] == 1
    assert report["recommendations"][0].startswith("Queue is not ready")


def test_build_nat_cohort_b_operator_report_requires_cohort_b_queue_shape() -> None:
    try:
        build_nat_cohort_b_operator_report({"cohort_id": "wrong"})
    except ValueError as exc:
        assert "cohort_b_reconciled_non_business" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-Cohort-B queue payload")
