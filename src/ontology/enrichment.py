from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence
from urllib.parse import quote

import requests

PROVIDER_NAMES = ("wikidata", "dbpedia")


@dataclass(frozen=True)
class LookupCandidate:
    """Candidate match returned from an external provider."""

    provider: str
    external_id: str
    label: str
    description: str | None = None
    url: str | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


def _wikidata_lookup(query: str, *, limit: int, timeout: float) -> list[LookupCandidate]:
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": query,
        "limit": limit,
    }
    try:
        response = requests.get(
            "https://www.wikidata.org/w/api.php",
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network guard
        print(f"[wikidata] lookup failed for '{query}': {exc}", file=sys.stderr)
        return []

    payload = response.json()
    candidates: list[LookupCandidate] = []
    for item in payload.get("search", [])[:limit]:
        external_id = str(item.get("id") or "")
        candidates.append(
            LookupCandidate(
                provider="wikidata",
                external_id=external_id,
                label=str(item.get("label") or query),
                description=item.get("description"),
                url=(
                    f"https://www.wikidata.org/wiki/{external_id}"
                    if external_id
                    else None
                ),
                score=(
                    float(item.get("score", 0))
                    if item.get("score") is not None
                    else None
                ),
            )
        )
    return candidates


def _dbpedia_lookup(query: str, *, limit: int, timeout: float) -> list[LookupCandidate]:
    headers = {"Accept": "application/json"}
    url = (
        "https://lookup.dbpedia.org/api/search"
        f"?query={quote(query)}&maxResults={limit}&format=json"
    )
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network guard
        print(f"[dbpedia] lookup failed for '{query}': {exc}", file=sys.stderr)
        return []

    payload = response.json()
    candidates: list[LookupCandidate] = []
    for item in payload.get("docs", [])[:limit]:
        identifier = (item.get("resource", []) or [""])[0]
        candidates.append(
            LookupCandidate(
                provider="dbpedia",
                external_id=identifier,
                label=(item.get("label", []) or [query])[0],
                description=(item.get("comment", []) or [None])[0],
                url=identifier or None,
                score=None,
            )
        )
    return candidates


PROVIDER_LOOKUPS = {
    "wikidata": _wikidata_lookup,
    "dbpedia": _dbpedia_lookup,
}


def batch_lookup(
    queries: Iterable[str | None],
    providers: Sequence[str],
    *,
    limit: int = 5,
    timeout: float = 10.0,
) -> dict[str, list[LookupCandidate]]:
    """Lookup a collection of ``queries`` across external ``providers``."""

    normalized_providers = [provider.lower() for provider in providers if provider]
    results: dict[str, list[LookupCandidate]] = {provider: [] for provider in normalized_providers}
    for provider in normalized_providers:
        lookup = PROVIDER_LOOKUPS.get(provider)
        if lookup is None:
            print(f"Skipping unsupported provider: {provider}", file=sys.stderr)
            continue
        seen: set[str] = set()
        for query in queries:
            if not query:
                continue
            cleaned = str(query).strip()
            if not cleaned:
                continue
            for candidate in lookup(cleaned, limit=limit, timeout=timeout):
                if candidate.external_id in seen:
                    continue
                seen.add(candidate.external_id)
                results[provider].append(candidate)
                if len(results[provider]) >= limit:
                    break
            if len(results[provider]) >= limit:
                break
    return results


def fetch_rows(
    connection: sqlite3.Connection, table: str, columns: Sequence[str]
) -> list[Mapping[str, object]]:
    cursor = connection.execute(f"SELECT {', '.join(columns)} FROM {table}")
    return [dict(row) for row in cursor.fetchall()]


def upsert_external_ref(
    connection: sqlite3.Connection,
    *,
    table: str,
    entity_id: int,
    provider: str,
    candidate: LookupCandidate,
) -> None:
    if table == "concepts":
        target_table = "concept_external_refs"
        id_column = "concept_id"
    elif table == "actors":
        target_table = "actor_external_refs"
        id_column = "actor_id"
    else:  # pragma: no cover - guarded by CLI choices
        raise ValueError(f"Unsupported table for upsert: {table}")
    connection.execute(
        f"""
        INSERT OR IGNORE INTO {target_table} ({id_column}, provider, external_id, external_url, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_id, provider, candidate.external_id, candidate.url, candidate.description),
    )


def serialise_candidates(
    entity: Mapping[str, object],
    candidates: Mapping[str, list[LookupCandidate]],
) -> dict[str, object]:
    return {
        **entity,
        "candidates": {
            provider: [candidate.to_dict() for candidate in matches]
            for provider, matches in candidates.items()
        },
    }


def write_candidates(payload: list[Mapping[str, object]], out_path: Path | None) -> None:
    serialised = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path is None:
        print(serialised)
    else:
        Path(out_path).write_text(serialised, encoding="utf-8")


__all__ = [
    "LookupCandidate",
    "PROVIDER_NAMES",
    "batch_lookup",
    "fetch_rows",
    "serialise_candidates",
    "upsert_external_ref",
    "write_candidates",
]
