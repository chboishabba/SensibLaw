from __future__ import annotations

from typing import Any, Mapping


def _coerce_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    revid = snapshot.get("revid")
    return {
        "title": snapshot.get("title") if isinstance(snapshot.get("title"), str) else None,
        "wiki": snapshot.get("wiki") if isinstance(snapshot.get("wiki"), str) else None,
        "revid": int(revid) if isinstance(revid, (int, float)) or (isinstance(revid, str) and revid.strip().isdigit()) else None,
        "source_url": snapshot.get("source_url") if isinstance(snapshot.get("source_url"), str) else None,
    }


def _coerce_anchor(anchor: Mapping[str, Any] | None) -> dict[str, Any]:
    anchor = anchor if isinstance(anchor, Mapping) else {}
    precision = str(anchor.get("precision") or "").strip().lower()
    if precision not in {"year", "month", "day"}:
        precision = "year"

    def _to_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
        return None

    year = _to_int_or_none(anchor.get("year")) or 0
    month = _to_int_or_none(anchor.get("month"))
    day = _to_int_or_none(anchor.get("day"))
    return {
        "year": year,
        "month": month,
        "day": day,
        "precision": precision,
        "text": str(anchor.get("text") or ""),
        "kind": str(anchor.get("kind") or ""),
    }


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, int, int, str]:
    anchor = event.get("anchor")
    anchor_obj = anchor if isinstance(anchor, Mapping) else {}
    year = int(anchor_obj.get("year") or 0) or 9999
    month = anchor_obj.get("month")
    day = anchor_obj.get("day")
    return (
        year,
        int(month) if isinstance(month, int) else 99,
        int(day) if isinstance(day, int) else 99,
        str(event.get("event_id") or ""),
    )


def build_timeline_view_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _coerce_snapshot(payload.get("snapshot") if isinstance(payload, Mapping) else {})
    events_raw = payload.get("events") if isinstance(payload, Mapping) else []
    out_events: list[dict[str, Any]] = []
    if isinstance(events_raw, list):
        for event in events_raw:
            if not isinstance(event, Mapping):
                continue
            event_id = str(event.get("event_id") or "").strip()
            text = str(event.get("text") or "").strip()
            if not event_id or not text:
                continue
            section = str(event.get("section") or "").strip() or "(unknown)"
            links_raw = event.get("links")
            links = [str(item) for item in links_raw if str(item)] if isinstance(links_raw, list) else []
            out_events.append(
                {
                    "event_id": event_id,
                    "anchor": _coerce_anchor(event.get("anchor") if isinstance(event.get("anchor"), Mapping) else {}),
                    "section": section,
                    "text": text,
                    "links": links,
                }
            )
    out_events.sort(key=_event_sort_key)
    return {"snapshot": snapshot, "events": out_events}
