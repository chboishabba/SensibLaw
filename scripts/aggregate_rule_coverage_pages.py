#!/usr/bin/env python3
"""Combine contiguous rule-coverage pages into one non-executing report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.transformation_rules import (  # noqa: E402
    build_cumulative_rule_coverage_report,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate contiguous, composite-cursor rule coverage pages."
    )
    parser.add_argument(
        "--page",
        action="append",
        nargs=2,
        metavar=("MANIFEST", "RULE_COVERAGE"),
        required=True,
        help="Repeat in cursor order for each materialized page.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--population-exhausted",
        action="store_true",
        help="Assert that the final supplied page exhausted the discovery query.",
    )
    return parser.parse_args()


def _read(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> None:
    args = _parse_args()
    reports: list[dict] = []
    boundaries: list[dict] = []
    manifests: list[dict] = []
    for manifest_path, report_path in args.page:
        manifest = _read(manifest_path)
        report_payload = _read(report_path)
        report = report_payload.get("coverage", report_payload)
        metadata = (manifest.get("discovery") or {}).get("metadata") or {}
        cursor_qid = str(metadata.get("cursor_qid") or "").strip()
        cursor_statement = str(metadata.get("cursor_statement") or "").strip()
        cursor = (
            {"subject_qid": cursor_qid, "statement_id": cursor_statement}
            if cursor_qid and cursor_statement
            else None
        )
        reports.append(report)
        manifests.append(manifest)
        boundaries.append(
            {"cursor": cursor, "next_cursor": metadata.get("next_cursor")}
        )
    exhaustion_ref = None
    if args.population_exhausted:
        final_discovery = manifests[-1].get("discovery") or {}
        final_metadata = final_discovery.get("metadata") or {}
        final_summary = final_discovery.get("summary") or {}
        page_size = int(final_metadata.get("page_size") or 0)
        discovered = int(final_summary.get("discovered_statement_count") or 0)
        if page_size < 1 or discovered >= page_size:
            raise ValueError(
                "population exhaustion requires a final page shorter than its limit"
            )
        exhaustion_ref = "short-page:" + str(args.page[-1][0])
    cumulative = build_cumulative_rule_coverage_report(
        page_reports=reports,
        page_boundaries=boundaries,
        population_exhausted=args.population_exhausted,
        population_exhaustion_ref=exhaustion_ref,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(cumulative, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "page_count": cumulative["page_count"],
                "candidate_count": cumulative["candidate_count"],
                "dependency_group_count": cumulative["dependency_group_count"],
                "population_exhausted": cumulative["population_exhausted"],
                "outcome_counts": cumulative["outcome_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
