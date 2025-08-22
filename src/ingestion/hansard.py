from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable


@dataclass
class Debate:
    """Simple representation of a parliamentary debate."""

    identifier: str
    text: str
    date: str | None = None


_CITATION_RE = re.compile(r"([A-Z][a-z]*(?: [A-Z][a-z]*)* Act \d{4})")


def normalize_text(text: str) -> str:
    """Return ``text`` normalised for spacing.

    Multiple whitespace characters are collapsed to a single space and
    leading/trailing whitespace is stripped.  This is intentionally simple
    but sufficient for unit tests where stable hashing across runs is
    important.
    """

    return re.sub(r"\s+", " ", text).strip()


def extract_citations(text: str) -> List[str]:
    """Extract crude Act citations from ``text``.

    The implementation uses a lightweight regular expression that matches
    phrases such as ``"Crimes Act 1914"``.  It is not intended to be
    exhaustive but provides deterministic behaviour for the tests.
    """

    return _CITATION_RE.findall(text)


def fetch_debates(raw_debates: Iterable[Dict[str, str]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Convert raw debate data into graph ``nodes`` and ``edges``.

    Parameters
    ----------
    raw_debates:
        Iterable of dictionaries each containing at least ``id`` and ``text``
        keys.  Optional metadata such as ``date`` may also be supplied.

    Returns
    -------
    ``(nodes, edges)``
        ``nodes`` contains a node for each debate and any cited Acts while
        ``edges`` expresses the ``"cites"`` relationship between debates and
        Acts.
    """

    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    seen_citations: set[str] = set()

    for item in raw_debates:
        ident = item.get("id") or item.get("identifier")
        if ident is None:
            continue
        body = normalize_text(item.get("text", ""))
        citations = extract_citations(body)
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        metadata = {
            "date": item.get("date"),
            "hash": sha,
            "citations": citations,
        }
        nodes.append({
            "id": ident,
            "type": "debate",
            "body": body,
            "metadata": metadata,
        })
        for cit in citations:
            if cit not in seen_citations:
                nodes.append({"id": cit, "type": "act"})
                seen_citations.add(cit)
            edges.append({"from": ident, "to": cit, "type": "cites"})
    return nodes, edges


__all__ = ["Debate", "normalize_text", "extract_citations", "fetch_debates"]
