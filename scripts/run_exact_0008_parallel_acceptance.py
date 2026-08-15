#!/usr/bin/env python3
"""Run exact-0008 with four semantic workers and compare durable receipts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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
    parser.add_argument(
        "--postgres-mode", choices=("local", "existing"), default="local"
    )
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
    parser.add_argument(
        "--reference-acceptance-report",
        type=Path,
        help="Prior successful exact-0008 acceptance report for persistence parity.",
    )
    parser.add_argument(
        "--semantic-checkpoint-root",
        type=Path,
        help="Durable checkpoint root; defaults below --acceptance-root.",
    )
    parser.add_argument(
        "--inject-stop-boundary",
        choices=("activation", "owner", "receipt", "reduction"),
        help="Run one expected-stop subprocess, then resume from its checkpoint.",
    )
    parser.add_argument("--inject-stop-after", type=int, default=1)
    parser.add_argument("--soft-memory-mib", type=int, default=6144)
    parser.add_argument("--hard-memory-mib", type=int, default=8192)
    parser.add_argument("--typing-workers", type=int, default=4)
    parser.add_argument("--typing-leaf-capacity", type=int, default=4096)
    parser.add_argument("--typing-arity", type=int, default=4)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--closure-activation-leaf-size", type=int, default=512)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument(
        "--parser-workers",
        type=int,
        default=1,
        help="Keep one to reuse the committed exact-0008 parser-fibre checkpoints.",
    )
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument(
        "--strict-exact",
        action="store_true",
        help="Use PostgreSQL leases/fences and committed finalisation evidence.",
    )
    parser.add_argument("--tranche", choices=("GWB", "AU", "BREXIT"), default="GWB")
    args = parser.parse_args()
    if args.postgres_mode == "existing" and not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.hard_memory_mib <= args.soft_memory_mib:
        parser.error("--hard-memory-mib must exceed --soft-memory-mib")
    for name in (
        "typing_workers",
        "typing_leaf_capacity",
        "closure_workers",
        "closure_activation_leaf_size",
        "owner_partitions",
        "parser_workers",
        "worker_budget",
        "inject_stop_after",
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
    activation = closure_counters.get("activation") or {}
    activation_pids = {
        int(pid) for pid in activation.get("worker_pids") or () if int(pid) > 0
    }
    activation_pids.update(
        int(str(key).split(":", maxsplit=1)[1])
        for key, value in closure_counters.items()
        if str(key).startswith("activation_worker_pid:") and int(value or 0) > 0
    )
    observed = typing_pids | closure_pids | activation_pids
    return {
        "typing_worker_pids": sorted(typing_pids),
        "closure_worker_pids": sorted(closure_pids),
        "closure_activation_worker_pids": sorted(activation_pids),
        "distinct_semantic_worker_pids": sorted(observed),
        "distinct_semantic_worker_count": len(observed),
        "parallel_process_execution_observed": len(observed) >= 2,
    }


def main() -> int:
    args = _parse_args()
    acceptance_root = args.acceptance_root.resolve()
    semantic_root = (
        args.semantic_checkpoint_root.resolve()
        if args.semantic_checkpoint_root is not None
        else acceptance_root / "semantic-checkpoints"
    )
    acceptance_root.mkdir(parents=True, exist_ok=True)
    baseline = _json(args.baseline.resolve())
    semantic_process_workers = max(args.typing_workers, args.closure_workers)

    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_strict_tranche_acceptance.py"),
        "--tranche",
        args.tranche,
        "--database-url",
        args.database_url or "",
        "--postgres-mode",
        args.postgres_mode,
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
    ]
    if not args.strict_exact:
        # Compatibility-only calibration path. Strict exact acceptance retains
        # a committed disposable database as authoritative evidence.
        command.append("--calibration")
    else:
        command.append("--strict-exact")
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": args.database_url,
            "PYTHONUNBUFFERED": "1",
            "SENSIBLAW_SEMANTIC_CHECKPOINT_DIR": str(semantic_root),
            "SENSIBLAW_TYPING_WORKERS": str(args.typing_workers),
            "SENSIBLAW_TYPING_LEAF_CAPACITY": str(args.typing_leaf_capacity),
            "SENSIBLAW_TYPING_HIERARCHY_ARITY": str(args.typing_arity),
            "SENSIBLAW_SEMANTIC_PROCESS_WORKERS": str(args.closure_workers),
            "SENSIBLAW_CLOSURE_ACTIVATION_LEAF_SIZE": str(
                args.closure_activation_leaf_size
            ),
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
            "closure_activation_leaf_size": args.closure_activation_leaf_size,
            "owner_partitions": args.owner_partitions,
            "parser_workers": args.parser_workers,
            "worker_budget": args.worker_budget,
            "semantic_process_workers": semantic_process_workers,
            "strict_exact": args.strict_exact,
        },
        "baseline": str(args.baseline.resolve()),
    }
    report_path = acceptance_root / "parallel-acceptance-comparison.json"
    _atomic_json(report_path, started)

    injected_stop: dict[str, Any] | None = None
    if args.inject_stop_boundary is not None:
        injection_names = {
            "activation": "SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION",
            "owner": "SENSIBLAW_CLOSURE_STOP_AFTER_OWNER_BATCH_ADMISSIONS",
            "receipt": "SENSIBLAW_CLOSURE_STOP_AFTER_RECEIPTS",
            "reduction": "SENSIBLAW_CLOSURE_STOP_AFTER_DIRTY_REDUCTIONS",
        }
        injected_environment = dict(environment)
        injected_environment[injection_names[args.inject_stop_boundary]] = str(
            args.inject_stop_after
        )
        injected = subprocess.run(
            command, cwd=ROOT, env=injected_environment, check=False
        )
        injected_semantic_path = semantic_root / "semantic-execution-receipt.json"
        injected_snapshot_path = acceptance_root / "injected-stop-semantic-receipt.json"
        if injected_semantic_path.exists():
            shutil.copyfile(injected_semantic_path, injected_snapshot_path)
        injected_stop = {
            "boundary": args.inject_stop_boundary,
            "stop_after": args.inject_stop_after,
            "returncode": injected.returncode,
            "expected_failure_observed": injected.returncode != 0,
            "semantic_receipt": (
                str(injected_snapshot_path) if injected_snapshot_path.exists() else None
            ),
        }
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
    calibration_path = (
        args.output_root.resolve() / args.tranche.lower() / "tranche_calibration.json"
    )
    calibration = _json(calibration_path) if calibration_path.exists() else {}
    rollback_counts = dict(calibration.get("rollback_row_counts") or {})
    rollback_counts_valid = (
        calibration.get("publication_mode") == "rolled_back"
        and int(rollback_counts.get("source_documents") or 0) == 1
        and int(rollback_counts.get("occurrences") or 0) == 1
        and int(rollback_counts.get("builds") or 0) == 1
        and int(rollback_counts.get("artifact_manifests") or 0) > 0
    )
    reference_report_path = args.reference_acceptance_report
    if reference_report_path is None and args.reference_semantic_receipt is not None:
        candidate = (
            args.reference_semantic_receipt.resolve().parent.parent
            / "parallel-acceptance-comparison.json"
        )
        if candidate.exists():
            reference_report_path = candidate
    reference_report = (
        _json(reference_report_path.resolve())
        if reference_report_path is not None
        else None
    )
    persistence_parity = reference_report is None or rollback_counts == dict(
        reference_report.get("rollback_verification", {}).get("row_counts") or {}
    )
    activation = (semantic_receipt.get("closure_audit") or {}).get("activation") or {}
    closure_jobs_completed = int(
        (semantic_receipt.get("closure_audit") or {}).get("jobs_completed") or 0
    )
    fixed_point = dict(activation.get("fixed_point_certificate") or {})
    fixed_point_verified = fixed_point.get("local_fixed_point") == "reached"
    resumed_required = args.inject_stop_boundary is not None
    resume_verified = not resumed_required or (
        bool(injected_stop and injected_stop["expected_failure_observed"])
        and int(activation.get("reused_leaf_count") or 0) > 0
        and (
            activation.get("owner_reconstructed") is True
            or args.inject_stop_boundary == "activation"
        )
    )
    parity_verified = (
        parity.get("semantic_parity") is True
        if args.reference_semantic_receipt is not None
        else current_surface is not None
    )
    resources = dict(strict_receipt.get("resources") or {})
    resource_verified = (
        int(resources.get("sample_count") or 0) > 0
        and int(resources.get("peak_process_tree_rss_bytes") or 0) > 0
        and resources.get("hard_limit_observed") is False
        and int(activation.get("max_buffered_leaves") or 0)
        <= int(activation.get("buffer_limit_leaves") or 0)
        and int(activation.get("activation_output_bytes") or 0) > 0
    )
    accepted = (
        strict_completed
        and rollback_verified
        and rollback_counts_valid
        and persistence_parity
        and semantic_receipt.get("state") == "completed"
        and process_execution["parallel_process_execution_observed"]
        and len(process_execution["closure_activation_worker_pids"]) >= 2
        and int(activation.get("leaf_count") or 0) > 0
        and int(activation.get("admitted_delta_count") or 0) > 0
        and activation.get("owner_admission_started_immediately") is True
        and activation.get("activation_owner_overlap_observed") is True
        and int(activation.get("ready_job_count") or 0) > 0
        and closure_jobs_completed > 0
        and fixed_point_verified
        and resource_verified
        and resume_verified
        and parity_verified
    )
    report = {
        **started,
        "state": "accepted" if accepted else "failed",
        "accepted": accepted,
        "failure_reason": strict_receipt.get("failure_reason")
        if not accepted
        else None,
        "diagnostic_path": strict_receipt.get("diagnostic_path")
        if not accepted
        else None,
        "kernel_key": strict_receipt.get("kernel_key") if not accepted else None,
        "child_returncode": completed.returncode,
        "strict_receipt": str(strict_receipt_path),
        "semantic_receipt": str(semantic_receipt_path),
        "runtime_comparison": runtime_comparison,
        "process_execution": process_execution,
        "semantic_parity": parity,
        "fixed_point_verified": fixed_point_verified,
        "resource_verified": resource_verified,
        "resume_verified": resume_verified,
        "injected_stop": injected_stop,
        "rollback_verification": {
            "state": "verified" if rollback_counts_valid else "failed",
            "row_counts": rollback_counts,
            "persistence_parity": persistence_parity,
            "calibration_receipt": str(calibration_path),
        },
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
