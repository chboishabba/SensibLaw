from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests


@dataclass
class ExternalCandidate:
    provider: str
    external_id: str
    label: str
    description: str | None = None
    external_url: str | None = None
    confidence: float | None = None

    def with_confidence(self, score: float) -> "ExternalCandidate":
        return ExternalCandidate(
            provider=self.provider,
            external_id=self.external_id,
            label=self.label,
            description=self.description,
            external_url=self.external_url,
            confidence=score,
        )


def _extract_dbpedia_id(uri: str) -> str:
    return uri.rsplit("/", maxsplit=1)[-1]


def wikidata_search(term: str, *, limit: int = 10, timeout: float = 10.0) -> list[ExternalCandidate]:
    """Search Wikidata via the public REST API.

    Parameters
    ----------
    term:
        Label or alias to search for.
    limit:
        Maximum number of results to return.
    timeout:
        Timeout in seconds for the HTTP request.
    """

    response = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "search": term,
            "limit": limit,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results: list[ExternalCandidate] = []
    for entry in data.get("search", []):
        results.append(
            ExternalCandidate(
                provider="wikidata",
                external_id=entry.get("id", ""),
                label=entry.get("label", ""),
                description=entry.get("description"),
                external_url=entry.get("concepturi"),
            )
        )
    return results


def dbpedia_search(
    term: str, *, limit: int = 10, timeout: float = 10.0
) -> list[ExternalCandidate]:
    """Search DBpedia using a SPARQL query against labels and aliases."""

    query = f"""
    SELECT ?item ?label ?comment WHERE {{
      ?item rdfs:label ?label .
      FILTER (lang(?label) = 'en').
      FILTER (CONTAINS(LCASE(?label), LCASE('{term}'))).
      OPTIONAL {{ ?item rdfs:comment ?comment . FILTER (lang(?comment) = 'en') }}
    }}
    LIMIT {limit}
    """

    response = requests.get(
        "https://dbpedia.org/sparql",
        params={"query": query, "format": "json"},
        timeout=timeout,
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    data = response.json()
    bindings: Iterable[dict[str, dict[str, str]]] = data.get("results", {}).get("bindings", [])
    results: list[ExternalCandidate] = []
    for binding in bindings:
        uri = binding.get("item", {}).get("value", "")
        label = binding.get("label", {}).get("value", "")
        comment = binding.get("comment", {}).get("value")
        results.append(
            ExternalCandidate(
                provider="dbpedia",
                external_id=_extract_dbpedia_id(uri),
                label=label,
                description=comment,
                external_url=uri,
            )
        )
    return results


def lookup_from_providers(
    term: str,
    *,
    providers: Optional[Iterable[str]] = None,
    limit: int = 10,
    timeout: float = 10.0,
) -> List[ExternalCandidate]:
    """Query configured providers for a label or alias."""

    selected = {provider.lower() for provider in providers} if providers else {"wikidata", "dbpedia"}
    results: list[ExternalCandidate] = []
    if "wikidata" in selected:
        results.extend(wikidata_search(term, limit=limit, timeout=timeout))
    if "dbpedia" in selected:
        results.extend(dbpedia_search(term, limit=limit, timeout=timeout))
    return results
