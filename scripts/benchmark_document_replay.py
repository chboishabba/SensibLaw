#!/usr/bin/env python3
"""Benchmark bounded document replay without creating another compiler path."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import pickle
from pprint import pformat
import subprocess
import sys
from time import monotonic_ns
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.semantic_parity import (  # noqa: E402
    canonical_stream_digest,
    compare_semantic_surfaces,
    semantic_surface_from_execution_receipt,
)
from scripts.run_exact_0008_parallel_acceptance import _json as read_report  # noqa: E402


SCHEMA_VERSION = "sensiblaw.document-replay-benchmark.v1"
MODES = ("full", "batched", "disabled")


@dataclass(frozen=True)
class DocumentCase:
    label: str
    path: Path


def _mapping(path: Path) -> dict[str, Any]:
    return read_report(path)


def load_manifest(path: Path) -> tuple[DocumentCase, ...]:
    payload = pickle.loads(path.read_bytes())
    rows = payload.get("documents") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("manifest must contain a non-empty documents list")
    cases: list[DocumentCase] = []
    labels: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("manifest document rows must be mappings")
        label = str(row.get("label") or "").strip()
        raw_path = str(row.get("path") or "").strip()
        if not label or not raw_path:
            raise ValueError("each manifest row requires label and path")
        if label in labels:
            raise ValueError(f"duplicate document label: {label}")
        document = Path(raw_path).expanduser().resolve()
        if not document.is_file():
            raise FileNotFoundError(document)
        labels.add(label)
        cases.append(DocumentCase(label=label, path=document))
    return tuple(cases)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _typed(path: Path) -> dict[str, Any]:
    if path.suffix == ".pkl":
        value = pickle.loads(path.read_bytes())
        if not isinstance(value, Mapping):
            raise ValueError(f"expected typed mapping: {path}")
        return dict(value)
    return _mapping(path)


def _find_semantic_receipt(root: Path) -> Path | None:
    for name in ("semantic-execution-receipt.pkl", "semantic-execution-receipt.json"):
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _kernel_seconds(receipt: Mapping[str, Any], prefix: str) -> float:
    total = 0
    for row in receipt.get("kernel_timeline") or ():
        if not isinstance(row, Mapping):
            continue
        if row.get("phase") == "kernel_completed" and str(
            row.get("stage", "")
        ).startswith(prefix):
            total += int(row.get("elapsed_ns") or 0)
    return total / 1_000_000_000


def _metrics(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    value = pickle.loads(path.read_bytes())
    return {str(key): int(item) for key, item in dict(value).items()}


def _command(
    *,
    case: DocumentCase,
    mode: str,
    run_root: Path,
    database_url: str,
    postgres_mode: str,
    tranche: str,
    strict_exact: bool,
    owner_partitions: int,
) -> list[str]:
    acceptance_root = run_root / "acceptance" / f"{case.label}-{mode}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_exact_0008_parallel_acceptance.py"),
        "--database-url",
        database_url,
        "--postgres-mode",
        postgres_mode,
        "--input-path",
        str(case.path),
        "--output-root",
        str(run_root / "output"),
        "--acceptance-root",
        str(acceptance_root),
        "--semantic-checkpoint-root",
        str(run_root / "semantic-checkpoints"),
        "--owner-partitions",
        str(owner_partitions),
        "--tranche",
        tranche,
    ]
    if strict_exact:
        command.append("--strict-exact")
    return command


def _run_case(
    *,
    case: DocumentCase,
    mode: str,
    output_root: Path,
    database_url: str,
    postgres_mode: str,
    tranche: str,
    strict_exact: bool,
    owner_partitions: int,
    batch_events: int,
    batch_seconds: float,
    reference_receipt: Path | None,
    py_spy_output: Path | None,
) -> dict[str, Any]:
    run_root = output_root / case.label / mode
    if run_root.exists():
        raise FileExistsError(
            f"benchmark output already exists; choose a new output root: {run_root}"
        )
    run_root.mkdir(parents=True)
    command = _command(
        case=case,
        mode=mode,
        run_root=run_root,
        database_url=database_url,
        postgres_mode=postgres_mode,
        tranche=tranche,
        strict_exact=strict_exact,
        owner_partitions=owner_partitions,
    )
    if reference_receipt is not None:
        command.extend(("--reference-semantic-receipt", str(reference_receipt)))
    environment = os.environ.copy()
    environment.update(
        {
            "SENSIBLAW_PROGRESS_PERSISTENCE_MODE": mode,
            "SENSIBLAW_PROGRESS_BATCH_EVENTS": str(batch_events),
            "SENSIBLAW_PROGRESS_BATCH_SECONDS": str(batch_seconds),
            "PYTHONUNBUFFERED": "1",
        }
    )
    if py_spy_output is not None:
        command = [
            "py-spy",
            "record",
            "--subprocesses",
            "--output",
            str(py_spy_output),
            "--",
            *command,
        ]
    started_ns = monotonic_ns()
    stdout_path = run_root / "stdout.log"
    stderr_path = run_root / "stderr.log"
    with (
        stdout_path.open("w", encoding="utf-8") as stdout,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    wall_ns = monotonic_ns() - started_ns
    semantic_root = run_root / "semantic-checkpoints"
    receipt_path = _find_semantic_receipt(semantic_root)
    receipt = _typed(receipt_path) if receipt_path is not None else {}
    strict_path = (
        run_root
        / "acceptance"
        / f"{case.label}-{mode}"
        / "strict"
        / "acceptance-receipt.json"
    )
    strict = _mapping(strict_path) if strict_path.exists() else {}
    metrics = _metrics(semantic_root / "progress" / "metrics.pkl")
    closure_audit = dict(receipt.get("closure_audit") or {})
    owner_reduction = {
        key: closure_audit.get(key)
        for key in (
            "jobs_completed",
            "proposals_emitted",
            "materialized_factors",
            "proposals_examined_per_emitted",
            "factor_scans_per_changed_factor",
            "handoff_compact_checkpoints",
            "handoff_compact_checkpoint_ns",
            "handoff_checkpoint_replay_rows_serialized",
        )
    }
    surface = (
        semantic_surface_from_execution_receipt(receipt)
        if receipt.get("state") == "completed"
        else None
    )
    return {
        "label": case.label,
        "input_path": str(case.path),
        "input_sha256": _sha256(case.path),
        "mode": mode,
        "returncode": completed.returncode,
        "completed": receipt.get("state") == "completed",
        "wall_seconds": wall_ns / 1_000_000_000,
        "kernel_seconds": {
            "local_typing": _kernel_seconds(receipt, "local_typing_diagnostics:"),
            "closure": _kernel_seconds(receipt, "streaming_closure:"),
        },
        "resources": dict(strict.get("resources") or {}),
        "process_execution": dict(strict.get("process_execution") or {}),
        "owner_reduction": owner_reduction,
        "persistence": metrics,
        "semantic_receipt": str(receipt_path) if receipt_path else None,
        "semantic_surface_digest": canonical_stream_digest(surface)
        if surface
        else None,
        "artifacts": {
            "run_root": str(run_root),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Typed binary manifest containing {documents: [{label, path}, ...]}.",
    )
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument(
        "--postgres-mode", choices=("local", "existing"), default="existing"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, action="append", dest="modes")
    parser.add_argument("--tranche", default="GWB")
    parser.add_argument("--strict-exact", action="store_true")
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--batch-events", type=int, default=32)
    parser.add_argument("--batch-seconds", type=float, default=1.0)
    parser.add_argument("--py-spy", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")
    if args.batch_events < 1 or args.batch_seconds <= 0:
        raise SystemExit("batch thresholds must be positive")
    cases = load_manifest(args.manifest.resolve())
    modes = tuple(args.modes or MODES)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for case in cases:
        reference_receipt: Path | None = None
        for mode in modes:
            profile = None
            if args.py_spy and mode == "full":
                profile = output_root / case.label / "full.speedscope.json"
            row = _run_case(
                case=case,
                mode=mode,
                output_root=output_root,
                database_url=args.database_url,
                postgres_mode=args.postgres_mode,
                tranche=args.tranche,
                strict_exact=args.strict_exact,
                owner_partitions=args.owner_partitions,
                batch_events=args.batch_events,
                batch_seconds=args.batch_seconds,
                reference_receipt=reference_receipt,
                py_spy_output=profile,
            )
            if row["completed"] and reference_receipt is None:
                reference_receipt = Path(str(row["semantic_receipt"]))
            if reference_receipt is not None and row["semantic_receipt"]:
                current = _typed(Path(str(row["semantic_receipt"])))
                reference = _typed(reference_receipt)
                row["parity"] = compare_semantic_surfaces(
                    (
                        semantic_surface_from_execution_receipt(reference),
                        semantic_surface_from_execution_receipt(current),
                    )
                )
            else:
                row["parity"] = {"semantic_parity": None}
            rows.append(row)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "repository": {"root": str(ROOT)},
        "configuration": {
            "manifest": str(args.manifest.resolve()),
            "postgres_mode": args.postgres_mode,
            "modes": list(modes),
            "batch_events": args.batch_events,
            "batch_seconds": args.batch_seconds,
            "strict_exact": args.strict_exact,
        },
        "runs": rows,
    }
    report_path = output_root / "benchmark-report.pkl"
    report_path.write_bytes(pickle.dumps(report, protocol=5))
    print(pformat(report, sort_dicts=True))
    return 0 if all(row["completed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
