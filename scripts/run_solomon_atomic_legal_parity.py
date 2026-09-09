#!/usr/bin/env python3
"""Validate Solomon Islands atomic legal parity against the SLR runtime contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.atomic_legal_registry import AtomicLegalTest, build_atomic_registry  # noqa: E402

EXPECTED = {
    "prop:SB:s92:benefit-influence-fact": 0,
    "prop:SB:s17:inducement-fact": 0,
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "fixtures/legal/solomon_islands_2026_atomic_registry.json",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _args()
    raw = json.loads(args.fixture.read_text(encoding="utf-8"))
    case_ref = str(raw["case_ref"])
    tests = tuple(
        AtomicLegalTest(
            proposition_ref=str(row["proposition_ref"]),
            case_ref=case_ref,
            legal_system_ref=str(row["legal_system_ref"]),
            source_revision_ref=str(row["source_revision_ref"]),
            exact_locator=str(row["exact_locator"]),
            authority_role=str(row["authority_role"]),
            subject_ref=str(row["subject_ref"]),
            gate=int(row["gate"]),
            positive_witness_refs=tuple(row.get("positive_witness_refs") or ()),
            negative_witness_refs=tuple(row.get("negative_witness_refs") or ()),
            evidence_fibre_ref=str(row.get("evidence_fibre_ref") or ""),
            test_reference=str(row.get("test_reference") or ""),
        )
        for row in raw.get("tests") or ()
    )
    registry = build_atomic_registry(case_ref=case_ref, tests=tests)

    missing = sorted(set(EXPECTED) - {row.proposition_ref for row in tests})
    unexpected = sorted({row.proposition_ref for row in tests} - set(EXPECTED))
    gate_mismatches = {
        proposition_ref: {
            "expected": expected,
            "actual": registry.gate_for(proposition_ref),
        }
        for proposition_ref, expected in EXPECTED.items()
        if proposition_ref not in missing
        and registry.gate_for(proposition_ref) != expected
    }

    availability = dict(raw.get("public_artifact_availability") or {})
    artifact_boundary_ok = (
        availability.get("journalist_or_opposition_reports_primary_artifact") is True
        and availability.get("public_full_thread_or_screenshot_located") is False
        and availability.get(
            "public_reviewer_can_inspect_sender_recipient_timestamp_topology"
        )
        is False
        and availability.get("user_side_acquisition_debt") is False
    )

    receipt = {
        **registry.to_dict(),
        "expected_gates": EXPECTED,
        "missing_propositions": missing,
        "unexpected_propositions": unexpected,
        "gate_mismatches": gate_mismatches,
        "public_artifact_boundary_ok": artifact_boundary_ok,
        "public_artifact_availability": availability,
        "parity_passed": not missing
        and not unexpected
        and not gate_mismatches
        and artifact_boundary_ok,
        "agda_parity_target": "DASHI.Law.SolomonIslandsAtomicPremiseRegistryExact",
    }

    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if receipt["parity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
