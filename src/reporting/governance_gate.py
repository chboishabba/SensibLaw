"""Governance gate supporting reporting across the shared normalized substrate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


READY_DECISIONS = {"promote", "audit"}


@dataclass(frozen=True, slots=True)
class LaneGovernanceSnapshot:
    """Minimal snapshot for a lane contributing to the shared governance gate."""

    lane_name: str
    promotion_gate_decision: str
    authority_receipt_count: int
    follow_queue_open: int
    unresolved_pressure_status: str | None = None


@dataclass(frozen=True, slots=True)
class MultiLaneGateSummary:
    decision: str
    ready_lane_count: int
    total_authority_receipts: int
    open_follow_conjectures: int
    ready_lanes: tuple[str, ...]
    gating_thresholds: dict[str, int]


def evaluate_multi_lane_gate(
    snapshots: Iterable[LaneGovernanceSnapshot],
    *,
    required_ready_lanes: int = 2,
    min_total_receipts: int = 5,
    max_open_conjectures: int = 10,
) -> MultiLaneGateSummary:
    """Evaluate the bounded multi-lane governance gate over shared substrate outputs.

    The gate is ready to move forward only when a minimum number of lanes have a
    promotion decision that is not `abstain`, there is enough receipt evidence,
    and open follow conjectures remain within bounded limits.
    """

    snapshots = tuple(snapshots)
    ready_lanes = []
    total_authority_receipts = 0
    open_follow_conjectures = 0

    for snapshot in snapshots:
        total_authority_receipts += snapshot.authority_receipt_count
        open_follow_conjectures += snapshot.follow_queue_open
        if snapshot.promotion_gate_decision in READY_DECISIONS:
            ready_lanes.append(snapshot.lane_name)

    decision = "hold"
    if (
        len(ready_lanes) >= required_ready_lanes
        and total_authority_receipts >= min_total_receipts
        and open_follow_conjectures <= max_open_conjectures
    ):
        decision = "go"

    return MultiLaneGateSummary(
        decision=decision,
        ready_lane_count=len(ready_lanes),
        total_authority_receipts=total_authority_receipts,
        open_follow_conjectures=open_follow_conjectures,
        ready_lanes=tuple(ready_lanes),
        gating_thresholds={
            "required_ready_lanes": required_ready_lanes,
            "min_total_receipts": min_total_receipts,
            "max_open_conjectures": max_open_conjectures,
        },
    )
