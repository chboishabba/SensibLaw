from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .search_selection import SearchQuery, SearchResult


@dataclass(frozen=True)
class SourceUnionKey:
    name: str
    branch: str


def _language_rank(language: str, preference: Sequence[str]) -> int:
    normalized = str(language or "").strip().lower()
    for index, value in enumerate(preference):
        if normalized == value.lower():
            return index
    return len(preference)


def merge_search_results(
    results: Iterable[SearchResult], *, limit: int | None = None, language_preference: Sequence[str] = ("en",)
) -> list[SearchResult]:
    sorted_results = sorted(
        results,
        key=lambda result: (
            -int(result.metadata.get("priority_score") or 0),
            _language_rank(result.metadata.get("language") or "en", language_preference),
            result.metadata.get("resolution_mode"),
            result.source_label,
        ),
    )
    if limit is None:
        return sorted_results
    return sorted_results[:limit]


def union_search_queries(
    queries: Sequence[SearchQuery], *, distinct: bool = True
) -> list[SearchQuery]:
    seen: set[str] = set()
    output: list[SearchQuery] = []
    for query in queries:
        query = canonicalize_multilingual_query(query)
        key = f"{query.source_label}:{query.query_text}"
        if distinct and key in seen:
            continue
        seen.add(key)
        output.append(query)
    return output


LANGUAGE_SOURCE_MAP: Mapping[str, str] = {
    "es": "eur_legislation",
    "fr": "undocs",
    "ar": "undocs",
}


def canonicalize_multilingual_query(query: SearchQuery) -> SearchQuery:
    canonical = LANGUAGE_SOURCE_MAP.get(query.language, query.source_label)
    return SearchQuery(source_label=canonical, query_text=query.query_text, language=query.language)


def rank_sources(
    queries: Iterable[SearchQuery], *, authority_order: Iterable[str], language_preference: Sequence[str] = ("en",)
) -> list[SearchQuery]:
    authority_rank = {name: index for index, name in enumerate(authority_order)}
    return sorted(
        queries,
        key=lambda query: (
            authority_rank.get(str(query.source_label) or "", len(authority_order)),
            _language_rank(query.language, language_preference),
        ),
    )


def authoritative_order_with_un(authority_order: Iterable[str]) -> list[str]:
    base = list(authority_order)
    if "undocs" not in base:
        base.append("undocs")
    return base


def inject_live_un_result(
    results: Iterable[SearchResult], *, live_result: SearchResult
) -> list[SearchResult]:
    payload = list(results)
    if live_result not in payload:
        payload.append(live_result)
    return payload


def inject_worldbank_result(
    results: Iterable[SearchResult], *, live_result: SearchResult
) -> list[SearchResult]:
    payload = inject_live_un_result(results, live_result=live_result)
    return payload


def inject_icc_case_result(
    results: Iterable[SearchResult], *, live_result: SearchResult
) -> list[SearchResult]:
    payload = inject_live_un_result(results, live_result=live_result)
    return payload
