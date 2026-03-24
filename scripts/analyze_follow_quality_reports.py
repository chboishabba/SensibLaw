#!/usr/bin/env python3
"""Aggregate follow-quality campaign reports into human-usable debug summaries."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _iter_report_paths(paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            resolved.extend(sorted(path.rglob("report.json")))
        elif path.is_file():
            resolved.append(path)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in resolved:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _infer_follow_flags(detail: dict[str, Any]) -> list[str]:
    flags = list(detail.get("quality_flags") or [])
    if flags:
        return flags
    non_list_score = detail.get("non_list_score")
    richness_score = detail.get("richness_score")
    regime_similarity_score = detail.get("regime_similarity_score")
    information_gain_score = detail.get("information_gain_score")
    if isinstance(non_list_score, (int, float)) and float(non_list_score) <= 0.25:
        flags.append("list_like_follow")
    if isinstance(richness_score, (int, float)) and float(richness_score) < 0.35:
        flags.append("thin_follow")
    if isinstance(information_gain_score, (int, float)) and float(information_gain_score) < 0.35:
        flags.append("low_information_gain_follow")
    if isinstance(regime_similarity_score, (int, float)) and float(regime_similarity_score) < 0.35:
        flags.append("regime_jump_follow")
    return flags


def _infer_follow_bucket(detail: dict[str, Any]) -> str:
    explicit = str(detail.get("primary_failure_bucket") or "").strip()
    if explicit:
        return explicit
    flags = _infer_follow_flags(detail)
    if flags:
        return flags[0]
    return "stable_follow"


def build_summary(report_paths: list[Path], *, worst_limit: int) -> dict[str, Any]:
    regime_counts: Counter[str] = Counter()
    follow_failure_bucket_counts: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = defaultdict(list)
    worst_follows: list[dict[str, Any]] = []
    report_summaries: list[dict[str, Any]] = []

    for path in report_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        summary = payload.get("summary") or {}
        pages = payload.get("pages") or []
        report_summaries.append(
            {
                "path": str(path),
                "page_count": int(summary.get("page_count") or len(pages) or 0),
                "dominant_regime_counts": dict(summary.get("dominant_regime_counts") or {}),
            }
        )
        for key, value in (summary.get("dominant_regime_counts") or {}).items():
            regime_counts[str(key)] += int(value or 0)
        for key, value in (summary.get("follow_failure_bucket_counts") or {}).items():
            follow_failure_bucket_counts[str(key)] += int(value or 0)
        for section in ("average_follow_yield_metrics", "average_two_hop_metrics", "average_best_path_metrics"):
            for key, value in (summary.get(section) or {}).items():
                if isinstance(value, (int, float)):
                    metric_values[f"{section}.{key}"].append(float(value))
        for page in pages:
            root_title = str(page.get("title") or "")
            for detail in page.get("follow_target_quality_details") or []:
                flags = _infer_follow_flags(detail)
                bucket = _infer_follow_bucket(detail)
                follow_failure_bucket_counts[bucket] += 1
                worst_follows.append(
                    {
                        "score": float(detail.get("follow_target_quality_score") or 0.0),
                        "root_title": root_title,
                        "follow_title": str(detail.get("follow_title") or detail.get("title") or ""),
                        "bucket": bucket,
                        "flags": flags,
                        "non_list_score": detail.get("non_list_score"),
                        "richness_score": detail.get("richness_score"),
                        "regime_similarity_score": detail.get("regime_similarity_score"),
                        "information_gain_score": detail.get("information_gain_score"),
                        "list_title_markers": list(detail.get("list_title_markers") or []),
                        "list_warning_markers": list(detail.get("list_warning_markers") or []),
                    }
                )
    worst_follows = sorted(worst_follows, key=lambda item: (item["score"], item["root_title"], item["follow_title"]))[:worst_limit]
    return {
        "report_count": len(report_paths),
        "report_summaries": report_summaries,
        "dominant_regime_counts": dict(sorted(regime_counts.items())),
        "follow_failure_bucket_counts": dict(sorted(follow_failure_bucket_counts.items())),
        "average_metrics": {
            key: _mean(values)
            for key, values in sorted(metric_values.items())
        },
        "worst_follows": worst_follows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate follow-quality campaign reports.")
    parser.add_argument("paths", nargs="+", help="Report JSON files or directories containing report.json files")
    parser.add_argument("--worst-limit", type=int, default=12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report_paths = _iter_report_paths(list(args.paths))
    if not report_paths:
        raise SystemExit("no report.json files found")
    summary = build_summary(report_paths, worst_limit=max(1, int(args.worst_limit)))
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("report_count", summary["report_count"])
    print("dominant_regime_counts", summary["dominant_regime_counts"])
    print("follow_failure_bucket_counts", summary["follow_failure_bucket_counts"])
    print("average_metrics", summary["average_metrics"])
    print("worst_follows")
    for item in summary["worst_follows"]:
        print(
            f"  {item['score']:.6f} {item['root_title']} -> {item['follow_title']} "
            f"bucket={item['bucket']} flags={item['flags']} "
            f"non_list={item['non_list_score']} richness={item['richness_score']} "
            f"regime={item['regime_similarity_score']} info={item['information_gain_score']} "
            f"title_markers={item['list_title_markers']} warning_markers={item['list_warning_markers']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
