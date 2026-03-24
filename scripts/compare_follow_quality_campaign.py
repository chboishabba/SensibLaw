#!/usr/bin/env python3
"""Compare follow-quality campaign aggregate summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_FOLLOW_BUCKET_KEYS = [
    "list_like_follow",
    "low_information_gain_follow",
    "stable_follow",
    "thin_follow",
]


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_payload(source: str) -> dict[str, Any]:
    candidate = Path(source)
    if candidate.is_file():
        return _load(str(candidate))
    if candidate.is_dir():
        aggregate = candidate / "aggregate_summary.json"
        if aggregate.is_file():
            return _load(str(aggregate))
    raise SystemExit(f"not a valid campaign aggregate file or directory: {source}")


def _metric(payload: dict[str, Any], key: str) -> float | None:
    if key in (payload.get("average_metrics") or {}):
        node = payload["average_metrics"][key]
        if isinstance(node, (int, float)):
            return float(node)
        return None

    node: Any = payload
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, (int, float)):
        return float(node)
    if node is None:
        return None
    return None


def _print_delta(label: str, before: float | None, after: float | None) -> None:
    if before is None or after is None:
        print(f"{label}: before={before} after={after} delta=NA")
        return
    delta = round(after - before, 6)
    print(f"{label}: before={before} after={after} delta={delta}")


def _print_comparison(before: dict[str, Any], after: dict[str, Any]) -> None:
    print(f"report_count before={before.get('report_count', 'NA')} after={after.get('report_count', 'NA')}")

    metrics = [
        "average_follow_yield_metrics.follow_target_quality_score",
        "average_follow_yield_metrics.followed_link_relevance_score",
        "average_follow_yield_metrics.follow_yield_score",
        "average_best_path_metrics.best_path_score",
        "average_best_path_metrics.best_path_vs_avg_gap",
        "average_two_hop_metrics.hop_quality_decay",
    ]
    for key in metrics:
        _print_delta(key, _metric(before, key), _metric(after, key))

    before_buckets = before.get("follow_failure_bucket_counts") or {}
    after_buckets = after.get("follow_failure_bucket_counts") or {}
    print("follow failure buckets:")
    for bucket in _FOLLOW_BUCKET_KEYS:
        b = int(before_buckets.get(bucket, 0))
        a = int(after_buckets.get(bucket, 0))
        print(f"  {bucket}: before={b} after={a} delta={a - b}")

    before_spec = before.get("specificity_reason_counts") or {}
    after_spec = after.get("specificity_reason_counts") or {}
    print("specificity reasons:")
    for reason in sorted(set(before_spec) | set(after_spec)):
        b = int(before_spec.get(reason, 0))
        a = int(after_spec.get(reason, 0))
        print(f"  {reason}: before={b} after={a} delta={a - b}")

    before_info = before.get("information_gain_reason_counts") or {}
    after_info = after.get("information_gain_reason_counts") or {}
    print("information_gain reasons:")
    for reason in sorted(set(before_info) | set(after_info)):
        b = int(before_info.get(reason, 0))
        a = int(after_info.get(reason, 0))
        print(f"  {reason}: before={b} after={a} delta={a - b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two follow-quality campaign aggregate outputs.")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    args = parser.parse_args(argv)

    before = _resolve_payload(args.before)
    after = _resolve_payload(args.after)
    _print_comparison(before, after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
