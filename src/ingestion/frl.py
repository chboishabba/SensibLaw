"""Federal Register of Legislation (FRL) API adapter.

The FRL exposes a JSON based API which can be used to retrieve metadata
about Australian legislative instruments.  The aim of this module is not
to provide a full featured client but rather a tiny helper used in unit
tests.  The functions convert API responses into simple ``nodes`` and
``edges`` lists representing a graph of Acts and their sections.

The API is accessed with :mod:`urllib.request` so that no third‑party
packages are required.  Tests can supply pre‑recorded JSON payloads via
function arguments which avoids the need for network access.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Tuple, Optional

from .cache import fetch_json

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Section:
    number: str
    title: str | None = None
    body: str | None = None


@dataclass
class Act:
    """Representation of an Act as returned by the FRL API."""

    identifier: str
    title: str
    point_in_time: Optional[str] = None
    sections: List[Section] | None = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_json(url: str) -> Dict[str, object]:
    """Fetch JSON from ``url`` using the cache."""

    return fetch_json(url)


def _acts_to_graph(acts: Iterable[Act]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Convert a sequence of :class:`Act` objects into graph ``nodes`` and
    ``edges`` representing the relationship between Acts and their sections."""

    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []

    for act in acts:
        nodes.append({
            "id": act.identifier,
            "type": "act",
            "title": act.title,
            "point_in_time": act.point_in_time,
        })
        for sec in act.sections or []:
            nodes.append({
                "id": f"{act.identifier}:{sec.number}",
                "type": "section",
                "number": sec.number,
                "title": sec.title,
            })
            edges.append({
                "from": act.identifier,
                "to": f"{act.identifier}:{sec.number}",
                "type": "has_section",
            })
    return nodes, edges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_acts(api_url: str, *, data: Optional[Dict[str, object]] = None) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Fetch Acts from the FRL API and return graph data.

    Parameters
    ----------
    api_url:
        Base URL of the FRL endpoint returning a collection of Acts.  The
        live API uses URLs such as
        ``"https://www.legislation.gov.au/federalregister/json/Acts"``.
    data:
        Optional pre-parsed JSON structure.  Supplying this allows tests to
        operate without network access.

    Returns
    -------
    ``(nodes, edges)``
        ``nodes`` contains Act and section nodes while ``edges`` expresses
        the ``"has_section"`` relationship.
    """

    if data is None:
        data = _get_json(api_url)  # pragma: no cover - network

    # The JSON structure returned by the API typically contains a ``results``
    # list, each item of which represents an Act.  We only rely on a small
    # subset of the fields so the parser is intentionally tolerant of missing
    # keys.
    acts: List[Act] = []
    term_definitions: Dict[str, str] = {}
    for item in data.get("results", []):
        ident = item.get("id") or item.get("identifier") or item.get("title")
        if not ident:
            continue
        title = item.get("title") or ident
        pit = (
            item.get("point_in_time")
            or item.get("pointInTime")
            or item.get("PointInTime")
        )
        sections_data = item.get("sections") or item.get("Sections") or []
        sections: List[Section] = []
        for s in sections_data:
            num = s.get("number") or s.get("id")
            if not num:
                continue
            num = str(num)
            body = s.get("body")
            sections.append(Section(number=num, title=s.get("title"), body=body))
            if body:
                for m in re.finditer(r'"([^"\n]+)"\s+means', body):
                    term_definitions[m.group(1).lower()] = f"{ident}:{num}"
        acts.append(Act(identifier=str(ident), title=title, point_in_time=pit, sections=sections))

    nodes, edges = _acts_to_graph(acts)

    # ------------------------------------------------------------------
    # Parse bodies for cross-references and uses of defined terms
    # ------------------------------------------------------------------
    for act in acts:
        sec_map = {sec.number: f"{act.identifier}:{sec.number}" for sec in act.sections or []}
        for sec in act.sections or []:
            body = sec.body or ""
            from_id = f"{act.identifier}:{sec.number}"

            # Cross references to other sections within the same Act
            for m in re.finditer(r"section\s+([0-9A-Za-z]+)", body, flags=re.IGNORECASE):
                ref = m.group(1)
                to_id = sec_map.get(ref)
                if to_id:
                    edges.append({
                        "from": from_id,
                        "to": to_id,
                        "type": "cites",
                        "text": m.group(0),
                    })

            # Usage of defined terms
            for term, def_id in term_definitions.items():
                if def_id == from_id:
                    continue
                m = re.search(rf"\b{re.escape(term)}\b", body, flags=re.IGNORECASE)
                if m:
                    edges.append({
                        "from": def_id,
                        "to": from_id,
                        "type": "defines",
                        "text": m.group(0),
                    })

    return nodes, edges


__all__ = ["Act", "Section", "fetch_acts"]
