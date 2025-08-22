from __future__ import annotations

"""Utilities for generating chronological event sequences.

This module builds simple timelines from graph data where nodes and edges
may carry ISO formatted ``date`` strings.  Events are derived from the case
node itself and from any edges connected to that case.  Each event retains
any ``citation`` metadata when present.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class TimelineEvent:
    """Representation of a single timeline entry."""

    date: date
    text: str
    citation: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: Any) -> Optional[date]:
    """Best effort conversion of ``value`` to :class:`~datetime.date`.

    ``value`` may be ``None``, a :class:`date`, :class:`datetime` or an ISO
    formatted string.  Invalid strings return ``None``.
    """

    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_timeline(
    nodes: Iterable[Dict[str, Any]],
    edges: Iterable[Dict[str, Any]],
    case_id: str,
) -> List[TimelineEvent]:
    """Derive a chronological list of events for ``case_id``.

    Parameters
    ----------
    nodes, edges:
        Iterable collections describing the graph.  Nodes must provide an
        ``id`` and may include ``title``, ``citation`` and ``date`` fields.
        Edges are expected to provide ``from``/``to`` (or ``source``/``target``),
        ``type`` and optional ``date`` and ``citation`` fields.
    case_id:
        Identifier of the case to build the timeline for.
    """

    node_map: Dict[str, Dict[str, Any]] = {n.get("id"): n for n in nodes}
    events: List[TimelineEvent] = []

    case_node = node_map.get(case_id)
    if case_node:
        d = _parse_date(case_node.get("date"))
        if d:
            citation = case_node.get("citation") or case_node.get("metadata", {}).get(
                "citation"
            )
            text = case_node.get("title") or case_node.get("id")
            events.append(TimelineEvent(d, text, citation))

    for edge in edges:
        src = edge.get("from") or edge.get("source")
        tgt = edge.get("to") or edge.get("target")
        if case_id not in {src, tgt}:
            continue
        d = _parse_date(edge.get("date"))
        if not d:
            continue
        other_id = tgt if src == case_id else src
        other = node_map.get(other_id, {})
        other_label = (
            other.get("title")
            or other.get("metadata", {}).get("label")
            or other_id
        )
        label = edge.get("type", "")
        text = f"{label} {other_label}".strip()
        citation = edge.get("citation") or edge.get("metadata", {}).get("citation")
        events.append(TimelineEvent(d, text, citation))

    events.sort(key=lambda e: e.date)
    return events


def events_to_json(events: List[TimelineEvent]) -> str:
    """Serialise ``events`` to a JSON string."""

    import json

    data = [
        {"date": e.date.isoformat(), "text": e.text, **({"citation": e.citation} if e.citation else {})}
        for e in events
    ]
    return json.dumps(data)


def events_to_svg(events: List[TimelineEvent]) -> str:
    """Render ``events`` as a simple SVG timeline."""

    height = 20 + 20 * len(events)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}">'
    ]
    y = 15
    for ev in events:
        lines.append(
            f'<text x="10" y="{y}">{ev.date.isoformat()} - {ev.text}</text>'
        )
        y += 20
    lines.append("</svg>")
    return "".join(lines)


__all__ = ["TimelineEvent", "build_timeline", "events_to_json", "events_to_svg"]
