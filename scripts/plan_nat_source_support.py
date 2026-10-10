#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_support import build_source_fetch_plan  # noqa: E402


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a coverage-complete Nat batch into residual-bound, URL-deduplicated "
            "external source fetch demands. Performs no network or semantic verification."
        )
    )
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--coverage-dispatch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = build_source_fetch_plan(_load(args.batch), _load(args.coverage_dispatch))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "plan_ref": plan["plan_ref"],
                "source_residual_count": plan["source_residual_count"],
                "distinct_url_count": plan["distinct_url_count"],
                "residuals_without_p854_count": plan["residuals_without_p854_count"],
                "network_performed": False,
                "source_support_paid_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
