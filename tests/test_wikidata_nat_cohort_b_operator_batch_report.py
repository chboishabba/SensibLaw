import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_b_operator_batch_report import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_BATCH_REPORT_SCHEMA_VERSION,
    build_nat_cohort_b_operator_batch_report,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_nat_cohort_b_operator_batch_report_matches_pinned_fixture() -> None:
    case1 = _load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json")
    case2 = _load_fixture("wikidata_nat_cohort_b_operator_packet_case2_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json")

    payload = build_nat_cohort_b_operator_batch_report(
        [case1, case2],
        max_queue_items=10,
        max_examples=5,
    )
    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_BATCH_REPORT_SCHEMA_VERSION
    assert payload == expected


def test_build_nat_cohort_b_operator_batch_report_holds_with_single_case() -> None:
    case1 = _load_fixture("wikidata_nat_cohort_b_operator_packet_20260402.json")
    payload = build_nat_cohort_b_operator_batch_report([case1])

    assert payload["batch_status"] == "hold"
    assert payload["decision_reasons"] == ["requires_at_least_two_operator_cases"]


def test_build_nat_cohort_b_operator_batch_report_holds_when_queue_not_ready() -> None:
    hold_case = {
        "packet_id": "operator-packet:hold",
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "decision": "hold",
        "selected_rows": [],
        "summary": {"selected_row_count": 0, "variance_flag_counts": {}},
    }
    review_case = _load_fixture("wikidata_nat_cohort_b_operator_packet_case2_20260402.json")
    payload = build_nat_cohort_b_operator_batch_report([review_case, hold_case])

    assert payload["batch_status"] == "hold"
    assert payload["decision_reasons"] == ["queue_not_ready"]
    assert payload["queue"]["queue_status"] == "hold"
