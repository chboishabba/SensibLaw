from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class AxisPoint:
    """
    Minimal axis-policy point for timeline/ribbon rendering.

    - `time_bucket`: normalized time coordinate (already bucketed by caller).
    - `account_lane`: account/owner lane (x-axis in 2D fallback).
    - `contact_lane`: contact/interaction lane (z-axis in 3D mode).
    - `point_id`: stable identifier for deterministic collision reporting.
    """

    point_id: str
    time_bucket: str
    account_lane: str
    contact_lane: str


def detect_axis_lane_collisions(points: Iterable[AxisPoint]) -> List[Tuple[AxisPoint, AxisPoint]]:
    """
    Detect collisions where two points claim the same time/account/contact slot.
    """
    by_slot: Dict[Tuple[str, str, str], AxisPoint] = {}
    collisions: List[Tuple[AxisPoint, AxisPoint]] = []
    for point in points:
        slot = (point.time_bucket, point.account_lane, point.contact_lane)
        first = by_slot.get(slot)
        if first is None:
            by_slot[slot] = point
            continue
        collisions.append((first, point))
    return collisions


def deterministic_2d_fallback(points: Iterable[AxisPoint]) -> List[dict]:
    """
    Deterministic projection when 3D contact/account semantics are too dense.

    Policy:
    - y-axis remains time (`time_bucket` lexical sort).
    - x-axis is account lane index (stable lexical sort).
    - contact lane remains attached as metadata (not dropped).
    """
    pts = list(points)
    account_order = {lane: idx for idx, lane in enumerate(sorted({p.account_lane for p in pts}))}
    time_order = {bucket: idx for idx, bucket in enumerate(sorted({p.time_bucket for p in pts}))}

    projected = [
        {
            "point_id": p.point_id,
            "x_account_lane_index": account_order[p.account_lane],
            "y_time_index": time_order[p.time_bucket],
            "account_lane": p.account_lane,
            "contact_lane": p.contact_lane,
            "time_bucket": p.time_bucket,
        }
        for p in sorted(
            pts,
            key=lambda p: (time_order[p.time_bucket], account_order[p.account_lane], p.contact_lane, p.point_id),
        )
    ]
    return projected
