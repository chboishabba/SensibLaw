import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_d_review import (
    WIKIDATA_NAT_COHORT_D_REVIEW_CONTROL_INDEX_SCHEMA_VERSION,
    _build_control_index_workflow_summary,
    build_wikidata_nat_cohort_d_review_control_index,
)
from src.policy.decision_surface import build_decision_surface


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_review_control_index_fixture_preserves_blockers_and_hold_signals() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_review_control_index_20260402.json")

    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_D_REVIEW_CONTROL_INDEX_SCHEMA_VERSION
    assert payload["index_id"] == "cohort_d_review_control_index_20260402"
    assert payload["decision"] == "review"
    assert payload["promotion_allowed"] is False
    assert payload["summary"]["batch_count"] == 2
    assert payload["summary"]["readiness_counts"] == {
        "review_queue_ready": 1,
        "review_queue_incomplete": 1,
    }
    assert payload["summary"]["all_batches_ready"] is False
    assert "batch_not_all_cases_ready" in payload["blocked_signals"]
    assert payload["hold_signals"] == [
        "promotion_guard_hold_enforced",
        "incomplete_batch_present",
        "unresolved_packet_refs_present",
    ]
    assert payload["workflow_summary"]["stage"] == "inspect"
    assert payload["workflow_summary"]["recommended_view"] == "batch_entries"
    assert payload["workflow_summary"]["counts"]["total_unresolved_packet_ref_count"] == 1


def test_cohort_d_review_control_index_builder_accepts_batch_reports() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_review_control_index_input_20260402.json")
    report = build_wikidata_nat_cohort_d_review_control_index(
        batch_reports=payload["batch_reports"],
        index_id=payload["index_id"],
    )

    assert report["index_id"] == "cohort_d_review_control_index_20260402"
    assert report["summary"]["batch_count"] == 2
    assert len(report["batch_entries"]) == 2
    assert report["workflow_summary"]["stage"] == "inspect"
    assert report["workflow_summary"]["recommended_view"] == "batch_entries"


def test_cohort_d_control_index_workflow_summary_uses_shared_decision_surface() -> None:
    summary = _build_control_index_workflow_summary(
        all_batches_ready=False,
        batch_count=2,
        case_count=5,
        total_queue_size=3,
        total_unresolved_packet_ref_count=1,
        promotion_guard="hold",
    )

    assert summary == build_decision_surface(
        counts={
            "batch_count": 2,
            "case_count": 5,
            "total_queue_size": 3,
            "total_unresolved_packet_ref_count": 1,
        },
        promotion_gate={"decision": "hold"},
        rules=[
            {
                "count_key": "total_unresolved_packet_ref_count",
                "stage": "inspect",
                "title": "",
                "recommended_view": "batch_entries",
                "reason_template": "{total_unresolved_packet_ref_count} unresolved packet reference(s) and {batch_count} batch(es) still need readiness review.",
            },
            {
                "count_key": "total_queue_size",
                "stage": "decide",
                "title": "",
                "recommended_view": "batch_entries",
                "reason_template": "{total_queue_size} queued packet review item(s) remain across {case_count} case(s).",
            },
        ],
        default_step={
            "stage": "inspect",
            "title": "",
            "recommended_view": "batch_entries",
            "reason_template": "{total_unresolved_packet_ref_count} unresolved packet reference(s) and {batch_count} batch(es) still need readiness review.",
        },
    )
