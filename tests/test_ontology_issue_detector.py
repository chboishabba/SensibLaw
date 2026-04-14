import json
from pathlib import Path

from src.ontology.ontology_issue_detector import detect_ontology_issues


def _load_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_detect_ontology_issues_from_type_probing_surface_emits_bounded_unsupported_is_a_chain_issues() -> None:
    probe = _load_fixture("wikidata_nat_cohort_d_type_probing_surface_20260402.json")

    issues = detect_ontology_issues(type_probing_surface=probe)

    assert [issue.issue_type for issue in issues] == [
        "unsupported_is_a_chain",
        "unsupported_is_a_chain",
    ]
    assert [issue.subject_ids for issue in issues] == [("Q1785637",), ("Q738421",)]
    assert all(issue.scope == "wikidata_ontology" for issue in issues)
    assert all(issue.status == "review_required" for issue in issues)
    assert all(issue.confidence_band == "medium" for issue in issues)
    assert all(issue.reason_codes == ("wikidata_missing_edge",) for issue in issues)
    assert issues[0].evidence_refs == (
        "review-packet:f451ac11e012b114",
        "split://Q1785637|P5991",
        "wikidata:Q1785637",
    )
    assert issues[0].details["smallest_typing_check"] == "resolve_page_open_questions"
    assert issues[0].details["required_reviewer_checks"] == [
        "confirm_absence_of_instance_of",
        "collect_typing_candidates",
        "record_reconcile_or_hold_decision",
    ]


def test_detect_ontology_issues_from_operator_review_surface_uses_queue_shape() -> None:
    review_surface = _load_fixture("wikidata_nat_cohort_d_operator_review_surface_20260402.json")

    issues = detect_ontology_issues(operator_review_surface=review_surface)

    assert len(issues) == 2
    assert issues[0].issue_id == "issue:wikidata:Q1785637:unsupported_is_a_chain"
    assert issues[0].details["packet_status"] is None
    assert issues[0].details["required_reviewer_checks"] == [
        "confirm_absence_of_instance_of",
        "collect_typing_candidates",
        "record_reconcile_or_hold_decision",
    ]


def test_detect_ontology_issues_returns_empty_for_non_wikidata_sources() -> None:
    probe = _load_fixture("wikidata_nat_cohort_d_type_probing_surface_20260402.json")

    issues = detect_ontology_issues(type_probing_surface=probe, source_system="gwb")

    assert issues == []
