import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_d_review import (
    WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_BATCH_SCHEMA_VERSION,
    build_wikidata_nat_cohort_d_operator_report_batch,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_operator_report_batch_fixture_aggregates_readiness_and_blockers() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_operator_report_batch_20260402.json")

    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_BATCH_SCHEMA_VERSION
    assert payload["batch_id"] == "cohort_d_operator_batch_20260402"
    assert payload["decision"] == "review"
    assert payload["promotion_allowed"] is False
    assert payload["summary"]["case_count"] == 2
    assert payload["summary"]["readiness_counts"] == {
        "review_queue_ready": 1,
        "review_queue_incomplete": 1,
    }
    assert payload["summary"]["all_cases_ready"] is False
    assert payload["summary"]["total_unresolved_packet_ref_count"] == 1
    assert "operator_review_surface_not_ready" in payload["blocked_signals"]
    assert "unresolved_packet_refs_present" in payload["blocked_signals"]


def test_cohort_d_operator_report_batch_builder_accepts_operator_review_surfaces() -> None:
    batch_input = _load_fixture("wikidata_nat_cohort_d_operator_report_batch_input_20260402.json")
    payload = build_wikidata_nat_cohort_d_operator_report_batch(
        operator_review_surfaces=batch_input["operator_review_surfaces"],
        batch_id=batch_input["batch_id"],
    )

    assert payload["batch_id"] == "cohort_d_operator_batch_20260402"
    assert payload["summary"]["case_count"] == 2
    assert len(payload["case_reports"]) == 2
