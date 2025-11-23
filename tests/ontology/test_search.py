import pytest

from src.ontology.search import _confidence_score, filter_candidates


def test_confidence_score_handles_empty_inputs():
    assert _confidence_score("", "anything") == 0.0
    assert _confidence_score("query", "") == 0.0


def test_confidence_score_prefers_alias_match():
    direct = _confidence_score("permit", "consent")
    via_alias = _confidence_score("permit", "consent", aliases=["permit", "permission"])
    assert via_alias == pytest.approx(1.0, rel=1e-3)
    assert via_alias > direct


def test_filter_candidates_respects_threshold_and_limit():
    candidates = [
        {"id": "a", "label": "Consent"},
        {"id": "b", "label": "Consult", "aliases": ["Consent"]},
        {"id": "c", "label": "Dissent"},
    ]
    results = filter_candidates("consent", candidates, threshold=0.6, limit=2)
    assert [item["id"] for item in results] == ["a", "b"]
    assert all(item["score"] >= 0.6 for item in results)


def test_filter_candidates_discards_non_matching_alias_strings():
    candidates = [
        {"id": "a", "label": "Consent", "aliases": "not a list"},
        {"id": "b", "label": "Consult", "aliases": ["discussion"]},
    ]
    results = filter_candidates("discussion", candidates, threshold=0.5)
    assert [item["id"] for item in results] == ["b"]
