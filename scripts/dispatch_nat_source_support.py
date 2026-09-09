#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_support_dispatch import (  # noqa: E402
    dispatch_source_fetch_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch each distinct Nat P854 source once under one shared rate limiter and "
            "project transport/integrity observations back to exact source-support residuals."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument("--max-fetches", type=int, default=128)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("expected source-fetch plan JSON object")
    dispatch = dispatch_source_fetch_plan(
        plan,
        worker_budget=max(1, int(args.worker_budget)),
        max_fetches=max(1, int(args.max_fetches)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dispatch, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "dispatch_ref": dispatch["dispatch_ref"],
                "source_residual_count": dispatch["source_residual_count"],
                "distinct_url_count": dispatch["distinct_url_count"],
                "fetch_call_count": dispatch["fetch_call_count"],
                "counts_by_fetch_status": dispatch["counts_by_fetch_status"],
                "reference_present_count": dispatch["reference_present_count"],
                "content_acquired_residual_count": dispatch[
                    "content_acquired_residual_count"
                ],
                "source_support_paid_count": dispatch["source_support_paid_count"],
                "source_support_still_open_count": dispatch[
                    "source_support_still_open_count"
                ],
                "bytes_received": dispatch["bytes_received"],
                "http_request_count": dispatch["http_request_count"],
                "cache_hits": dispatch["cache_hits"],
                "cache_misses": dispatch["cache_misses"],
                "consumer_verification_performed": dispatch[
                    "consumer_verification_performed"
                ],
                "semantic_promotion_performed": dispatch[
                    "semantic_promotion_performed"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
