#!/usr/bin/env python3
"""Fail-closed acceptance check for the Solomon full Legal-IR + atomic run.

The PostgreSQL parity runner can validly produce an empty Legal-IR coverage result.
That is useful diagnostic evidence, but it is not proof that the exact Solomon
statutory sources participated in the runtime.  This checker keeps those claims
separate and requires the defining s 92 / s 17 source revisions to be selected
before declaring the Solomon source-to-Legal-IR weld complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_ATOMIC_PROPOSITIONS = {
    "prop:SB:s92:benefit-influence-fact",
    "prop:SB:s17:inducement-fact",
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _args()
    root = args.output_dir.resolve()
    full = _load(root / "full_legal_parity_receipt.json")
    flow = _load(root / "legal_ir_flow.json")
    atomic = _load(root / "atomic_legal_registry_receipt.json")

    plans = tuple(flow.get("plans") or ())
    legal_ir = tuple(flow.get("legal_ir") or ())
    typed_meets = tuple(flow.get("typed_meets") or ())
    demands = tuple(flow.get("demands") or ())

    ready_plans = tuple(
        row for row in plans if isinstance(row, dict) and row.get("state") == "ready_persisted"
    )
    selected_source_refs = sorted(
        {
            str(ref)
            for row in ready_plans
            for ref in (row.get("selected_source_revision_refs") or ())
            if str(ref)
        }
    )

    tests = tuple(atomic.get("tests") or ())
    atomic_props = {
        str(row.get("proposition_ref"))
        for row in tests
        if isinstance(row, dict) and row.get("proposition_ref")
    }
    defining_source_refs = sorted(
        {
            str(row.get("source_revision_ref"))
            for row in tests
            if isinstance(row, dict) and row.get("source_revision_ref")
        }
    )
    missing_defining_sources = sorted(set(defining_source_refs) - set(selected_source_refs))

    runtime_exercised = bool(
        demands and ready_plans and selected_source_refs and legal_ir and typed_meets
    )
    atomic_registry_complete = EXPECTED_ATOMIC_PROPOSITIONS.issubset(atomic_props)
    defining_sources_selected = bool(defining_source_refs) and not missing_defining_sources
    base_full_parity_green = full.get("full_parity_passed") is True
    legal_truth_stays_open = full.get("legal_truth_closed") is False
    no_case_evidence_router_reuse = (
        full.get("atomic_case_evidence_reuses_legal_source_acquisition") is False
    )

    passed = bool(
        base_full_parity_green
        and legal_truth_stays_open
        and no_case_evidence_router_reuse
        and atomic_registry_complete
        and runtime_exercised
        and defining_sources_selected
    )

    receipt = {
        "contract_ref": "solomon-full-legal-ir-acceptance:v0_1",
        "base_full_parity_green": base_full_parity_green,
        "legal_truth_stays_open": legal_truth_stays_open,
        "case_evidence_router_separation_ok": no_case_evidence_router_reuse,
        "atomic_registry_complete": atomic_registry_complete,
        "demand_count": len(demands),
        "ready_persisted_plan_count": len(ready_plans),
        "selected_source_revision_refs": selected_source_refs,
        "legal_ir_count": len(legal_ir),
        "typed_meet_count": len(typed_meets),
        "legal_ir_runtime_exercised": runtime_exercised,
        "atomic_defining_source_revision_refs": defining_source_refs,
        "missing_atomic_defining_source_revision_refs": missing_defining_sources,
        "atomic_defining_sources_selected": defining_sources_selected,
        "solomon_source_to_legal_ir_weld_complete": passed,
        "empty_legal_ir_is_valid_coverage_result_but_not_weld_completion": True,
        "legal_truth_closed": False,
    }

    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    output = root / "solomon_full_legal_ir_acceptance.json"
    output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
