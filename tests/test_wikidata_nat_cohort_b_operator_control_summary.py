import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_b_operator_control_summary import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_CONTROL_SUMMARY_SCHEMA_VERSION,
    build_nat_cohort_b_operator_control_summary,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_nat_cohort_b_operator_control_summary_matches_pinned_fixture() -> None:
    index1 = _load_fixture("wikidata_nat_cohort_b_operator_evidence_index_20260402.json")
    index2 = _load_fixture("wikidata_nat_cohort_b_operator_evidence_index_case2_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_control_summary_20260402.json")

    payload = build_nat_cohort_b_operator_control_summary(
        [index1, index2],
        min_ready_indexes=2,
    )
    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_CONTROL_SUMMARY_SCHEMA_VERSION
    assert payload == expected


def test_build_nat_cohort_b_operator_control_summary_holds_on_insufficient_ready_indexes() -> None:
    index2 = _load_fixture("wikidata_nat_cohort_b_operator_evidence_index_case2_20260402.json")
    payload = build_nat_cohort_b_operator_control_summary([index2], min_ready_indexes=2)

    assert payload["control_status"] == "hold"
    assert payload["decision_reasons"] == ["insufficient_ready_indexes"]
    assert payload["ready_index_ids"] == []


def test_build_nat_cohort_b_operator_control_summary_holds_on_validation_error() -> None:
    invalid = {"cohort_id": "cohort_x", "index_status": "review_index_ready"}
    payload = build_nat_cohort_b_operator_control_summary([invalid], min_ready_indexes=1)

    assert payload["control_status"] == "hold"
    assert payload["decision_reasons"] == ["validation_errors_present"]
    assert payload["summary"]["validation_error_count"] == 1
