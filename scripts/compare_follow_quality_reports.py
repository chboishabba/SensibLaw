#!/usr/bin/env python3
"""Compare two follow-quality report JSON files built from the same manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(summary: dict[str, Any], key: str) -> float | None:
    parts = key.split(".")
    node: Any = summary
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, (int, float)):
        return float(node)
    return None


def _load_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("summary"), dict):
        return payload["summary"]
    return {}


def _load_average_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("average_metrics"), dict):
        return payload["average_metrics"]
    return {}


def _load_counts(payload: dict[str, Any], key: str) -> dict[str, int]:
    summary = _load_summary(payload)
    if isinstance(summary.get(key), dict):
        return {str(k): int(v or 0) for k, v in summary[key].items()}
    fallback = payload.get(key)
    if isinstance(fallback, dict):
        return {str(k): int(v or 0) for k, v in fallback.items()}
    return {}


def _load_metric(payload: dict[str, Any], key: str) -> float | None:
    summary = _load_summary(payload)
    if summary:
        value = _metric(summary, key)
        if value is not None:
            return value
    average_metrics = _load_average_metrics(payload)
    if key in average_metrics:
        value = average_metrics[key]
        return float(value) if isinstance(value, (int, float)) else None
    return None


def build_comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "average_follow_yield_metrics.follow_target_quality_score",
        "average_follow_yield_metrics.followed_link_relevance_score",
        "average_best_path_metrics.best_path_vs_avg_gap",
        "average_two_hop_metrics.hop_quality_decay",
    ]
    metric_deltas = {}
    for key in keys:
        b = _load_metric(before, key)
        a = _load_metric(after, key)
        metric_deltas[key] = {
            "before": b,
            "after": a,
            "delta": round(a - b, 6) if a is not None and b is not None else None,
        }

    before_summary = _load_summary(before)
    after_summary = _load_summary(after)
    before_counts = _load_counts(before, "follow_failure_bucket_counts")
    after_counts = _load_counts(after, "follow_failure_bucket_counts")

    bucket_names = sorted(set(before_counts.keys()) | set(after_counts.keys()))
    bucket_deltas = {}
    for name in bucket_names:
        b = before_counts.get(name, 0)
        a = after_counts.get(name, 0)
        bucket_deltas[name] = {"before": b, "after": a, "delta": a - b}

    before_specificity = _load_counts(before, "specificity_reason_counts")
    after_specificity = _load_counts(after, "specificity_reason_counts")
    reason_names = sorted(set(before_specificity.keys()) | set(after_specificity.keys()))
    specificity_reason_deltas = {}
    for name in reason_names:
        b = before_specificity.get(name, 0)
        a = after_specificity.get(name, 0)
        specificity_reason_deltas[name] = {"before": b, "after": a, "delta": a - b}

    before_info = _load_counts(before, "information_gain_reason_counts")
    after_info = _load_counts(after, "information_gain_reason_counts")
    info_reason_names = sorted(set(before_info.keys()) | set(after_info.keys()))
    information_gain_reason_deltas = {}
    for name in info_reason_names:
        b = before_info.get(name, 0)
        a = after_info.get(name, 0)
        information_gain_reason_deltas[name] = {"before": b, "after": a, "delta": a - b}

    before_pages = {str(page.get("title") or ""): page for page in (before.get("pages") or [])}
    after_pages = {str(page.get("title") or ""): page for page in (after.get("pages") or [])}
    shared_titles = sorted(set(before_pages) & set(after_pages))
    mismatched_titles = sorted((set(before_pages) ^ set(after_pages)))

    page_deltas = []
    for title in shared_titles:
        b_page = before_pages[title]
        a_page = after_pages[title]
        b_quality = (b_page.get("follow_yield_metrics") or {}).get("follow_target_quality_score")
        a_quality = (a_page.get("follow_yield_metrics") or {}).get("follow_target_quality_score")
        b_gap = (b_page.get("best_path_metrics") or {}).get("best_path_vs_avg_gap")
        a_gap = (a_page.get("best_path_metrics") or {}).get("best_path_vs_avg_gap")
        page_deltas.append(
            {
                "title": title,
                "follow_target_quality_delta": round(float(a_quality) - float(b_quality), 6)
                if isinstance(a_quality, (int, float)) and isinstance(b_quality, (int, float))
                else None,
                "best_path_gap_delta": round(float(a_gap) - float(b_gap), 6)
                if isinstance(a_gap, (int, float)) and isinstance(b_gap, (int, float))
                else None,
            }
        )
    page_deltas.sort(
        key=lambda row: (
            row["follow_target_quality_delta"] if row["follow_target_quality_delta"] is not None else -999.0,
            row["best_path_gap_delta"] if row["best_path_gap_delta"] is not None else -999.0,
            row["title"],
        )
    )

    return {
        "before_schema": before.get("schema_version"),
        "after_schema": after.get("schema_version"),
        "shared_page_count": len(shared_titles),
        "mismatched_titles": mismatched_titles,
        "metric_deltas": metric_deltas,
        "bucket_deltas": bucket_deltas,
        "specificity_reason_deltas": specificity_reason_deltas,
        "information_gain_reason_deltas": information_gain_reason_deltas,
        "lowest_page_deltas": page_deltas[:10],
        "highest_page_deltas": list(reversed(page_deltas[-10:])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two follow-quality reports built from the same manifests.")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    comparison = build_comparison(_load(args.before), _load(args.after))
    if args.output:
        args.output.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
