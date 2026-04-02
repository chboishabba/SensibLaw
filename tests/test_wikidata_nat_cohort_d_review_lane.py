import json
from pathlib import Path


def _load_cohort_d_review_surface_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_d_review_surface_20260402.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_cohort_d_review_surface_is_fail_closed_and_review_first() -> None:
    payload = _load_cohort_d_review_surface_fixture()

    assert payload["schema_version"] == "sl.wikidata_nat_cohort_d_review_surface.v0_1"
    assert payload["lane_id"] == "wikidata_nat_cohort_d_no_instance_of"
    assert payload["cohort_id"] == "cohort_d_no_instance_of"
    assert payload["cohort_bucket_summary"]["sandbox_claimed_statement_count"] == 1395

    governance = payload["governance"]
    assert governance["bucket_type"] == "typing_deficit_review_only"
    assert governance["automation_allowed"] is False
    assert governance["can_execute_edits"] is False
    assert governance["promotion_guard"] == "hold"
    assert governance["fail_closed"] is True

    review_surface = payload["review_surface"]
    assert review_surface["current_gate_id"] == "review_first_typing_resolution_scan"
    assert review_surface["current_gate_status"] == "open_review"
    assert review_surface["next_gate_id"] == "type_probing_scan_review_only"
    assert review_surface["progress_claim"] == "reviewable_surface_only"


def test_cohort_d_review_surface_references_disjoint_probe_packets() -> None:
    payload = _load_cohort_d_review_surface_fixture()
    packet_refs = payload["candidate_packet_refs"]

    assert len(packet_refs) == 2
    assert packet_refs[0]["review_entity_qid"] == "Q738421"
    assert packet_refs[1]["review_entity_qid"] == "Q1785637"
    assert all(ref["packet_role"] == "cohort_d_typing_deficit_probe" for ref in packet_refs)
    assert "no_direct_migration_execution" in payload["non_claims"]
