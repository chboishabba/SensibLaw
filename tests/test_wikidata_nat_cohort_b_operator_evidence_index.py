import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_b_operator_evidence_index import (
    WIKIDATA_NAT_COHORT_B_OPERATOR_EVIDENCE_INDEX_SCHEMA_VERSION,
    build_nat_cohort_b_operator_evidence_index,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_nat_cohort_b_operator_evidence_index_matches_pinned_fixture() -> None:
    batch1 = _load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json")
    batch2 = _load_fixture("wikidata_nat_cohort_b_operator_batch_report_case2_20260402.json")
    expected = _load_fixture("wikidata_nat_cohort_b_operator_evidence_index_20260402.json")

    payload = build_nat_cohort_b_operator_evidence_index(
        [batch1, batch2],
        min_ready_batches=2,
    )
    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_B_OPERATOR_EVIDENCE_INDEX_SCHEMA_VERSION
    assert payload == expected


def test_build_nat_cohort_b_operator_evidence_index_holds_on_insufficient_ready_batches() -> None:
    batch1 = _load_fixture("wikidata_nat_cohort_b_operator_batch_report_20260402.json")
    payload = build_nat_cohort_b_operator_evidence_index([batch1], min_ready_batches=2)

    assert payload["index_status"] == "hold"
    assert payload["decision_reasons"] == ["insufficient_ready_batches"]
    assert payload["ready_batch_ids"] == []


def test_build_nat_cohort_b_operator_evidence_index_holds_on_validation_error() -> None:
    invalid = {"cohort_id": "cohort_x", "batch_status": "batch_review_ready"}
    payload = build_nat_cohort_b_operator_evidence_index([invalid], min_ready_batches=1)

    assert payload["index_status"] == "hold"
    assert payload["decision_reasons"] == ["validation_errors_present"]
    assert payload["summary"]["validation_error_count"] == 1
