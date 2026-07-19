"""Bounded Wikimedia candidate providers for the external PNF enrichment phase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence, TextIO

import requests

from src.ontology.external_enrichment import (
    EnrichmentResult,
    ExternalCandidate,
    ExternalLookupDemand,
    build_external_candidate_set,
    canonical_sha256,
    group_lookup_demands,
)
from src.runtime.progress import ProgressEvent, emit_progress


WIKIDATA_PROVIDER_REF = "wikidata-wbsearchentities:v0_1"
WIKTIONARY_PROVIDER_REF = "wiktionary-action-api:v0_1"


class ResponseLike(Protocol):
    status_code: int

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class SessionLike(Protocol):
    def get(self, url: str, **kwargs: Any) -> ResponseLike: ...


@dataclass(frozen=True)
class ProviderLookup:
    lookup_key: str
    provider_ref: str
    candidates: tuple[ExternalCandidate, ...]
    snapshot_refs: tuple[str, ...]
    request_receipts: tuple[Mapping[str, Any], ...]


class LookupProvider(Protocol):
    provider_ref: str
    demand_kind: str

    def lookup_batch(
        self,
        demands: Sequence[ExternalLookupDemand],
        *,
        request_budget: int,
        progress_stream: TextIO,
    ) -> Mapping[str, ProviderLookup]: ...


@dataclass(frozen=True)
class CacheEntry:
    lookup: ProviderLookup
    expires_at: datetime


class MemoryLookupCache:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], CacheEntry] = {}

    def get(self, provider_ref: str, lookup_key: str, *, now: datetime) -> ProviderLookup | None:
        row = self._rows.get((provider_ref, lookup_key))
        if row is None or row.expires_at <= now:
            return None
        return row.lookup

    def put(
        self,
        lookup: ProviderLookup,
        *,
        now: datetime,
        ttl: timedelta,
    ) -> None:
        self._rows[(lookup.provider_ref, lookup.lookup_key)] = CacheEntry(
            lookup=lookup,
            expires_at=now + ttl,
        )


def _snapshot_ref(provider_ref: str, payload: Any) -> str:
    return "provider-snapshot:" + canonical_sha256(
        {"provider_ref": provider_ref, "payload": payload}
    )


def _request_receipt(
    *,
    provider_ref: str,
    operation: str,
    request_key: str,
    status: str,
    payload: Any | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    response_sha = canonical_sha256(payload) if payload is not None else None
    receipt = {
        "provider_ref": provider_ref,
        "operation": operation,
        "request_key": request_key,
        "status": status,
        "response_sha256": response_sha,
        "detail": detail,
        "authority": "transport_receipt_only",
    }
    receipt["request_receipt_ref"] = "provider-request:" + canonical_sha256(receipt)
    return {key: value for key, value in receipt.items() if value not in (None, "")}


def _chunks(values: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), max(size, 1)):
        yield values[start : start + max(size, 1)]


class WikidataProvider:
    provider_ref = WIKIDATA_PROVIDER_REF
    demand_kind = "entity_identity"
    endpoint = "https://www.wikidata.org/w/api.php"

    def __init__(
        self,
        *,
        session: SessionLike | None = None,
        candidate_limit: int = 5,
        timeout_seconds: float = 15.0,
        user_agent: str = "SensibLaw-ITIR/0.1 (candidate-only Wikidata enrichment)",
    ) -> None:
        self.session = session or requests.Session()
        self.candidate_limit = candidate_limit
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def _get(self, params: Mapping[str, Any]) -> Any:
        response = self.session.get(
            self.endpoint,
            params=dict(params),
            timeout=self.timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        return response.json()

    def lookup_batch(
        self,
        demands: Sequence[ExternalLookupDemand],
        *,
        request_budget: int,
        progress_stream: TextIO,
    ) -> Mapping[str, ProviderLookup]:
        by_key = {demand.lookup_key: demand for demand in demands}
        search_rows: dict[str, list[Mapping[str, Any]]] = {}
        receipts: dict[str, list[Mapping[str, Any]]] = {key: [] for key in by_key}
        requests_used = 0
        for index, (lookup_key, demand) in enumerate(sorted(by_key.items()), start=1):
            if requests_used >= request_budget:
                receipts[lookup_key].append(
                    _request_receipt(
                        provider_ref=self.provider_ref,
                        operation="wbsearchentities",
                        request_key=lookup_key,
                        status="budget_exhausted",
                    )
                )
                search_rows[lookup_key] = []
                continue
            try:
                payload = self._get(
                    {
                        "action": "wbsearchentities",
                        "format": "json",
                        "language": demand.language,
                        "uselang": demand.language,
                        "type": "item",
                        "search": demand.surface,
                        "limit": self.candidate_limit,
                    }
                )
                requests_used += 1
                rows = payload.get("search", []) if isinstance(payload, Mapping) else []
                search_rows[lookup_key] = [
                    dict(row) for row in rows[: self.candidate_limit] if isinstance(row, Mapping)
                ]
                receipts[lookup_key].append(
                    _request_receipt(
                        provider_ref=self.provider_ref,
                        operation="wbsearchentities",
                        request_key=lookup_key,
                        status="completed",
                        payload=payload,
                    )
                )
            except (requests.RequestException, ValueError) as error:
                requests_used += 1
                search_rows[lookup_key] = []
                receipts[lookup_key].append(
                    _request_receipt(
                        provider_ref=self.provider_ref,
                        operation="wbsearchentities",
                        request_key=lookup_key,
                        status="failed",
                        detail=str(error),
                    )
                )
            emit_progress(
                ProgressEvent(
                    phase="wikidata_lookup",
                    state="searched",
                    completed=index,
                    total=len(by_key),
                    subject_ref=demand.surface,
                ),
                stream=progress_stream,
            )

        all_ids = sorted(
            {
                str(row.get("id") or "")
                for rows in search_rows.values()
                for row in rows
                if str(row.get("id") or "")
            }
        )
        entity_rows: dict[str, Mapping[str, Any]] = {}
        entity_snapshots: dict[str, str] = {}
        for chunk in _chunks(all_ids, 50):
            if requests_used >= request_budget:
                break
            request_key = canonical_sha256(
                {"provider": self.provider_ref, "operation": "wbgetentities", "ids": list(chunk)}
            )
            try:
                payload = self._get(
                    {
                        "action": "wbgetentities",
                        "format": "json",
                        "ids": "|".join(chunk),
                        "languages": "en",
                        "props": "labels|aliases|descriptions|claims",
                    }
                )
                requests_used += 1
                snapshot = _snapshot_ref(self.provider_ref, payload)
                raw_entities = payload.get("entities", {}) if isinstance(payload, Mapping) else {}
                if isinstance(raw_entities, Mapping):
                    for qid, row in raw_entities.items():
                        if isinstance(row, Mapping):
                            entity_rows[str(qid)] = row
                            entity_snapshots[str(qid)] = snapshot
                batch_receipt = _request_receipt(
                    provider_ref=self.provider_ref,
                    operation="wbgetentities",
                    request_key=request_key,
                    status="completed",
                    payload=payload,
                )
            except (requests.RequestException, ValueError) as error:
                requests_used += 1
                batch_receipt = _request_receipt(
                    provider_ref=self.provider_ref,
                    operation="wbgetentities",
                    request_key=request_key,
                    status="failed",
                    detail=str(error),
                )
            for lookup_key, rows in search_rows.items():
                if any(str(row.get("id") or "") in chunk for row in rows):
                    receipts[lookup_key].append(batch_receipt)

        output: dict[str, ProviderLookup] = {}
        for lookup_key, demand in by_key.items():
            candidates: list[ExternalCandidate] = []
            snapshots: set[str] = set()
            for search_row in search_rows.get(lookup_key, []):
                qid = str(search_row.get("id") or "")
                if not qid:
                    continue
                entity = entity_rows.get(qid, {})
                labels = entity.get("labels", {}) if isinstance(entity, Mapping) else {}
                descriptions = entity.get("descriptions", {}) if isinstance(entity, Mapping) else {}
                aliases = entity.get("aliases", {}) if isinstance(entity, Mapping) else {}
                claims = entity.get("claims", {}) if isinstance(entity, Mapping) else {}
                label = str(
                    ((labels.get("en") or {}).get("value") if isinstance(labels, Mapping) else None)
                    or search_row.get("label")
                    or demand.surface
                )
                description = str(
                    ((descriptions.get("en") or {}).get("value") if isinstance(descriptions, Mapping) else None)
                    or search_row.get("description")
                    or ""
                ) or None
                alias_rows = aliases.get("en", []) if isinstance(aliases, Mapping) else []
                alias_values = tuple(
                    sorted(
                        {
                            str(row.get("value") or "")
                            for row in alias_rows
                            if isinstance(row, Mapping) and str(row.get("value") or "")
                        }
                    )
                )
                type_refs: set[str] = set()
                if isinstance(claims, Mapping):
                    for property_ref in ("P31", "P279"):
                        for claim in claims.get(property_ref, []) or []:
                            try:
                                value = claim["mainsnak"]["datavalue"]["value"]
                                if isinstance(value, Mapping) and value.get("id"):
                                    type_refs.add(str(value["id"]))
                            except (KeyError, TypeError):
                                continue
                snapshot_ref = entity_snapshots.get(qid)
                if snapshot_ref:
                    snapshots.add(snapshot_ref)
                raw_score = search_row.get("score")
                candidates.append(
                    ExternalCandidate(
                        provider_ref=self.provider_ref,
                        external_id=qid,
                        label=label,
                        description=description,
                        aliases=alias_values,
                        type_refs=tuple(sorted(type_refs)),
                        candidate_kind="wikidata_item",
                        source_url=f"https://www.wikidata.org/wiki/{qid}",
                        provider_score=(float(raw_score) if raw_score is not None else None),
                        snapshot_ref=snapshot_ref,
                        evidence_refs=tuple(
                            str(row["request_receipt_ref"]) for row in receipts[lookup_key]
                        ),
                    )
                )
            output[lookup_key] = ProviderLookup(
                lookup_key=lookup_key,
                provider_ref=self.provider_ref,
                candidates=tuple(candidates),
                snapshot_refs=tuple(sorted(snapshots)),
                request_receipts=tuple(receipts[lookup_key]),
            )
        return output


class WiktionaryProvider:
    provider_ref = WIKTIONARY_PROVIDER_REF
    demand_kind = "lexical_sense"

    def __init__(
        self,
        *,
        session: SessionLike | None = None,
        timeout_seconds: float = 15.0,
        user_agent: str = "SensibLaw-ITIR/0.1 (candidate-only Wiktionary enrichment)",
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def lookup_batch(
        self,
        demands: Sequence[ExternalLookupDemand],
        *,
        request_budget: int,
        progress_stream: TextIO,
    ) -> Mapping[str, ProviderLookup]:
        by_key = {demand.lookup_key: demand for demand in demands}
        output: dict[str, ProviderLookup] = {}
        if not by_key or request_budget <= 0:
            return output
        grouped_by_language: dict[str, list[ExternalLookupDemand]] = {}
        for demand in by_key.values():
            grouped_by_language.setdefault(demand.language, []).append(demand)
        requests_used = 0
        for language, language_demands in sorted(grouped_by_language.items()):
            for demand_chunk in _chunks(
                [demand.lookup_key for demand in language_demands], 50
            ):
                selected = [by_key[key] for key in demand_chunk]
                if requests_used >= request_budget:
                    for demand in selected:
                        receipt = _request_receipt(
                            provider_ref=self.provider_ref,
                            operation="query_extracts",
                            request_key=demand.lookup_key,
                            status="budget_exhausted",
                        )
                        output[demand.lookup_key] = ProviderLookup(
                            demand.lookup_key,
                            self.provider_ref,
                            (),
                            (),
                            (receipt,),
                        )
                    continue
                endpoint = f"https://{language}.wiktionary.org/w/api.php"
                request_key = canonical_sha256(
                    {
                        "provider": self.provider_ref,
                        "language": language,
                        "titles": [demand.surface for demand in selected],
                    }
                )
                try:
                    response = self.session.get(
                        endpoint,
                        params={
                            "action": "query",
                            "format": "json",
                            "redirects": 1,
                            "prop": "extracts",
                            "explaintext": 1,
                            "exintro": 1,
                            "titles": "|".join(demand.surface for demand in selected),
                        },
                        timeout=self.timeout_seconds,
                        headers={"User-Agent": self.user_agent},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    requests_used += 1
                    receipt = _request_receipt(
                        provider_ref=self.provider_ref,
                        operation="query_extracts",
                        request_key=request_key,
                        status="completed",
                        payload=payload,
                    )
                    snapshot = _snapshot_ref(self.provider_ref, payload)
                    query = payload.get("query", {}) if isinstance(payload, Mapping) else {}
                    pages = query.get("pages", {}) if isinstance(query, Mapping) else {}
                    page_rows = [row for row in pages.values() if isinstance(row, Mapping)] if isinstance(pages, Mapping) else []
                except (requests.RequestException, ValueError) as error:
                    requests_used += 1
                    receipt = _request_receipt(
                        provider_ref=self.provider_ref,
                        operation="query_extracts",
                        request_key=request_key,
                        status="failed",
                        detail=str(error),
                    )
                    snapshot = ""
                    page_rows = []
                for demand in selected:
                    normalized = demand.surface.casefold()
                    matches = [
                        row
                        for row in page_rows
                        if str(row.get("title") or "").casefold() == normalized
                        and not row.get("missing")
                    ]
                    candidates = tuple(
                        ExternalCandidate(
                            provider_ref=self.provider_ref,
                            external_id=str(row.get("pageid") or row.get("title") or demand.surface),
                            label=str(row.get("title") or demand.surface),
                            description=str(row.get("extract") or "") or None,
                            candidate_kind="wiktionary_lexical_entry",
                            source_url=f"https://{language}.wiktionary.org/wiki/{str(row.get('title') or demand.surface).replace(' ', '_')}",
                            snapshot_ref=snapshot or None,
                            evidence_refs=(str(receipt["request_receipt_ref"]),),
                        )
                        for row in matches
                    )
                    output[demand.lookup_key] = ProviderLookup(
                        demand.lookup_key,
                        self.provider_ref,
                        candidates,
                        ((snapshot,) if snapshot else ()),
                        (receipt,),
                    )
                    emit_progress(
                        ProgressEvent(
                            phase="wiktionary_lookup",
                            state="searched",
                            completed=len(output),
                            total=len(by_key),
                            subject_ref=demand.surface,
                        ),
                        stream=progress_stream,
                    )
        return output


class WikimediaMicrobatchRunner:
    def __init__(
        self,
        providers: Sequence[LookupProvider],
        *,
        cache: MemoryLookupCache | None = None,
        microbatch_size: int = 16,
        request_budget_per_provider: int = 64,
        cache_ttl: timedelta = timedelta(days=30),
        negative_cache_ttl: timedelta = timedelta(days=1),
        minimum_batch_interval_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if microbatch_size <= 0 or request_budget_per_provider < 0:
            raise ValueError("microbatch and request budget must be non-negative")
        self.providers = tuple(providers)
        self.cache = cache or MemoryLookupCache()
        self.microbatch_size = microbatch_size
        self.request_budget_per_provider = request_budget_per_provider
        self.cache_ttl = cache_ttl
        self.negative_cache_ttl = negative_cache_ttl
        self.minimum_batch_interval_seconds = minimum_batch_interval_seconds
        self.sleep = sleep

    def run(
        self,
        demands: Iterable[ExternalLookupDemand],
        *,
        progress_stream: TextIO | None = None,
        now: datetime | None = None,
    ) -> tuple[EnrichmentResult, ...]:
        stream = progress_stream or sys.stderr
        active_now = now or datetime.now(timezone.utc)
        demand_rows = tuple(demands)
        grouped = group_lookup_demands(demand_rows)
        representative = {key: rows[0] for key, rows in grouped}
        lookups: dict[tuple[str, str], ProviderLookup] = {}
        cache_states: dict[tuple[str, str], str] = {}
        for provider in self.providers:
            applicable = [
                demand
                for demand in representative.values()
                if demand.demand_kind == provider.demand_kind
            ]
            misses: list[ExternalLookupDemand] = []
            for demand in applicable:
                cached = self.cache.get(provider.provider_ref, demand.lookup_key, now=active_now)
                key = (provider.provider_ref, demand.lookup_key)
                if cached is not None:
                    lookups[key] = cached
                    cache_states[key] = "fresh_cache_hit"
                else:
                    misses.append(demand)
            remaining_budget = self.request_budget_per_provider
            for start in range(0, len(misses), self.microbatch_size):
                batch = misses[start : start + self.microbatch_size]
                batch_rows = provider.lookup_batch(
                    batch,
                    request_budget=remaining_budget,
                    progress_stream=stream,
                )
                used = sum(
                    1
                    for lookup in batch_rows.values()
                    for receipt in lookup.request_receipts
                    if receipt.get("status") in {"completed", "failed"}
                )
                remaining_budget = max(remaining_budget - used, 0)
                for demand in batch:
                    lookup = batch_rows.get(
                        demand.lookup_key,
                        ProviderLookup(
                            demand.lookup_key,
                            provider.provider_ref,
                            (),
                            (),
                            (
                                _request_receipt(
                                    provider_ref=provider.provider_ref,
                                    operation="lookup_batch",
                                    request_key=demand.lookup_key,
                                    status="no_result",
                                ),
                            ),
                        ),
                    )
                    key = (provider.provider_ref, demand.lookup_key)
                    lookups[key] = lookup
                    cache_states[key] = "fresh"
                    self.cache.put(
                        lookup,
                        now=active_now,
                        ttl=(self.cache_ttl if lookup.candidates else self.negative_cache_ttl),
                    )
                if self.minimum_batch_interval_seconds > 0 and start + self.microbatch_size < len(misses):
                    self.sleep(self.minimum_batch_interval_seconds)

        results: list[EnrichmentResult] = []
        for demand in demand_rows:
            candidate_sets = []
            pressure_receipts = []
            request_receipts: list[Mapping[str, Any]] = []
            states: list[str] = []
            for provider in self.providers:
                if demand.demand_kind != provider.demand_kind:
                    continue
                lookup = lookups.get((provider.provider_ref, demand.lookup_key))
                if lookup is None:
                    continue
                candidate_set, pressure = build_external_candidate_set(
                    demand,
                    provider_ref=provider.provider_ref,
                    candidates=lookup.candidates,
                    snapshot_refs=lookup.snapshot_refs,
                )
                candidate_sets.append(candidate_set)
                pressure_receipts.append(pressure)
                request_receipts.extend(lookup.request_receipts)
                states.append(cache_states.get((provider.provider_ref, demand.lookup_key), "fresh"))
            results.append(
                EnrichmentResult(
                    demand=demand,
                    candidate_sets=tuple(candidate_sets),
                    pressure_receipts=tuple(pressure_receipts),
                    request_receipts=tuple(request_receipts),
                    cache_state=(states[0] if states and len(set(states)) == 1 else "mixed"),
                )
            )
        return tuple(results)


__all__ = [
    "CacheEntry",
    "LookupProvider",
    "MemoryLookupCache",
    "ProviderLookup",
    "WIKIDATA_PROVIDER_REF",
    "WIKTIONARY_PROVIDER_REF",
    "WikidataProvider",
    "WikimediaMicrobatchRunner",
    "WiktionaryProvider",
]
