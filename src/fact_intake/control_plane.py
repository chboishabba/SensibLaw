from __future__ import annotations

from typing import Any, Iterable, Mapping

FOLLOW_CONTROL_PLANE_VERSION = "follow.control.v1"


def build_follow_control_plane(
    *,
    source_family: str,
    hint_kind: str,
    receipt_kind: str,
    substrate_kind: str,
    conjecture_kind: str,
    route_targets: Iterable[str] | None = None,
    resolution_statuses: Iterable[str] | None = None,
) -> dict[str, Any]:
    return {
        "version": FOLLOW_CONTROL_PLANE_VERSION,
        "source_family": str(source_family),
        "hint_kind": str(hint_kind),
        "receipt_kind": str(receipt_kind),
        "substrate_kind": str(substrate_kind),
        "conjecture_kind": str(conjecture_kind),
        "route_targets": sorted({str(value) for value in route_targets or [] if str(value).strip()}),
        "resolution_statuses": sorted({str(value) for value in resolution_statuses or [] if str(value).strip()}),
    }


def build_follow_queue_item(
    *,
    item_id: str,
    title: str,
    conjecture_kind: str,
    route_target: str,
    resolution_status: str,
    subtitle: str | None = None,
    description: str | None = None,
    chips: Iterable[str] | None = None,
    detail_rows: Iterable[Mapping[str, Any]] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_details: list[dict[str, str]] = []
    for row in detail_rows or []:
        label = str(row.get("label") or "").strip()
        value = str(row.get("value") or "").strip()
        if label and value:
            normalized_details.append({"label": label, "value": value})
    payload = {
        "item_id": str(item_id),
        "title": str(title),
        "subtitle": str(subtitle).strip() if subtitle else None,
        "description": str(description).strip() if description else None,
        "conjecture_kind": str(conjecture_kind),
        "route_target": str(route_target),
        "resolution_status": str(resolution_status),
        "chips": [str(value) for value in chips or [] if str(value).strip()],
        "detail_rows": normalized_details,
    }
    if extra:
        for key, value in extra.items():
            payload[str(key)] = value
    return payload


def summarize_follow_queue(queue: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    route_target_counts: dict[str, int] = {}
    resolution_status_counts: dict[str, int] = {}
    queue_rows = list(queue)
    for row in queue_rows:
        route_target = str(row.get("route_target") or "manual_review")
        resolution_status = str(row.get("resolution_status") or "open")
        route_target_counts[route_target] = route_target_counts.get(route_target, 0) + 1
        resolution_status_counts[resolution_status] = resolution_status_counts.get(resolution_status, 0) + 1
    return {
        "queue_count": len(queue_rows),
        "route_target_counts": route_target_counts,
        "resolution_status_counts": resolution_status_counts,
    }
