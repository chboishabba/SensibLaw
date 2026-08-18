#!/usr/bin/env python3
"""Report live/failure-surviving strict numeric PNF progress and timing evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.numeric_kernel_progress import numeric_kernel_progress_snapshot


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--run-ref", required=True)
    parser.add_argument("--document-ref", required=True)
    parser.add_argument(
        "--progress-ledger",
        type=Path,
        help=(
            "Optional durable local_pnf_compile_progress.jsonl journal or final "
            "local_pnf_compile_progress.json snapshot."
        ),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _last_progress_event(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    if path.suffix == ".jsonl":
        last: dict[str, Any] | None = None
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, dict):
                    last = dict(row)
        return last
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list) or not events:
        return None
    row = events[-1]
    return dict(row) if isinstance(row, dict) else None


def main() -> int:
    args = _parse_args()
    snapshot = numeric_kernel_progress_snapshot(
        args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
    )
    progress_event = _last_progress_event(args.progress_ledger)
    report: dict[str, Any] = {
        "schema_version": "sensiblaw.numeric-kernel-progress-report.v1",
        "snapshot": snapshot,
        "last_durable_progress_event": progress_event,
        "interpretation": {
            "parser_summed_work_ns": (
                "completed partition parser-active work; not total pipeline wall"
            ),
            "frontier_summed_interface_elapsed_ms": (
                "completed interface reduction work by region kind; do not add to "
                "coordinator wall as if disjoint"
            ),
            "active_kernel": (
                "last durable progress event names the current/failing coordinator "
                "kernel when instrumentation is enabled"
            ),
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
