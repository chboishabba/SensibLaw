from __future__ import annotations

from dataclasses import dataclass

from src.search_selection.search_selection import SearchQuery, SearchResult
from src.search_selection.search_union import (
    authoritative_order_with_un,
    inject_icc_case_result,
    inject_live_un_result,
    inject_worldbank_result,
    merge_search_results,
    rank_sources,
    union_search_queries,
    canonicalize_multilingual_query,
)


@dataclass(frozen=True)
class DummyResult(SearchResult):
    pass


def test_union_dedups_and_maintains_order() -> None:
    queries = [
        SearchQuery(source_label="uk_legislation", query_text="act"),
        SearchQuery(source_label="eu_legislation", query_text="act"),
        SearchQuery(source_label="uk_legislation", query_text="act"),
    ]
    unioned = union_search_queries(queries)
    assert len(unioned) == 2
    assert unioned[0].source_label == "uk_legislation"


def test_rank_sources_by_authority_order() -> None:
    queries = [
        SearchQuery(source_label="courtlistener", query_text="case"),
        SearchQuery(source_label="legislation", query_text="statute"),
    ]
    authority_order = ["legislation", "courtlistener"]
    ranked = rank_sources(queries, authority_order=authority_order)
    assert ranked[0].source_label == "legislation"


def test_rank_sources_prefers_language_preference() -> None:
    queries = [
        SearchQuery(source_label="legislation", query_text="tax", language="fr"),
        SearchQuery(source_label="legislation", query_text="tax", language="en"),
    ]
    ranked = rank_sources(queries, authority_order=["legislation"], language_preference=("en", "fr"))
    assert ranked[0].language == "en"


def test_merge_respects_priority_and_limit() -> None:
    results = [
        DummyResult(
            source_label="uk_legislation",
            query_text="act",
            metadata={"priority_score": 5},
        ),
        DummyResult(
            source_label="eu_legislation",
            query_text="directive",
            metadata={"priority_score": 2},
        ),
    ]
    ranked = merge_search_results(results, limit=1)
    assert len(ranked) == 1
    assert ranked[0].source_label == "uk_legislation"


def test_merge_preference_falls_back_to_multilingual_placeholder() -> None:
    results = [
        DummyResult(
            source_label="un_treaty",
            query_text="resolution",
            metadata={"priority_score": 3, "language": "fr"},
        ),
        DummyResult(
            source_label="uk_legislation",
            query_text="act",
            metadata={"priority_score": 3, "language": "en"},
        ),
    ]
    ranked = merge_search_results(results, language_preference=("en", "fr"))
    assert ranked[0].source_label == "uk_legislation"


def test_authoritative_order_with_un_adds_placeholder() -> None:
    base = ["legislation", "eur_legislation"]
    ordered = authoritative_order_with_un(base)
    assert ordered[-1] == "undocs"


def test_inject_live_un_result_appends_unique_entry() -> None:
    initial = [
        DummyResult(source_label="uk_legislation", query_text="act", metadata={"priority_score": 1})
    ]
    live = DummyResult(source_label="undocs", query_text="resolution", metadata={"priority_score": 2})
    combined = inject_live_un_result(initial, live_result=live)
    assert live in combined
    assert combined[0].source_label == "uk_legislation"


def test_inject_worldbank_result_reuses_live_union() -> None:
    initial = [
        DummyResult(source_label="uk_legislation", query_text="act", metadata={"priority_score": 1})
    ]
    live = DummyResult(source_label="worldbank", query_text="report", metadata={"priority_score": 2})
    combined = inject_worldbank_result(initial, live_result=live)
    assert live in combined


def test_inject_icc_case_result_reuses_live_union() -> None:
    initial = [
        DummyResult(source_label="uk_legislation", query_text="act", metadata={"priority_score": 1})
    ]
    live = DummyResult(source_label="icc_case", query_text="judgment", metadata={"priority_score": 2})
    combined = inject_icc_case_result(initial, live_result=live)
    assert live in combined


def test_canonicalize_multilingual_query_fixes_language() -> None:
    query = SearchQuery(source_label="other", query_text="act", language="es")
    canonical = canonicalize_multilingual_query(query)
    assert canonical.source_label == "eur_legislation"
