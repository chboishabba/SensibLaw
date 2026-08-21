#!/usr/bin/env python3
"""Summarize diagnostic hierarchy-close EXPLAIN and nested SQL receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUMMARY_REF = "sensiblaw.live-hierarchy-close-attribution-summary.v0_1"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top-statements", type=int, default=12)
    args = parser.parse_args()
    if args.top_statements < 1:
        parser.error("--top-statements must be positive")
    return args


def _records(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            result.append(json.loads(line))
    return result


def summarize(records: list[dict[str, Any]], *, top_statements: int) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for record in records:
        selection = record["selection"]
        support = record["hierarchy_support"]
        metrics = record["close_metrics"]
        nested = sorted(
            record.get("nested_statement_deltas", ()),
            key=lambda item: float(item.get("total_exec_ms", 0.0)),
            reverse=True,
        )
        summaries.append(
            {
                "region_kind": int(selection["region_kind"]),
                "region_kind_name": str(selection["region_kind_name"]),
                "per_kind_ordinal": int(selection["per_kind_ordinal"]),
                "region_id": int(record["preclose"]["region_id"]),
                "close_execution_ms": float(metrics.get("execution_time_ms", 0.0)),
                "close_shared_hits": int(metrics.get("shared_hit_blocks", 0)),
                "close_shared_reads": int(metrics.get("shared_read_blocks", 0)),
                "close_temp_reads": int(metrics.get("temp_read_blocks", 0)),
                "close_temp_writes": int(metrics.get("temp_written_blocks", 0)),
                "close_wal_bytes": int(metrics.get("wal_bytes", 0)),
                "child_count": int(support["child_count"]),
                "child_interface_count": int(support["child_interface_count"]),
                "child_interface_cardinality": int(
                    support["child_interface_cardinality"]
                ),
                "child_unresolved_count": int(support["child_unresolved_count"]),
                "child_export_count_by_target_kind": support[
                    "child_export_count_by_target_kind"
                ],
                "top_nested_statements": nested[:top_statements],
                "nested_total_exec_ms": sum(
                    float(item.get("total_exec_ms", 0.0)) for item in nested
                ),
            }
        )
    summaries.sort(key=lambda item: (item["region_kind"], item["per_kind_ordinal"]))
    return {
        "contract_ref": SUMMARY_REF,
        "record_count": len(summaries),
        "records": summaries,
        "semantics": (
            "close execution time is the genuine EXPLAINed region UPDATE; nested "
            "statement deltas cover the complete selected parent-close call and can "
            "overlap by inclusive PL/pgSQL/SPI attribution, so they are diagnostic "
            "rankings rather than an additive wall-time decomposition"
        ),
    }


def main() -> int:
    args = _parse_args()
    summary = summarize(_records(args.input), top_statements=args.top_statements)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
