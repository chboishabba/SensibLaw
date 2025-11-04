from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from src.models.provision import RuleReference


@dataclass
class Debate:
    """Simple representation of a parliamentary debate."""

    identifier: str
    text: str
    date: str | None = None


_ACT_TITLE_RE = r"[A-Z][a-z]*(?: [A-Z][a-z]*)* Act \d{4}"
_MARKER_RE = r"(?:s|ss|section|sections)\s*\d+[A-Za-z]*|Part\s+\d+[A-Za-z]*"
_CITATION_RE = re.compile(
    (
        r"(?:(?P<prefix>(?i:{marker}))(?:\s+of\s+the\s+)?)?"
        r"(?P<work>(?-i:{work}))"
        r"(?:\s+(?P<suffix>(?i:{marker})))?"
    ).format(marker=_MARKER_RE, work=_ACT_TITLE_RE),
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Return ``text`` normalised for spacing.

    Multiple whitespace characters are collapsed to a single space and
    leading/trailing whitespace is stripped.  This is intentionally simple
    but sufficient for unit tests where stable hashing across runs is
    important.
    """

    return re.sub(r"\s+", " ", text).strip()


def _classify_marker(marker: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(section, pinpoint)`` extracted from ``marker``."""

    if not marker:
        return None, None
    cleaned = normalize_text(marker)
    lowered = cleaned.lower()
    if lowered.startswith(("s", "ss", "section", "sections")):
        return cleaned, None
    if cleaned:
        return None, cleaned
    return None, None


def extract_citations(text: str) -> List[Dict[str, Optional[str]]]:
    """Extract structured Act citations from ``text``.

    The implementation captures the Act title together with optional
    section/part markers (for example ``"s 223"`` or ``"Part 3"``) so that
    downstream consumers receive normalised metadata.
    """

    citations: List[Dict[str, Optional[str]]] = []
    for match in _CITATION_RE.finditer(text):
        work = normalize_text(match.group("work"))
        section: Optional[str] = None
        pinpoint: Optional[str] = None
        for marker in (match.group("prefix"), match.group("suffix")):
            marker_section, marker_pinpoint = _classify_marker(marker)
            if marker_section and section is None:
                section = marker_section
            if marker_pinpoint and pinpoint is None:
                pinpoint = marker_pinpoint
        citations.append(
            {
                "work": work,
                "section": section,
                "pinpoint": pinpoint,
                "text": normalize_text(match.group(0)),
            }
        )
    return citations


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
        citation_data = extract_citations(body)
        references = [
            RuleReference(
                work=citation.get("work"),
                section=citation.get("section"),
                pinpoint=citation.get("pinpoint"),
                citation_text=citation.get("text"),
            )
            for citation in citation_data
        ]
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        metadata = {
            "date": item.get("date"),
            "hash": sha,
            "citations": [ref.to_dict() for ref in references],
        }
        nodes.append({
            "id": ident,
            "type": "debate",
            "body": body,
            "metadata": metadata,
        })
        for ref in references:
            if not ref.work:
                continue
            if ref.work not in seen_citations:
                nodes.append({"id": ref.work, "type": "act"})
                seen_citations.add(ref.work)
            edges.append({"from": ident, "to": ref.work, "type": "cites"})
    return nodes, edges


__all__ = ["Debate", "normalize_text", "extract_citations", "fetch_debates"]
