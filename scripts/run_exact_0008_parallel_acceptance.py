#!/usr/bin/env python3
"""Run exact-0008 with four semantic workers and compare durable receipts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.semantic_parity import (  # noqa: E402
    compare_semantic_surfaces,
    semantic_surface_from_execution_receipt,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help=(
            "Use the failed trial's output root to reuse source and parser checkpoints, "
            "or a new root for a clean run."
        ),
    )
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "docs" / "calibration" / "exact_0008_serial_baseline.v1.json",
    )
    parser.add_argument(
        "--reference-semantic-receipt",
        type=Path,
        help="Optional prior successful/resumed exact-0008 semantic receipt.",
    )
    parser.add_argument("--soft-memory-mib", type=int, default=6144)
    parser.add_argument("--hard-memory-mib", type=int, default=8192)
    parser.add_argument("--typing-workers", type=int, default=4)
    parser.add_argument("--typing-leaf-capacity", type=int, default=4096)
    parser.add_argument("--typing-arity", type=int, default=4)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument(
        "--parser-workers",
        type=int,
        default=1,
        help="Keep one to reuse the committed exact-0008 parser-fibre checkpoints.",
    )
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument("--tranche", choices=("GWB", "AU", "BREXIT"), default="GWB")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.hard_memory_mib <= args.soft_memory_mib:
        parser.error("--hard-memory-mib must exceed --soft-memory-mib")
    for name in (
        "typing_workers",
        "typing_leaf_capacity",
        "closure_workers",
        "owner_partitions",
        "parser_workers",
        "worker_budget",
    ):
        if int(getattr(args, name)) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.typing_arity < 2:
        parser.error("--typing-arity must be at least two")
    return args


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _kernel_seconds(
    receipt: Mapping[str, Any], prefix: str, *, exact_stage: str | None = None
) -> float:
    total = 0
    for row in receipt.get("kernel_timeline") or ():
        if not isinstance(row, Mapping) or row.get("phase") != "kernel_completed":
            continue
        stage = str(row.get("stage") or "")
        selected = (
            stage == exact_stage
            if exact_stage is not None
            else stage.startswith(prefix)
        )
        if selected:
            total += int(row.get("elapsed_ns") or 0)
    return total / 1_000_000_000


def _process_parallelism(receipt: Mapping[str, Any]) -> dict[str, Any]:
    typing_pids = {
        int(pid)
        for hierarchy in (receipt.get("typing_hierarchies") or {}).values()
        if isinstance(hierarchy, Mapping)
        for pid in hierarchy.get("worker_pids") or ()
        if int(pid) > 0
    }
    closure_counters = receipt.get("closure_audit") or {}
    closure_pids = {
        int(str(key).split(":", maxsplit=1)[1])
        for key, value in closure_counters.items()
        if str(key).startswith("process_worker_pid:") and int(value or 0) > 0
    }
    observed = typing_pids | closure_pids
    return {
        "typing_worker_pids": sorted(typing_pids),
        "closure_worker_pids": sorted(closure_pids),
        "distinct_semantic_worker_pids": sorted(observed),
        "distinct_semantic_worker_count": len(observed),
        "parallel_process_execution_observed": len(observed) >= 2,
    }


def main() -> int:
    args = _parse_args()
    acceptance_root = args.acceptance_root.resolve()
    semantic_root = acceptance_root / "semantic-checkpoints"
    acceptance_root.mkdir(parents=True, exist_ok=True)
    baseline = _json(args.baseline.resolve())
    semantic_process_workers = max(args.typing_workers, args.closure_workers)

    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_strict_tranche_acceptance.py"),
        "--tranche",
        args.tranche,
        "--database-url",
        args.database_url,
        "--input-path",
        str(args.input_path.resolve()),
        "--output-root",
        str(args.output_root.resolve()),
        "--acceptance-root",
        str(acceptance_root / "strict"),
        "--soft-memory-mib",
        str(args.soft_memory_mib),
        "--hard-memory-mib",
        str(args.hard_memory_mib),
        "--document-workers",
        "1",
        "--closure-workers",
        str(args.closure_workers),
        "--owner-partitions",
        str(args.owner_partitions),
        "--parser-workers",
        str(args.parser_workers),
        "--worker-budget",
        str(args.worker_budget),
        "--offline",
        "--skip-legal-follow",
        "--calibration",
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": args.database_url,
            "PYTHONUNBUFFERED": "1",
            "SENSIBLAW_SEMANTIC_CHECKPOINT_DIR": str(semantic_root),
            "SENSIBLAW_TYPING_WORKERS": str(args.typing_workers),
            "SENSIBLAW_TYPING_LEAF_CAPACITY": str(args.typing_leaf_capacity),
            "SENSIBLAW_TYPING_HIERARCHY_ARITY": str(args.typing_arity),
            "SENSIBLAW_SEMANTIC_PROCESS_WORKERS": str(semantic_process_workers),
            "SENSIBLAW_DOCUMENT_RETENTION_MODE": "production_compact",
        }
    )
    started = {
        "schema_version": "sensiblaw.exact-0008-parallel-acceptance.v1",
        "state": "started",
        "accepted": False,
        "command": command,
        "configuration": {
            "typing_workers": args.typing_workers,
            "typing_leaf_capacity": args.typing_leaf_capacity,
            "typing_arity": args.typing_arity,
            "closure_workers": args.closure_workers,
            "owner_partitions": args.owner_partitions,
            "parser_workers": args.parser_workers,
            "worker_budget": args.worker_budget,
            "semantic_process_workers": semantic_process_workers,
        },
        "baseline": str(args.baseline.resolve()),
    }
    report_path = acceptance_root / "parallel-acceptance-comparison.json"
    _atomic_json(report_path, started)

    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    strict_receipt_path = acceptance_root / "strict" / "acceptance-receipt.json"
    strict_receipt = (
        _json(strict_receipt_path)
        if strict_receipt_path.exists()
        else {"state": "missing", "accepted": False}
    )
    semantic_receipt_path = semantic_root / "semantic-execution-receipt.json"
    semantic_receipt = (
        _json(semantic_receipt_path)
        if semantic_receipt_path.exists()
        else {"state": "missing"}
    )

    local_typing_seconds = _kernel_seconds(
        semantic_receipt, "local_typing_diagnostics:"
    )
    closure_seconds = _kernel_seconds(
        semantic_receipt,
        "streaming_closure:",
        exact_stage="streaming_closure:fixed_point",
    )
    baseline_runtime = dict(baseline.get("runtime") or {})
    runtime_comparison = {
        "serial_local_typing_seconds": baseline_runtime.get(
            "local_typing_diagnostics_seconds"
        ),
        "parallel_local_typing_seconds": local_typing_seconds,
        "local_typing_speedup": (
            float(baseline_runtime["local_typing_diagnostics_seconds"])
            / local_typing_seconds
            if local_typing_seconds > 0
            else None
        ),
        "serial_closure_seconds": baseline_runtime.get("streaming_closure_seconds"),
        "parallel_closure_seconds": closure_seconds,
        "closure_speedup": (
            float(baseline_runtime["streaming_closure_seconds"]) / closure_seconds
            if closure_seconds > 0
            else None
        ),
        "serial_peak_rss_bytes": baseline_runtime.get("observed_peak_rss_bytes"),
        "parallel_peak_resources": strict_receipt.get("peak_resources") or {},
    }

    current_surface = (
        semantic_surface_from_execution_receipt(semantic_receipt)
        if semantic_receipt.get("state") == "completed"
        else None
    )
    if args.reference_semantic_receipt is not None:
        reference_receipt = _json(args.reference_semantic_receipt.resolve())
        parity = compare_semantic_surfaces(
            (
                semantic_surface_from_execution_receipt(reference_receipt),
                current_surface or {},
            )
        )
    else:
        parity = {
            "semantic_parity": None,
            "state": "awaiting_prior_successful_or_resumed exact-0008 receipt",
            "fixture_parity_required": True,
            "failed_serial_baseline_has_no_semantic_output_identity": True,
        }
    process_execution = _process_parallelism(semantic_receipt)

    strict_completed = strict_receipt.get("state") in {"completed", "calibrated"}
    rollback_verified = (
        strict_receipt.get("publication_verification", {}).get("publication_mode")
        == "rolled_back"
    )
    accepted = (
        strict_completed
        and rollback_verified
        and semantic_receipt.get("state") == "completed"
        and process_execution["parallel_process_execution_observed"]
        and parity.get("semantic_parity") is not False
    )
    report = {
        **started,
        "state": "accepted" if accepted else "failed",
        "accepted": accepted,
        "child_returncode": completed.returncode,
        "strict_receipt": str(strict_receipt_path),
        "semantic_receipt": str(semantic_receipt_path),
        "runtime_comparison": runtime_comparison,
        "process_execution": process_execution,
        "semantic_parity": parity,
        "semantic_surface": current_surface,
        "publication_verification": strict_receipt.get("publication_verification"),
        "parser_checkpoint_reuse_policy": (
            "same output/state path and parser_workers=1 retain exact checkpoint identity"
        ),
    }
    _atomic_json(report_path, report)
    print(json.dumps({"report": str(report_path), **report}, sort_keys=True))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
