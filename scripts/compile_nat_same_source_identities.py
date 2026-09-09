#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata_nat_source_discovery import build_same_source_identity_receipt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile reviewed same-source identity decisions for discovered Nat source locators."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--discovery-dispatch", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    dispatch = json.loads(args.discovery_dispatch.read_text(encoding="utf-8"))
    decisions_doc = json.loads(args.decisions.read_text(encoding="utf-8"))
    demands = {item["demand_ref"]: item for item in plan.get("demands", [])}
    candidates = {
        candidate["candidate_ref"]: candidate
        for receipt in dispatch.get("receipts", [])
        for candidate in receipt.get("candidates", [])
    }
    receipts = []
    for decision in decisions_doc.get("decisions", []):
        demand_ref = str(decision.get("source_discovery_demand_ref", "")).strip()
        candidate_ref = str(decision.get("candidate_ref", "")).strip()
        if demand_ref not in demands:
            raise ValueError(f"identity decision names unknown demand: {demand_ref}")
        if candidate_ref not in candidates:
            raise ValueError(f"identity decision names unknown candidate: {candidate_ref}")
        receipts.append(build_same_source_identity_receipt(
            demands[demand_ref],
            candidates[candidate_ref],
            disposition=str(decision.get("disposition", "unresolved")),
            verifier_reference=str(decision.get("verifier_reference", "")),
            identity_evidence_locator=str(decision.get("identity_evidence_locator", "")),
            verification_note=str(decision.get("verification_note", "")),
        ))
    receipts.sort(key=lambda item: item["receipt_ref"])
    payload = {
        "source_discovery_plan_ref": plan.get("plan_ref", ""),
        "source_discovery_dispatch_ref": dispatch.get("dispatch_ref", ""),
        "receipt_count": len(receipts),
        "same_source_identity_paid_count": sum(1 for item in receipts if item["same_source_identity_paid"]),
        "receipts": receipts,
        "source_support_paid_count": 0,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "receipt_count", "same_source_identity_paid_count", "source_support_paid_count"
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
