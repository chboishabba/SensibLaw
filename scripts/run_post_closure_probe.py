#!/usr/bin/env python3
"""Probe post-closure handoff from typed binary references only."""

from __future__ import annotations

import argparse
from pathlib import Path
import pickle
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.checkpoint_retention import (  # noqa: E402
    ArtifactRetentionClass,
    CheckpointRetentionLedger,
)
from src.runtime.reference_receipt import (  # noqa: E402
    atomic_write_binary,
    run_isolated_reference_serializer,
)
from src.runtime.stage_memory_budget import (  # noqa: E402
    MIB,
    StageMemoryBudgetGuard,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--serializer-hard-mib", type=int, default=3072)
    parser.add_argument("--disk-budget-mib", type=int, default=8192)
    return parser.parse_args()


def _mapping(path: Path) -> dict[str, Any]:
    value = pickle.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise ValueError(f"expected binary mapping: {path}")
    return dict(value)


def _find_finalization_root(root: Path) -> Path:
    direct = root / "closure-reference-receipt.spec.pkl"
    if direct.is_file():
        return root
    candidates = sorted(root.glob("closure-finalization/*"))
    for candidate in candidates:
        if (candidate / "materialized-reduction.manifest.pkl").is_file():
            return candidate
    raise FileNotFoundError(
        "no typed binary closure finalization checkpoint found; "
        "legacy text checkpoints are not accepted as authority"
    )


def main() -> int:
    args = _parse_args()
    if args.serializer_hard_mib < 1 or args.disk_budget_mib < 1:
        raise ValueError("probe budgets must be positive")
    finalization_root = _find_finalization_root(args.checkpoint_root.resolve())
    args.output_root.mkdir(parents=True, exist_ok=True)
    budget = StageMemoryBudgetGuard(root=args.output_root)
    before = budget.checkpoint(
        "serialization",
        phase="probe_started",
        details={"finalization_root": str(finalization_root)},
    )

    source_spec = finalization_root / "closure-reference-receipt.spec.pkl"
    probe_spec = args.output_root / "post-closure-probe.spec.pkl"
    spec = _mapping(source_spec)
    spec["probe_source_contract"] = "reference-backed-finalization:v2"
    atomic_write_binary(probe_spec, spec)

    serializer_report_path = args.output_root / "post-closure-serializer-report.pkl"
    serializer_report = run_isolated_reference_serializer(
        spec_path=probe_spec,
        output_path=args.output_root / "post-closure-reference-receipt.pkl",
        report_path=serializer_report_path,
        hard_pss_bytes=args.serializer_hard_mib * MIB,
    )
    after = budget.checkpoint(
        "serialization",
        phase="probe_completed",
        details={"serializer_report": str(serializer_report_path)},
    )

    retention = CheckpointRetentionLedger(
        root=finalization_root,
        budget_bytes=args.disk_budget_mib * MIB,
    )
    authoritative_names = (
        "materialized-reduction.manifest.pkl",
        "materialized-factors.bin",
        "materialized-residuals.bin",
        "closure-reference-receipt.spec.pkl",
    )
    for name in authoritative_names:
        path = finalization_root / name
        if path.exists():
            retention.register(
                path,
                retention_class=ArtifactRetentionClass.AUTHORITATIVE_REUSABLE,
                content_ref=name,
            )

    report = {
        "schema_version": "sensiblaw.post-closure-probe.v2",
        "state": "completed",
        "finalization_root": str(finalization_root),
        "serializer_hard_bytes": args.serializer_hard_mib * MIB,
        "serializer": serializer_report,
        "parent_memory_before": before,
        "parent_memory_after": after,
        "checkpoint_retention": retention.report(),
        "owner_object_transferred": False,
        "full_factor_payload_loaded": False,
        "full_residual_payload_loaded": False,
        "text_serialization": False,
        "promotion_ready": bool(
            serializer_report.get("reference_only")
            and int((serializer_report.get("after") or {}).get("pss_bytes") or 0)
            < args.serializer_hard_mib * MIB
        ),
    }
    atomic_write_binary(args.output_root / "post-closure-probe-report.pkl", report)
    print(
        "post-closure probe "
        f"state={report['state']} promotion_ready={report['promotion_ready']} "
        f"text_serialization={report['text_serialization']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
