#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_discovery import build_source_discovery_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile provider-neutral source-discovery demands for failed Nat source locators."
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--source-dispatch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_plan = json.loads(args.source_plan.read_text(encoding="utf-8"))
    source_dispatch = json.loads(args.source_dispatch.read_text(encoding="utf-8"))
    plan = build_source_discovery_plan(source_plan, source_dispatch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "plan_ref": plan["plan_ref"],
        "failed_locator_count": plan["failed_locator_count"],
        "blocked_residual_count": plan["blocked_residual_count"],
        "source_support_paid_count": plan["source_support_paid_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
