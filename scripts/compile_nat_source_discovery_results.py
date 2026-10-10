#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_discovery import normalize_discovery_provider_receipt  # noqa: E402
from src.policy.carriers.canonical import canonical_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize Tavily/Google/Exa/MCP/human source-discovery results against exact Nat discovery demands."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--provider-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    raw = json.loads(args.provider_results.read_text(encoding="utf-8"))
    demands = {item["demand_ref"]: item for item in plan.get("demands", [])}
    entries = raw.get("results", []) if isinstance(raw, dict) else []
    receipts = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        demand_ref = str(entry.get("source_discovery_demand_ref", "")).strip()
        if demand_ref not in demands:
            raise ValueError(f"provider result names unknown discovery demand: {demand_ref}")
        receipts.append(normalize_discovery_provider_receipt(demands[demand_ref], entry))
    receipts.sort(key=lambda item: item["receipt_ref"])
    payload_without_ref = {
        "source_discovery_plan_ref": plan.get("plan_ref", ""),
        "receipt_count": len(receipts),
        "candidate_count": sum(int(item.get("candidate_count", 0)) for item in receipts),
        "receipts": receipts,
        "same_source_identity_paid_count": 0,
        "source_support_paid_count": 0,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-source-discovery-dispatch:" + canonical_sha256(payload_without_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "dispatch_ref": payload["dispatch_ref"],
        "receipt_count": payload["receipt_count"],
        "candidate_count": payload["candidate_count"],
        "same_source_identity_paid_count": 0,
        "source_support_paid_count": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
