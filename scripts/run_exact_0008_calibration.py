#!/usr/bin/env python3
"""Run three fresh, rolled-back exact-0008 calibrations and compare reports.

This is an orchestration/reporting script, not a compiler entry point.  Every
trial launches ``run_complete_tranche.py`` in a new process and persists the
raw bounded stream, environment, stage ledger, single-trial report, and final
three-trial comparison.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from src.runtime.execution_resource_ledger import compare_ownership_reports


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL"), required=True
    )
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ledger-root", type=Path, required=True)
    parser.add_argument("--tranche", choices=("GWB", "AU", "BREXIT"), default="GWB")
    parser.add_argument("--closure-workers", type=int, default=1)
    parser.add_argument("--owner-partitions", type=int, default=1)
    parser.add_argument("--parser-workers", type=int, default=1)
    parser.add_argument("--worker-budget", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_path = args.input_path.resolve()
    if not input_path.exists():
        raise SystemExit(f"input path does not exist: {input_path}")
    output_root = args.output_root.resolve()
    ledger_root = args.ledger_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    ledger_root.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for trial in range(1, 4):
        trial_ref = f"trial-{trial}"
        trial_output = output_root / trial_ref
        command = [
            sys.executable,
            str(Path(__file__).with_name("run_complete_tranche.py")),
            "--tranche",
            args.tranche,
            "--database-url",
            args.database_url,
            "--output-root",
            str(trial_output),
            "--input-path",
            str(input_path),
            "--calibration",
            "--ledger-root",
            str(ledger_root),
            "--trial-ref",
            trial_ref,
            "--closure-workers",
            str(args.closure_workers),
            "--owner-partitions",
            str(args.owner_partitions),
            "--parser-workers",
            str(args.parser_workers),
            "--worker-budget",
            str(args.worker_budget),
        ]
        environment = os.environ.copy()
        environment["SENSIBLAW_TRANCHE_CALIBRATION"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        subprocess.run(command, check=True, env=environment)
        report_path = ledger_root / f"{trial_ref}-{args.tranche.lower()}.report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        calibration_path = (
            trial_output / args.tranche.lower() / "tranche_calibration.json"
        )
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        if calibration.get("rollback_row_counts") != {
            "source_documents": 0,
            "occurrences": 0,
            "builds": 0,
            "artifact_manifests": 0,
        }:
            raise SystemExit(f"rollback leak in {calibration_path}")
        reports.append(report)

    comparison = compare_ownership_reports(reports)
    comparison["input_path"] = str(input_path)
    comparison["tranche"] = args.tranche
    comparison["rollback_verified"] = True
    comparison["optimisation_owner"] = None
    comparison["threshold_selected"] = False
    comparison_path = ledger_root / "exact-0008-comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"comparison": str(comparison_path), **comparison}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
