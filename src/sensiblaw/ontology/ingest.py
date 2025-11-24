from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, List, Mapping

from .clients import ExternalCandidate, lookup_from_providers

# Filtering heuristics derived from documentation on curating external ontology matches.
IRRELEVANT_KEYWORDS = {
    "album",
    "band",
    "film",
    "fictional",
    "metaphor",
    "metaphorical",
    "novel",
    "poem",
    "song",
    "television",
    "video game",
}
GENERIC_LABELS = {"concept", "idea", "notion"}


def _confidence_score(term: str, label: str) -> float:
    return SequenceMatcher(None, term.lower(), label.lower()).ratio()


def filter_candidates(candidates: Iterable[ExternalCandidate], term: str) -> list[ExternalCandidate]:
    """Apply documented filtering rules and attach confidence scores."""

    filtered: list[ExternalCandidate] = []
    for candidate in candidates:
        haystack = f"{candidate.label} {candidate.description or ''}".lower()
        if any(keyword in haystack for keyword in IRRELEVANT_KEYWORDS):
            continue
        if candidate.label.lower() in GENERIC_LABELS:
            continue
        score = _confidence_score(term, candidate.label)
        filtered.append(candidate.with_confidence(score))
    return filtered


def lookup_candidates(
    term: str,
    *,
    providers: Iterable[str] | None = None,
    limit: int = 10,
    timeout: float = 10.0,
) -> list[ExternalCandidate]:
    """Query providers for a term and return filtered candidates."""

    raw = lookup_from_providers(term, providers=providers, limit=limit, timeout=timeout)
    return filter_candidates(raw, term)


def to_reference_payload(candidate: ExternalCandidate, *, target_id: int, kind: str) -> Mapping[str, object]:
    """Render a candidate into a JSON-serialisable payload for persistence."""

    return {
        "kind": kind,
        "target_id": target_id,
        "provider": candidate.provider,
        "external_id": candidate.external_id,
        "external_url": candidate.external_url,
        "notes": candidate.description,
        "confidence": candidate.confidence,
    }


def batch_lookup(
    terms: Iterable[str],
    *,
    providers: Iterable[str] | None = None,
    limit: int = 10,
    timeout: float = 10.0,
) -> List[dict[str, object]]:
    """Lookup candidates for multiple terms and return serialisable payloads."""

    results: list[dict[str, object]] = []
    for term in terms:
        candidates = lookup_candidates(term, providers=providers, limit=limit, timeout=timeout)
        for candidate in candidates:
            results.append(
                {
                    "term": term,
                    "provider": candidate.provider,
                    "external_id": candidate.external_id,
                    "label": candidate.label,
                    "description": candidate.description,
                    "external_url": candidate.external_url,
                    "confidence": candidate.confidence,
                }
            )
    return results
