from __future__ import annotations

from typing import Iterable, Mapping


def build_summary_index(summaries: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Aggregate a sequence of Cohort E summaries into a reusable index."""
    index: dict[str, int] = {"total_batch_runs": 0, "total_agreements": 0, "total_disagreements": 0}
    axis_counts: dict[str, int] = {}
    lane_id: str | None = None
    for summary in summaries:
        index["total_batch_runs"] += 1
        index["total_agreements"] += int(summary.get("agreement_rows", 0))
        index["total_disagreements"] += int(summary.get("disagreement_rows", 0))
        if lane_id is None:
            lane_id = summary.get("lane_id")
        for axis, count in summary.get("axis_disagreement_counts", {}).items():
            axis_counts[axis] = axis_counts.get(axis, 0) + int(count)
    index["axis_disagreement_counts"] = axis_counts
    if lane_id is not None:
        index["lane_id"] = lane_id
    return index


__all__ = ["build_summary_index"]
