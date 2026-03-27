from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Set, Tuple

import json
from pathlib import Path

from src.sources.austlii_sino import AustLiiSearchAdapter, SinoQuery
from src.sources.austlii_sino_parse import AustLiiSearchHit, parse_sino_search_html
from src.citations.normalize import (
    CitationKey,
    austlii_case_url_from_mnc,
    jade_content_ext_url,
    normalize_mnc,
)


@dataclass(frozen=True)
class CitationRef:
    raw_text: str
    offset: int
    key: Optional[CitationKey] = None


@dataclass(frozen=True)
class FetchPlan:
    source: str  # "jade" | "austlii" | "austlii_search"
    url: Optional[str] = None
    query: Optional[str] = None
    vc: Optional[str] = None
    citation: Optional[CitationKey] = None


_NEUTRAL_PATTERN = re.compile(r"\[\d{4}\]\s+[A-Z][A-Z0-9]+\s+\d+")


def extract_citations(text: str) -> List[CitationRef]:
    """Extract neutral citations from text. No inference, no expansion."""

    refs: List[CitationRef] = []
    for match in _NEUTRAL_PATTERN.finditer(text or ""):
        raw = match.group(0)
        key = normalize_mnc(raw)
        refs.append(CitationRef(raw_text=raw, offset=match.start(), key=key))
    return refs


def resolve_citation(
    ref: CitationRef,
    *,
    store_has: Callable[[CitationKey], bool],
    prefer_jade: bool = True,
    austlii_state: str = "cth",
) -> Optional[FetchPlan]:
    """Return a FetchPlan for a citation or None if unresolved/already ingested."""

    if ref.key is None:
        return None
    if store_has(ref.key):
        return None

    if prefer_jade:
        return FetchPlan(source="jade", url=jade_content_ext_url(ref.key), citation=ref.key)

    return FetchPlan(
        source="austlii",
        url=austlii_case_url_from_mnc(ref.key, state=austlii_state),
        citation=ref.key,
    )


def resolve_citation_candidates(
    ref: CitationRef,
    *,
    store_has: Callable[[CitationKey], bool],
    prefer_jade: bool = True,
    austlii_state: str = "cth",
) -> List[FetchPlan]:
    if ref.key is None:
        return []
    if store_has(ref.key):
        return []

    candidates: List[FetchPlan] = []
    if prefer_jade:
        candidates.append(FetchPlan(source="jade", url=jade_content_ext_url(ref.key), citation=ref.key))
    candidates.append(
        FetchPlan(
            source="austlii",
            url=austlii_case_url_from_mnc(ref.key, state=austlii_state),
            citation=ref.key,
        )
    )
    return candidates


def _hit_matches_citation(ref: CitationRef, hit: AustLiiSearchHit) -> bool:
    if ref.key is None:
        return False
    for candidate in (hit.citation, hit.title, hit.url):
        key = normalize_mnc(candidate or "")
        if key == ref.key:
            return True
    return False


def resolve_austlii_search_plan(
    ref: CitationRef,
    *,
    search_adapter: AustLiiSearchAdapter | None = None,
    vc: str = "/au",
    results: int = 10,
    method: str = "phrase",
) -> Optional[FetchPlan]:
    if ref.key is None:
        return None

    adapter = search_adapter or AustLiiSearchAdapter()
    html = adapter.search(SinoQuery(meta=vc, query=ref.raw_text, results=results, method=method))
    hits = parse_sino_search_html(html)
    for hit in hits:
        if _hit_matches_citation(ref, hit):
            return FetchPlan(
                source="austlii_search",
                url=hit.url,
                query=ref.raw_text,
                vc=vc,
                citation=ref.key,
            )
    return None


def follow_citations_bounded(
    *,
    seed_text: str,
    fetch: Callable[[FetchPlan], bytes],
    ingest: Callable[[bytes, Optional[CitationKey], Optional[int]], Tuple[int, str]],
    store_has: Callable[[CitationKey], bool],
    max_depth: int = 1,
    max_new_docs: int = 5,
    unresolved: Optional[List[dict]] = None,
    unresolved_path: Optional[Path] = None,
    prefer_jade: bool = True,
    austlii_state: str = "cth",
    resolve_search: Optional[Callable[[CitationRef], Optional[FetchPlan]]] = None,
) -> Set[int]:
    """Bounded citation-following ingestion.

    - seed_text: text of the seed document.
    - fetch(plan): returns raw bytes for the cited document.
    - ingest(bytes, citation_key, parent_doc_id): returns (doc_id, extracted_text).
    - store_has(key): returns True if citation already ingested.
    """

    queue: List[Tuple[str, int, Optional[int]]] = [(seed_text, 0, None)]
    ingested: Set[int] = set()
    unresolved_list = unresolved if unresolved is not None else []

    while queue and len(ingested) < max_new_docs:
        text, depth, parent_id = queue.pop(0)
        if depth > max_depth:
            continue

        refs = extract_citations(text)
        for ref in refs:
            if len(ingested) >= max_new_docs:
                break

            candidates = resolve_citation_candidates(
                ref,
                store_has=store_has,
                prefer_jade=prefer_jade,
                austlii_state=austlii_state,
            )
            if not candidates:
                reason = "already_ingested" if ref.key and store_has(ref.key) else "unresolved"
                if unresolved is not None or unresolved_path:
                    unresolved_list.append(
                        {
                            "citation": ref.raw_text,
                            "offset": ref.offset,
                            "reason": reason,
                            "citing_doc": parent_id,
                        }
                    )
                continue

            cited_bytes = None
            chosen_plan: Optional[FetchPlan] = None
            last_error: Optional[Exception] = None
            for plan in candidates:
                try:
                    cited_bytes = fetch(plan)
                    chosen_plan = plan
                    break
                except Exception as exc:
                    last_error = exc

            if cited_bytes is None or chosen_plan is None:
                search_resolver = resolve_search or resolve_austlii_search_plan
                search_plan = search_resolver(ref)
                if search_plan is None:
                    if unresolved is not None or unresolved_path:
                        unresolved_list.append(
                            {
                                "citation": ref.raw_text,
                                "offset": ref.offset,
                                "reason": "fetch_failed",
                                "citing_doc": parent_id,
                                "attempted_sources": [plan.source for plan in candidates],
                                "error": str(last_error) if last_error else None,
                            }
                        )
                    continue
                try:
                    cited_bytes = fetch(search_plan)
                    chosen_plan = search_plan
                except Exception as exc:
                    if unresolved is not None or unresolved_path:
                        unresolved_list.append(
                            {
                                "citation": ref.raw_text,
                                "offset": ref.offset,
                                "reason": "search_fetch_failed",
                                "citing_doc": parent_id,
                                "attempted_sources": [plan.source for plan in candidates] + [search_plan.source],
                                "error": str(exc),
                            }
                        )
                    continue

            doc_id, cited_text = ingest(cited_bytes, chosen_plan.citation, parent_id)
            if doc_id in ingested:
                continue
            ingested.add(doc_id)

            if depth + 1 <= max_depth and cited_text:
                queue.append((cited_text, depth + 1, doc_id))

    if unresolved_path:
        unresolved_path.parent.mkdir(parents=True, exist_ok=True)
        unresolved_path.write_text(
            json.dumps(unresolved_list, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return ingested
