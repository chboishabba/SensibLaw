from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.review_geometry.reviewer_packets import (
    build_reviewer_packet,
    summarize_reviewer_packets,
)

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
    return build_reviewer_packet(
        item_id=item_id,
        title=title,
        subtitle=subtitle,
        description=description,
        conjecture_kind=conjecture_kind,
        route_target=route_target,
        resolution_status=resolution_status,
        chips=chips,
        detail_rows=detail_rows,
        extra=extra,
    )


def summarize_follow_queue(queue: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return summarize_reviewer_packets(queue)
