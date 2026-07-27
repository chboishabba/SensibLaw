#!/usr/bin/env python3
"""Benchmark one document with serial and bounded parallel graph execution.

This harness measures the actual acceptance objective: time from one canonical
text input to one complete document-local operational compilation.  It runs each
worker budget in an isolated process, compares authoritative semantic artefact
fingerprints, and retains operator receipts plus the semantic timing ledger.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from time import monotonic_ns
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.carriers.canonical import canonical_sha256  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.operational_corpus_compilation import (  # noqa: E402
    compile_document_operational,
)


BENCHMARK_SCHEMA_VERSION = "sl.document_graph_execution_benchmark.v0_1"
_EXECUTION_ONLY_KEYS = {
    "licensing_execution_receipt",
    "projection_receipt",
}
_SEMANTIC_ARTIFACT_KEYS = (
    "canonical_text_sha256",
    "licensing",
    "recurrence",
    "forms",
    "local_typing",
    "structural_type_hypotheses",
    "unresolved_span_diagnostics",
    "annotation_layer",
    "annotation_graph",
    "semantic_annotation_layer",
    "relational_bundle",
    "semantic_reduction_constraints",
    "constraint_assessments",
    "local_evidence",
    "local_meet_plan",
    "pnf_graph",
    "refined_pnf_graph",
    "resolution_demands",
    "typed_meets",
    "factor_refinements",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--parallel-workers", type=int, default=4)
    parser.add_argument("--serial-workers", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--parser-limit-chars", type=int, default=1_000_000)
    parser.add_argument("--parser-target-chars", type=int, default=400_000)
    parser.add_argument("--parser-overlap-chars", type=int, default=8_192)
    parser.add_argument("--_worker-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_worker-count", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--_result-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.parallel_workers < 1 or args.serial_workers < 1:
        parser.error("worker counts must be positive")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args._worker_run and (args._worker_count is None or args._result_file is None):
        parser.error("worker mode requires --_worker-count and --_result-file")
    return args


def _strip_execution(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_execution(item)
            for key, item in value.items()
            if str(key) not in _EXECUTION_ONLY_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_execution(item) for item in value]
    return value


def _semantic_payload(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _strip_execution(artifacts[key])
        for key in _SEMANTIC_ARTIFACT_KEYS
        if key in artifacts
    }


def _compile_once(args: argparse.Namespace) -> int:
    input_path = args.input_file.resolve()
    text = input_path.read_text(encoding="utf-8")
    content_sha256 = sha256(text.encode("utf-8")).hexdigest()
    worker_count = int(args._worker_count)
    os.environ["SENSIBLAW_DOCUMENT_WORKERS"] = str(worker_count)

    started_ns = monotonic_ns()
    compilation = compile_document_operational(
        {
            "document_ref": f"document:benchmark:{content_sha256}",
            "content_sha256": content_sha256,
            "media_type": "text/plain",
            "canonical_text": text,
            "source_ref": f"document-source:benchmark:{content_sha256}",
        },
        default_compiler_context(),
        closure_workers=worker_count,
        owner_partitions=max(1, worker_count * 2),
        parser_workers=worker_count,
        parser_limit_chars=args.parser_limit_chars,
        parser_target_chars=args.parser_target_chars,
        parser_overlap_chars=args.parser_overlap_chars,
    )
    elapsed_ms = max(0, (monotonic_ns() - started_ns) // 1_000_000)
    artifacts = compilation.artifacts
    semantic_payload = _semantic_payload(artifacts)
    licensing = artifacts.get("licensing") or {}
    relational_bundle = artifacts.get("relational_bundle") or {}
    result = {
        "worker_count": worker_count,
        "elapsed_ms": elapsed_ms,
        "semantic_fingerprint": canonical_sha256(semantic_payload),
        "semantic_stage_timing": artifacts.get("semantic_stage_timing") or {},
        "mention_execution_receipt": licensing.get(
            "licensing_execution_receipt"
        ),
        "projection_execution_receipt": relational_bundle.get(
            "projection_receipt"
        ),
        "semantic_counts": {
            "mentions": len(licensing.get("mentions") or ()),
            "relations": len(relational_bundle.get("relations") or ()),
            "factors": len(
                (artifacts.get("refined_pnf_graph") or {}).get("factors") or ()
            ),
            "constraints": len(
                (artifacts.get("refined_pnf_graph") or {}).get("constraints") or ()
            ),
            "demands": len(artifacts.get("resolution_demands") or ()),
        },
    }
    args._result_file.parent.mkdir(parents=True, exist_ok=True)
    args._result_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _isolated_run(
    args: argparse.Namespace,
    *,
    workers: int,
    result_path: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(args.input_file.resolve()),
        "--_worker-run",
        "--_worker-count",
        str(workers),
        "--_result-file",
        str(result_path),
        "--parser-limit-chars",
        str(args.parser_limit_chars),
        "--parser-target-chars",
        str(args.parser_target_chars),
        "--parser-overlap-chars",
        str(args.parser_overlap_chars),
    ]
    subprocess.run(command, check=True)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("isolated benchmark result must be a JSON object")
    return payload


def _summarise_runs(
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = sorted(runs, key=lambda row: int(row["elapsed_ms"]))
    representative = ordered[len(ordered) // 2]
    return {
        **representative,
        "elapsed_ms_samples": [int(row["elapsed_ms"]) for row in runs],
        "median_elapsed_ms": median(int(row["elapsed_ms"]) for row in runs),
        "fingerprints": sorted(
            {str(row["semantic_fingerprint"]) for row in runs}
        ),
    }


def _run_benchmark(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="sensiblaw-document-graph-benchmark-") as raw:
        temp_dir = Path(raw)
        serial_runs = [
            _isolated_run(
                args,
                workers=args.serial_workers,
                result_path=temp_dir / f"serial-{index}.json",
            )
            for index in range(args.repeats)
        ]
        parallel_runs = [
            _isolated_run(
                args,
                workers=args.parallel_workers,
                result_path=temp_dir / f"parallel-{index}.json",
            )
            for index in range(args.repeats)
        ]

    serial = _summarise_runs(serial_runs)
    parallel = _summarise_runs(parallel_runs)
    serial_fingerprints = set(serial["fingerprints"])
    parallel_fingerprints = set(parallel["fingerprints"])
    parity = (
        len(serial_fingerprints) == 1
        and serial_fingerprints == parallel_fingerprints
    )
    serial_ms = float(serial["median_elapsed_ms"])
    parallel_ms = float(parallel["median_elapsed_ms"])
    payload = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "input_file": str(args.input_file.resolve()),
        "input_bytes": args.input_file.stat().st_size,
        "serial": serial,
        "parallel": parallel,
        "semantic_fingerprint_parity": parity,
        "speedup": round(serial_ms / parallel_ms, 4) if parallel_ms > 0 else None,
        "elapsed_ms_saved": serial_ms - parallel_ms,
        "acceptance": {
            "semantic_parity": parity,
            "parallel_faster": parallel_ms < serial_ms,
            "worker_budget_observed": bool(
                parallel.get("mention_execution_receipt")
                or parallel.get("projection_execution_receipt")
            ),
            "accepted": parity and parallel_ms < serial_ms,
        },
        "authority": "execution_benchmark_only",
    }
    output = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if parity else 2


def main() -> int:
    args = _parse_args()
    if args._worker_run:
        return _compile_once(args)
    return _run_benchmark(args)


if __name__ == "__main__":
    raise SystemExit(main())
