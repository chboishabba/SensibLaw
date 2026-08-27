#!/usr/bin/env python3
"""Summarise timeout-surviving partial execution timing samples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.partial_execution_timing import aggregate_partial_timing


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="One or more *.partial-timing.jsonl files or directories containing them.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _files(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if path.is_dir():
            result.extend(sorted(path.rglob("*.partial-timing.jsonl")))
        else:
            result.append(path)
    return result


def main() -> int:
    args = _args()
    rows: list[dict[str, Any]] = []
    selected = _files(args.paths)
    for path in selected:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"expected JSON object in {path}")
                    rows.append(value)
    report = aggregate_partial_timing(rows)
    report["source_files"] = [str(path) for path in selected]
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if rows else 3


if __name__ == "__main__":
    raise SystemExit(main())
