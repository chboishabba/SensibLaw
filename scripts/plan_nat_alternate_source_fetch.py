#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_discovery_integration import (  # noqa: E402
    build_replayable_alternate_source_fetch_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile same-source-admitted alternate locators onto the existing Nat source fetch plan contract."
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--discovery-plan", type=Path, required=True)
    parser.add_argument("--discovery-dispatch", type=Path, required=True)
    parser.add_argument("--identity-receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_plan = json.loads(args.source_plan.read_text(encoding="utf-8"))
    discovery_plan = json.loads(args.discovery_plan.read_text(encoding="utf-8"))
    discovery_dispatch = json.loads(args.discovery_dispatch.read_text(encoding="utf-8"))
    identities_doc = json.loads(args.identity_receipts.read_text(encoding="utf-8"))
    plan = build_replayable_alternate_source_fetch_plan(
        source_plan,
        discovery_plan,
        discovery_dispatch,
        identities_doc.get("receipts", []),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "plan_ref": plan["plan_ref"],
        "source_residual_count": plan["source_residual_count"],
        "distinct_url_count": plan["distinct_url_count"],
        "source_support_paid_count": plan["source_support_paid_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
