#!/usr/bin/env python3
"""Probe post-closure serialization from durable references only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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
    atomic_stream_json,
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


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON mapping: {path}")
    return dict(value)


def _find_finalization_root(root: Path) -> Path:
    direct = root / "closure-reference-receipt.spec.json"
    if direct.is_file():
        return root
    candidates = sorted(root.glob("closure-finalization/*"))
    for candidate in candidates:
        if (candidate / "materialized-reduction.manifest.json").is_file():
            return candidate
    raise FileNotFoundError("no completed closure finalization checkpoint found")


def _legacy_spec(finalization_root: Path) -> dict[str, Any]:
    reduction = _json(finalization_root / "materialized-reduction.manifest.json")
    certificate_payload = _json(finalization_root / "fixed-point-certificate.json")
    certificate = certificate_payload.get("certificate") or certificate_payload
    ledger_path = finalization_root / "convergent-ledger.json"
    boundary_path = finalization_root / "region-boundary-summaries.json"
    factor_path = finalization_root / "materialized-factors.jsonl"
    residual_path = finalization_root / "materialized-residuals.jsonl"
    return {
        "probe_source_contract": "legacy-finalization-checkpoints:v1",
        "document_ref": str(certificate.get("document_ref") or ""),
        "revision": int(certificate.get("revision") or 0),
        "owner_fingerprint": reduction.get("owner_fingerprint") or {},
        "materialized_reduction": {
            "graph_ref": reduction.get("graph_ref"),
            "proposal_count": reduction.get("proposal_count"),
            "deduplicated_count": reduction.get("deduplicated_count"),
            "factor_count": reduction.get("factor_count"),
            "residual_count": reduction.get("residual_count"),
            "factor_path": str(factor_path),
            "residual_path": str(residual_path),
        },
        "ledger_ref": certificate.get("ledger_ref"),
        "ledger_path": str(ledger_path),
        "boundary_summary_path": str(boundary_path),
        "fixed_point_certificate": certificate,
        "reference_only": True,
        "owner_object_present": False,
    }


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

    source_spec = finalization_root / "closure-reference-receipt.spec.json"
    probe_spec = args.output_root / "post-closure-probe.spec.json"
    if source_spec.is_file():
        spec = _json(source_spec)
        spec["probe_source_contract"] = "reference-backed-finalization:v1"
    else:
        spec = _legacy_spec(finalization_root)
    atomic_stream_json(probe_spec, spec)

    serializer_report = run_isolated_reference_serializer(
        spec_path=probe_spec,
        output_path=args.output_root / "post-closure-reference-receipt.json",
        report_path=args.output_root / "post-closure-serializer-report.json",
        hard_pss_bytes=args.serializer_hard_mib * MIB,
    )
    after = budget.checkpoint(
        "serialization",
        phase="probe_completed",
        details={
            "serializer_report": str(
                args.output_root / "post-closure-serializer-report.json"
            )
        },
    )

    retention = CheckpointRetentionLedger(
        root=finalization_root,
        budget_bytes=args.disk_budget_mib * MIB,
    )
    authoritative_names = (
        "materialized-reduction.manifest.json",
        "materialized-factors.jsonl",
        "materialized-residuals.jsonl",
        "convergent-ledger.json",
        "fixed-point-certificate.json",
        "closure-reference-receipt.spec.json",
    )
    for name in authoritative_names:
        path = finalization_root / name
        if path.exists():
            retention.register(
                path,
                retention_class=ArtifactRetentionClass.AUTHORITATIVE_REUSABLE,
                content_ref=name,
            )
    for path in finalization_root.glob("*progress*.json"):
        retention.register(
            path,
            retention_class=ArtifactRetentionClass.DIAGNOSTIC,
            successor_ref="post-closure-probe",
        )

    report = {
        "schema_version": "sensiblaw.post-closure-probe.v1",
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
        "promotion_ready": bool(
            serializer_report.get("reference_only")
            and int((serializer_report.get("after") or {}).get("pss_bytes") or 0)
            < args.serializer_hard_mib * MIB
        ),
    }
    atomic_stream_json(args.output_root / "post-closure-probe-report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
