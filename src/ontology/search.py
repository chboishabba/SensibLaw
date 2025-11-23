"""Utilities for filtering ontology lookup results."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, Mapping


Candidate = Mapping[str, object]


def _confidence_score(query: str, label: str, *, aliases: Iterable[str] | None = None) -> float:
    """Return a similarity score between ``query`` and a candidate label.

    Scores are calculated using :class:`difflib.SequenceMatcher` across the
    primary ``label`` and any provided ``aliases``.  Empty inputs return
    ``0.0`` to keep filtering predictable for borderline cases.
    """

    query_norm = query.strip().lower()
    if not query_norm:
        return 0.0

    options = [label, *(aliases or [])]
    best = 0.0
    for option in options:
        option_norm = str(option).strip().lower()
        if not option_norm:
            continue
        score = SequenceMatcher(None, query_norm, option_norm).ratio()
        if score > best:
            best = score
    return best


def filter_candidates(
    query: str,
    candidates: Iterable[Candidate],
    *,
    threshold: float = 0.0,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Rank and filter ontology candidates for a query.

    Each candidate is expected to expose a ``label`` field and may include
    optional ``aliases`` for alternate spellings.  Candidates with a
    confidence score below ``threshold`` are discarded and the remainder are
    sorted by descending score and label for deterministic output.
    """

    ranked: list[dict[str, object]] = []
    for candidate in candidates:
        label = str(candidate.get("label", ""))
        aliases = candidate.get("aliases")
        alias_values = (
            aliases
            if isinstance(aliases, Iterable) and not isinstance(aliases, (str, bytes))
            else None
        )
        score = _confidence_score(query, label, aliases=alias_values)
        if score < threshold:
            continue
        enriched = dict(candidate)
        enriched["score"] = score
        ranked.append(enriched)

    ranked.sort(key=lambda item: (-item["score"], str(item.get("label", ""))))
    if limit is not None:
        return ranked[:limit]
    return ranked


__all__ = ["filter_candidates", "_confidence_score"]
