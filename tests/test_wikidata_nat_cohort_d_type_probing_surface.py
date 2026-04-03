import json
from pathlib import Path

from src.ontology.wikidata_nat_cohort_d_review import (
    WIKIDATA_NAT_COHORT_D_TYPE_PROBING_SURFACE_SCHEMA_VERSION,
    build_wikidata_nat_cohort_d_type_probing_surface,
)


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_type_probing_surface_fixture_is_fail_closed_and_non_executing() -> None:
    payload = _load_fixture("wikidata_nat_cohort_d_type_probing_surface_20260402.json")

    assert payload["schema_version"] == WIKIDATA_NAT_COHORT_D_TYPE_PROBING_SURFACE_SCHEMA_VERSION
    assert payload["artifact_status"] == "review_only_ready"
    assert payload["lane_id"] == "wikidata_nat_cohort_d_no_instance_of"
    assert payload["current_gate_id"] == "review_first_typing_resolution_scan"
    assert payload["next_gate_id"] == "type_probing_scan_review_only"
    assert payload["governance"]["automation_allowed"] is False
    assert payload["governance"]["can_execute_edits"] is False
    assert payload["governance"]["fail_closed"] is True
    assert payload["governance"]["promotion_guard"] == "hold"
    assert payload["unresolved_packet_refs"] == []
    assert payload["surface_flags"] == ["missing_instance_of_typing_deficit"]

    qids = [row["review_entity_qid"] for row in payload["probe_rows"]]
    assert qids == ["Q738421", "Q1785637"]
    assert all(row["execution_allowed"] is False for row in payload["probe_rows"])
    assert all(row["cohort_flags"] == ["missing_instance_of_typing_deficit"] for row in payload["probe_rows"])


def test_cohort_d_type_probing_surface_marks_missing_packet_refs_incomplete() -> None:
    review_surface = _load_fixture("wikidata_nat_cohort_d_review_surface_20260402.json")
    one_packet = _load_fixture("wikidata_nat_review_packet_Q738421_sidecar_20260402.json")

    payload = build_wikidata_nat_cohort_d_type_probing_surface(
        cohort_d_review_surface=review_surface,
        packet_payloads=[one_packet],
    )

    assert payload["artifact_status"] == "review_only_incomplete"
    assert payload["unresolved_packet_refs"] == [
        {"review_entity_qid": "Q1785637", "reason": "missing_packet_payload"}
    ]
