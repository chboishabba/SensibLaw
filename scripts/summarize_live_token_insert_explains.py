#!/usr/bin/env python3
"""Summarize genuine parser-token INSERT EXPLAIN JSONL captures."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


CONTRACT_REF = "sensiblaw.live-token-insert-explain-summary.v0_1"


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    strata: list[dict[str, Any]] = []
    referenced = Counter()
    trigger_totals: defaultdict[str, float] = defaultdict(float)
    trigger_calls: defaultdict[str, int] = defaultdict(int)
    constraint_count = 0
    fk_count = 0
    indexes: set[str] = set()

    for record in records:
        metrics = record.get("metrics") or {}
        rows = int(record.get("row_count") or 0)
        execution_ms = metrics.get("execution_time_ms")
        execution_value = (
            float(execution_ms) if isinstance(execution_ms, (int, float)) else None
        )
        wal_bytes = metrics.get("wal_bytes")
        wal_value = int(wal_bytes) if isinstance(wal_bytes, (int, float)) else None
        strata.append(
            {
                "token_batch_ordinal": int(record["selection"]["token_batch_ordinal"]),
                "row_count": rows,
                "execution_time_ms": execution_value,
                "execution_us_per_row": (
                    execution_value * 1000.0 / rows
                    if execution_value is not None and rows
                    else None
                ),
                "shared_hit_blocks": metrics.get("shared_hit_blocks"),
                "shared_read_blocks": metrics.get("shared_read_blocks"),
                "wal_records": metrics.get("wal_records"),
                "wal_bytes": wal_value,
                "wal_bytes_per_row": wal_value / rows if wal_value is not None and rows else None,
                "producer_complete_first_write": bool(
                    record.get("producer_complete_first_write")
                ),
            }
        )
        constraints = record.get("constraints") or []
        constraint_count = max(constraint_count, len(constraints))
        for constraint in constraints:
            if constraint.get("type") == "f":
                fk_count = max(
                    fk_count,
                    sum(1 for item in constraints if item.get("type") == "f"),
                )
                referenced[str(constraint.get("referenced_relation"))] += 1
        for index in record.get("indexes") or []:
            indexes.add(str(index.get("name")))
        triggers = metrics.get("trigger_metrics")
        if isinstance(triggers, list):
            for trigger in triggers:
                name = str(trigger.get("Trigger Name") or trigger.get("Trigger") or "unknown")
                time = trigger.get("Time")
                calls = trigger.get("Calls")
                if isinstance(time, (int, float)):
                    trigger_totals[name] += float(time)
                if isinstance(calls, int):
                    trigger_calls[name] += calls

    ranked_triggers = [
        {
            "trigger_name": name,
            "total_time_ms": total,
            "calls": trigger_calls.get(name, 0),
        }
        for name, total in sorted(trigger_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "contract_ref": CONTRACT_REF,
        "record_count": len(records),
        "strata": sorted(strata, key=lambda item: item["token_batch_ordinal"]),
        "inventory": {
            "constraint_count": constraint_count,
            "foreign_key_count": fk_count,
            "index_count": len(indexes),
            "foreign_keys_by_referenced_relation": dict(sorted(referenced.items())),
        },
        "ranked_explain_triggers": ranked_triggers,
        "interpretation_boundary": (
            "EXPLAIN trigger timing attributes trigger execution, while index/heap "
            "executor costs remain in the plan/flame profile; this summary does not "
            "pretend to assign every millisecond to one constraint or index"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = summarize(_records(args.input))
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
