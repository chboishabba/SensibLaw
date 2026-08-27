"""Aggregate timeout-surviving document timing samples without acceptance promotion.

Partial timing is execution diagnostics only. Intervals are attributed to the
*previous* checkpoint coordinate because each interval spans from that observed
state to the next sample. Concurrent owner occupancies are never summed into a
synthetic wall clock and partial parser/post-parser values are never acceptance
eligible.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


PARTIAL_TIMING_REPORT_SCHEMA_VERSION = "sensiblaw.partial-execution-timing-report.v0_1"


@dataclass(frozen=True, slots=True)
class PartialTimingBucket:
    stage: str
    current_kernel: str
    interval_count: int
    wall_ns: int
    process_cpu_ns: int
    peak_rss_bytes: int
    peak_process_tree_rss_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "current_kernel": self.current_kernel,
            "interval_count": self.interval_count,
            "wall_ns": self.wall_ns,
            "process_cpu_ns": self.process_cpu_ns,
            "peak_rss_bytes": self.peak_rss_bytes,
            "peak_process_tree_rss_bytes": self.peak_process_tree_rss_bytes,
        }


def _timing(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("partial_timing") or {}
    return value if isinstance(value, Mapping) else {}


def _resources(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("resources") or {}
    return value if isinstance(value, Mapping) else {}


def aggregate_partial_timing(
    samples: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return diagnostic owner intervals from ordered durable checkpoints.

    Each interval is assigned to the coordinate observed at its *start* sample.
    The first sample contributes no attributable interval because no earlier
    checkpoint establishes what owned time before it. The final open interval at
    process termination is likewise unknown unless an external terminator emits a
    final sample; this is reported explicitly rather than inferred.
    """

    rows = [dict(row) for row in samples]
    rows.sort(
        key=lambda row: (
            str(row.get("document_ref") or ""),
            int(_timing(row).get("observed_monotonic_ns") or 0),
        )
    )
    totals: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {
            "interval_count": 0,
            "wall_ns": 0,
            "process_cpu_ns": 0,
            "peak_rss_bytes": 0,
            "peak_process_tree_rss_bytes": 0,
        }
    )
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_document[str(row.get("document_ref") or "unknown")].append(row)

    unattributed_prefix_documents = 0
    open_tail_documents = 0
    for document_rows in by_document.values():
        if document_rows:
            unattributed_prefix_documents += 1
            open_tail_documents += 1
        for previous, current in zip(document_rows, document_rows[1:]):
            previous_timing = _timing(previous)
            current_timing = _timing(current)
            previous_monotonic = int(previous_timing.get("observed_monotonic_ns") or 0)
            current_monotonic = int(current_timing.get("observed_monotonic_ns") or 0)
            previous_cpu = int(previous_timing.get("process_cpu_elapsed_ns") or 0)
            current_cpu = int(current_timing.get("process_cpu_elapsed_ns") or 0)
            wall_ns = max(0, current_monotonic - previous_monotonic)
            process_cpu_ns = max(0, current_cpu - previous_cpu)
            stage = str(previous.get("active_stage") or previous_timing.get("stage") or "unknown")
            kernel = str(
                previous.get("current_kernel")
                or previous_timing.get("current_kernel")
                or "unknown"
            )
            bucket = totals[(stage, kernel)]
            bucket["interval_count"] += 1
            bucket["wall_ns"] += wall_ns
            bucket["process_cpu_ns"] += process_cpu_ns
            resources = _resources(previous)
            bucket["peak_rss_bytes"] = max(
                bucket["peak_rss_bytes"], int(resources.get("rss_bytes") or 0)
            )
            bucket["peak_process_tree_rss_bytes"] = max(
                bucket["peak_process_tree_rss_bytes"],
                int(resources.get("process_tree_rss_bytes") or 0),
            )

    buckets = [
        PartialTimingBucket(stage, kernel, **values).to_dict()
        for (stage, kernel), values in totals.items()
    ]
    buckets.sort(key=lambda row: (-int(row["wall_ns"]), row["stage"], row["current_kernel"]))
    return {
        "schema_version": PARTIAL_TIMING_REPORT_SCHEMA_VERSION,
        "state": "partial_diagnostic_only",
        "acceptance_eligible": False,
        "parser_relative_gate_eligible": False,
        "semantic_authority_effect": "none",
        "sample_count": len(rows),
        "document_count": len(by_document),
        "buckets": buckets,
        "unattributed_prefix_documents": unattributed_prefix_documents,
        "open_tail_documents": open_tail_documents,
        "concurrent_bucket_wall_ns_must_not_be_summed": True,
    }


__all__ = [
    "PARTIAL_TIMING_REPORT_SCHEMA_VERSION",
    "PartialTimingBucket",
    "aggregate_partial_timing",
]
