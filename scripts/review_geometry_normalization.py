from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


NORMALIZED_WORKLOAD_ORDER = [
    "structural_pressure",
    "governance_pressure",
    "linkage_pressure",
    "event_or_time_pressure",
    "evidence_pressure",
    "normalization_pressure",
    "queue_pressure",
]


def _round6(value: float) -> float:
    return round(float(value), 6)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round6(numerator / denominator)


def _count_statuses(
    rows: list[dict[str, Any]],
    *,
    raw_key: str,
    status_map: Mapping[str, str],
) -> dict[str, int]:
    counts = {"accepted": 0, "review_required": 0, "held": 0}
    for row in rows:
        raw_status = str(row.get(raw_key) or "").strip()
        normalized = status_map.get(raw_status)
        if normalized in counts:
            counts[normalized] += 1
    return counts


def _raw_workloads(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("workload_classes")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    single = str(row.get("workload_class") or "").strip()
    return [single] if single else []


def compute_normalized_metrics(
    *,
    artifact_id: str,
    lane_family: str,
    lane_variant: str,
    review_item_rows: list[dict[str, Any]],
    review_item_status_key: str,
    review_item_status_map: Mapping[str, str],
    source_review_rows: list[dict[str, Any]],
    source_status_key: str,
    source_status_map: Mapping[str, str],
    primary_workload_map: Mapping[str, str | None],
    presence_workload_map: Mapping[str, str | None],
    candidate_signal_count: int,
    provisional_queue_row_count: int,
    provisional_bundle_count: int,
) -> dict[str, Any]:
    review_item_status_counts = _count_statuses(
        review_item_rows,
        raw_key=review_item_status_key,
        status_map=review_item_status_map,
    )
    source_status_counts = _count_statuses(
        source_review_rows,
        raw_key=source_status_key,
        status_map=source_status_map,
    )

    primary_counts = {name: 0 for name in NORMALIZED_WORKLOAD_ORDER}
    presence_counts = {name: 0 for name in NORMALIZED_WORKLOAD_ORDER}

    for row in source_review_rows:
        raw_status = str(row.get(source_status_key) or "").strip()
        normalized_status = source_status_map.get(raw_status)
        if normalized_status != "review_required":
            continue

        primary_raw = str(
            row.get("primary_workload_class") or row.get("workload_class") or ""
        ).strip()
        primary_normalized = primary_workload_map.get(primary_raw)
        if primary_normalized in primary_counts:
            primary_counts[primary_normalized] += 1

        for raw_workload in _raw_workloads(row):
            normalized_workload = presence_workload_map.get(raw_workload)
            if normalized_workload in presence_counts:
                presence_counts[normalized_workload] += 1

    dominant_primary_workload = "none"
    for workload_name in NORMALIZED_WORKLOAD_ORDER:
        if primary_counts[workload_name] > primary_counts.get(dominant_primary_workload, 0):
            dominant_primary_workload = workload_name
        elif (
            dominant_primary_workload == "none"
            and primary_counts[workload_name] > 0
        ):
            dominant_primary_workload = workload_name

    review_required_source_count = source_status_counts["review_required"]

    return {
        "artifact_id": artifact_id,
        "lane_family": lane_family,
        "lane_variant": lane_variant,
        "review_item_status_counts": review_item_status_counts,
        "source_status_counts": source_status_counts,
        "primary_workload_counts": primary_counts,
        "workload_presence_counts": presence_counts,
        "dominant_primary_workload": dominant_primary_workload,
        "candidate_signal_count": int(candidate_signal_count),
        "provisional_queue_row_count": int(provisional_queue_row_count),
        "provisional_bundle_count": int(provisional_bundle_count),
        "review_required_source_ratio": _safe_ratio(
            review_required_source_count,
            len(source_review_rows),
        ),
        "candidate_signal_density": _safe_ratio(
            int(candidate_signal_count),
            review_required_source_count,
        ),
        "provisional_row_density": _safe_ratio(
            int(provisional_queue_row_count),
            review_required_source_count,
        ),
        "provisional_bundle_density": _safe_ratio(
            int(provisional_bundle_count),
            review_required_source_count,
        ),
    }


def render_normalized_metrics_markdown(metrics: Mapping[str, Any]) -> list[str]:
    item_status = metrics.get("review_item_status_counts", {})
    source_status = metrics.get("source_status_counts", {})
    primary_counts = metrics.get("primary_workload_counts", {})
    presence_counts = metrics.get("workload_presence_counts", {})
    lines = [
        "## Normalized Metrics",
        "",
        (
            "- Review-item statuses: "
            f"accepted `{item_status.get('accepted', 0)}`, "
            f"review_required `{item_status.get('review_required', 0)}`, "
            f"held `{item_status.get('held', 0)}`"
        ),
        (
            "- Source statuses: "
            f"accepted `{source_status.get('accepted', 0)}`, "
            f"review_required `{source_status.get('review_required', 0)}`, "
            f"held `{source_status.get('held', 0)}`"
        ),
        f"- Dominant primary workload: `{metrics.get('dominant_primary_workload', 'none')}`",
        "- Primary workload counts:",
    ]
    for workload_name in NORMALIZED_WORKLOAD_ORDER:
        lines.append(f"  - `{workload_name}` `{primary_counts.get(workload_name, 0)}`")
    lines.append("- Workload presence counts:")
    for workload_name in NORMALIZED_WORKLOAD_ORDER:
        lines.append(f"  - `{workload_name}` `{presence_counts.get(workload_name, 0)}`")
    lines.extend(
        [
            f"- Review-required source ratio: `{metrics.get('review_required_source_ratio', 0.0):.6f}`",
            f"- Candidate signal count: `{metrics.get('candidate_signal_count', 0)}`",
            f"- Candidate signal density: `{metrics.get('candidate_signal_density', 0.0):.6f}`",
            f"- Provisional queue rows: `{metrics.get('provisional_queue_row_count', 0)}`",
            f"- Provisional row density: `{metrics.get('provisional_row_density', 0.0):.6f}`",
            f"- Provisional bundles: `{metrics.get('provisional_bundle_count', 0)}`",
            f"- Provisional bundle density: `{metrics.get('provisional_bundle_density', 0.0):.6f}`",
        ]
    )
    return lines


def compute_normalized_metrics_from_profile(
    *,
    profile: Mapping[str, Any],
    artifact_id: str,
    lane_family: str,
    lane_variant: str,
    review_item_rows: list[dict[str, Any]],
    source_review_rows: list[dict[str, Any]],
    candidate_signal_count: int,
    provisional_queue_row_count: int,
    provisional_bundle_count: int,
) -> dict[str, Any]:
    return compute_normalized_metrics(
        artifact_id=artifact_id,
        lane_family=lane_family,
        lane_variant=lane_variant,
        review_item_rows=review_item_rows,
        review_item_status_key=str(profile["review_item_status_key"]),
        review_item_status_map=profile["review_item_status_map"],
        source_review_rows=source_review_rows,
        source_status_key=str(profile["source_status_key"]),
        source_status_map=profile["source_status_map"],
        primary_workload_map=profile["primary_workload_map"],
        presence_workload_map=profile["presence_workload_map"],
        candidate_signal_count=candidate_signal_count,
        provisional_queue_row_count=provisional_queue_row_count,
        provisional_bundle_count=provisional_bundle_count,
    )
