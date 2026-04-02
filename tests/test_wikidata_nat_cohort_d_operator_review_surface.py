import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_d_review import (
    WIKIDATA_NAT_COHORT_D_OPERATOR_REVIEW_SURFACE_SCHEMA_VERSION,
    build_wikidata_nat_cohort_d_operator_review_surface,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_operator_review_surface_fixture_is_non_executing_queue() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_operator_review_surface_20260402.json")

    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_D_OPERATOR_REVIEW_SURFACE_SCHEMA_VERSION
    assert payload["readiness"] == "review_queue_ready"
    assert payload["queue_size"] == 2
    assert payload["unresolved_packet_ref_count"] == 0
    assert payload["required_checklist"] == [
        "confirm_absence_of_instance_of",
        "collect_typing_candidates",
        "record_reconcile_or_hold_decision",
    ]
    assert payload["governance"]["automation_allowed"] is False
    assert payload["governance"]["can_execute_edits"] is False
    assert payload["governance"]["promotion_guard"] == "hold"
    assert all(row["execution_allowed"] is False for row in payload["operator_queue"])


def test_cohort_d_operator_review_surface_becomes_incomplete_when_probe_surface_has_unresolved_refs() -> None:
    probe = _load_fixture("wikidata_nat_cohort_d_type_probing_surface_20260402.json")
    probe["unresolved_packet_refs"] = [{"review_entity_qid": "Q1785637", "reason": "missing_packet_payload"}]

    payload = build_wikidata_nat_cohort_d_operator_review_surface(type_probing_surface=probe)

    assert payload["readiness"] == "review_queue_incomplete"
    assert payload["unresolved_packet_ref_count"] == 1
