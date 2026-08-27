#!/usr/bin/env python3
"""Check that performance receipts cover a representative token volume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.performance_workload_scale import (
    MIN_REPRESENTATIVE_TOKENS,
    assess_performance_workload,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "receipt",
        nargs="+",
        type=Path,
        help="One or more JSON receipts whose parsed token counts form the corpus.",
    )
    parser.add_argument(
        "--minimum-tokens",
        type=int,
        default=MIN_REPRESENTATIVE_TOKENS,
        help="Representative corpus floor (default: 25000 tokens).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    receipts: list[dict[str, Any]] = []
    for path in args.receipt:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"receipt must contain one JSON object: {path}")
        receipts.append(payload)
    assessment = assess_performance_workload(
        receipts,
        minimum_tokens=args.minimum_tokens,
    )
    print(json.dumps(assessment.to_dict(), indent=2, sort_keys=True))
    if assessment.gate.value == "pass":
        return 0
    if assessment.gate.value == "fail":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
