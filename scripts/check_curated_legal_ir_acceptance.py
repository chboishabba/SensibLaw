#!/usr/bin/env python3
"""Evaluate curated Legal IR correctness, offline, parity, and p50 thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--parity-root", type=Path, required=True)
    parser.add_argument("--maximum-p50-postgres-seconds", type=float, default=1.85)
    parser.add_argument("--maximum-p50-base-reduction-seconds", type=float, default=0.69)
    parser.add_argument("--require-control-parity", action="store_true")
    return parser.parse_args()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stage_values(timing: dict[str, object], stage: str) -> list[float]:
    values = []
    for document in timing.get("documents", []):
        for row in document.get("stage_timings", []):
            if str(row.get("stage")) == stage:
                values.append(float(row.get("elapsed_ms") or 0) / 1000.0)
    return values


def main() -> int:
    args = _args()
    build = args.build_root.resolve()
    parity = args.parity_root.resolve()
    catalogue = _load(build / "catalogue_build_manifest.json")
    admission = _load(build / "source_admission_manifest.json")
    network = _load(build / "network_absence_receipt.json")
    timing = _load(build / "document_compilation_timings.json")
    parity_receipt = _load(parity / "parity_receipt.json")
    parity_network = _load(parity / "network_absence_receipt.json")

    failures: list[str] = []
    if catalogue.get("failure_refs"):
        failures.append("unexpected_compiler_failures")
    if not network.get("external_network_absent"):
        failures.append("catalogue_external_network_attempt")
    if not parity_network.get("external_network_absent"):
        failures.append("parity_external_network_attempt")
    if int(parity_receipt.get("network_attempt_count") or 0) != 0:
        failures.append("parity_receipt_network_attempt")
    if parity_receipt.get("unexpected_failure_refs"):
        failures.append("parity_unexpected_failures")
    if args.require_control_parity and parity_receipt.get("identity_parity") is not True:
        failures.append("semantic_identity_drift_or_control_absent")
    if admission.get("counts", {}).get("compile", 0) < 1:
        failures.append("no_compile_eligible_source")

    postgres_values = _stage_values(timing, "postgres_persistence")
    base_values = _stage_values(timing, "base_proposal_reduction")
    p50_postgres = median(postgres_values) if postgres_values else None
    p50_base = median(base_values) if base_values else None
    if p50_postgres is None:
        failures.append("postgres_timing_absent")
    elif p50_postgres > args.maximum_p50_postgres_seconds:
        failures.append("postgres_p50_threshold_failed")
    if p50_base is None:
        failures.append("base_reduction_timing_absent")
    elif p50_base > args.maximum_p50_base_reduction_seconds:
        failures.append("base_reduction_p50_threshold_failed")

    result = {
        "schema_version": "sl.curated_legal_ir_acceptance.v0_1",
        "accepted": not failures,
        "failures": failures,
        "thresholds": {
            "maximum_p50_postgres_seconds": args.maximum_p50_postgres_seconds,
            "maximum_p50_base_reduction_seconds": args.maximum_p50_base_reduction_seconds,
        },
        "observed": {
            "p50_postgres_seconds": p50_postgres,
            "p50_base_reduction_seconds": p50_base,
            "document_count": len(timing.get("documents", [])),
            "admission_counts": admission.get("counts", {}),
            "identity_parity": parity_receipt.get("identity_parity"),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
