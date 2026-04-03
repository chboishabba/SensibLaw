import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_d_review import (
    WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_SCHEMA_VERSION,
    build_wikidata_nat_cohort_d_operator_report,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_operator_report_fixture_is_fail_closed_and_review_only() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_operator_report_20260402.json")

    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_SCHEMA_VERSION
    assert payload["readiness"] == "review_queue_ready"
    assert payload["decision"] == "review"
    assert payload["promotion_allowed"] is False
    assert payload["summary"]["queue_size"] == 2
    assert payload["summary"]["high_priority_count"] == 2
    assert payload["summary"]["unresolved_packet_ref_count"] == 0
    assert payload["governance"]["automation_allowed"] is False
    assert payload["governance"]["can_execute_edits"] is False
    assert payload["blocked_signals"] == []
    assert payload["queue_preview"][0]["review_entity_qid"] == "Q1785637"
    assert payload["workflow_summary"]["stage"] == "follow_up"
    assert payload["workflow_summary"]["recommended_view"] == "operator_queue"
    assert payload["workflow_summary"]["counts"]["high_priority_count"] == 2
    assert payload["workflow_summary"]["promotion_gate"]["decision"] == "hold"


def test_cohort_d_operator_report_adds_blocked_signal_when_queue_not_ready() -> None:
    operator_review_surface = _load_fixture("wikidata_nat_cohort_d_operator_review_surface_20260402.json")
    operator_review_surface["readiness"] = "review_queue_incomplete"
    operator_review_surface["unresolved_packet_ref_count"] = 1

    payload = build_wikidata_nat_cohort_d_operator_report(operator_review_surface)

    assert payload["summary"]["unresolved_packet_ref_count"] == 1
    assert "unresolved_packet_refs_present" in payload["blocked_signals"]
    assert "operator_review_surface_not_ready" in payload["blocked_signals"]
    assert payload["workflow_summary"]["stage"] == "inspect"
    assert payload["workflow_summary"]["recommended_view"] == "unresolved_packet_refs"
