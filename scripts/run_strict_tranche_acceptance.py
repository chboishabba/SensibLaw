#!/usr/bin/env python3
"""Run the canonical tranche pipeline under a recorded strict memory contract.

This wrapper does not implement compilation.  It launches
``scripts/run_complete_tranche.py`` with a reproducible environment, samples the
entire process tree, and writes an atomic acceptance receipt.  A non-zero child
exit, missing resource receipt after a memory breach, or observed RSS above the
hard limit fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tranche", required=True, choices=("GWB", "AU", "BREXIT", "ALL")
    )
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL"), required=False
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--soft-memory-mib", type=int, default=512)
    parser.add_argument("--hard-memory-mib", type=int, default=576)
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    parser.add_argument("--max-source-files", type=int)
    parser.add_argument("--max-file-bytes", type=int)
    parser.add_argument(
        "--input-path",
        type=Path,
        action="append",
        help="Explicit source file or directory forwarded to the canonical runner.",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-legal-follow", action="store_true")
    parser.add_argument("--document-workers", type=int, default=1)
    parser.add_argument("--closure-workers", type=int, default=4)
    parser.add_argument("--owner-partitions", type=int, default=8)
    parser.add_argument("--parser-workers", type=int, default=2)
    parser.add_argument("--worker-budget", type=int, default=4)
    parser.add_argument(
        "--calibration",
        action="store_true",
        help=(
            "Run the local compiler and persistence path inside one rolled-back "
            "transaction and emit a non-publishing calibration receipt."
        ),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.soft_memory_mib < 1:
        parser.error("--soft-memory-mib must be positive")
    if args.hard_memory_mib <= args.soft_memory_mib:
        parser.error("--hard-memory-mib must exceed --soft-memory-mib")
    if args.sample_seconds <= 0:
        parser.error("--sample-seconds must be positive")
    return args


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _git_value(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _migration_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    migration_root = ROOT / "database" / "postgres_migrations"
    for path in sorted(migration_root.glob("*.sql")):
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _process_memory(pid: int) -> dict[str, int | None]:
    """Read Linux RSS/PSS/USS; PSS/USS are unavailable without smaps_rollup."""

    result: dict[str, int | None] = {
        "rss_bytes": None,
        "pss_bytes": None,
        "uss_bytes": None,
    }
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(":")
            if key == "Rss":
                result["rss_bytes"] = int(value.split()[0]) * 1024
            elif key == "Pss":
                result["pss_bytes"] = int(value.split()[0]) * 1024
            elif key in {"Private_Clean", "Private_Dirty"}:
                result["uss_bytes"] = (result["uss_bytes"] or 0) + int(value.split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        try:
            pages = int(Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()[1])
            result["rss_bytes"] = pages * int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, IndexError):
            pass
    return result


def _child_pids(pid: int) -> tuple[int, ...]:
    result: list[int] = []
    pending = [pid]
    seen = {pid}
    while pending:
        parent = pending.pop()
        try:
            direct = tuple(
                int(value)
                for value in Path(f"/proc/{parent}/task/{parent}/children")
                .read_text(encoding="ascii")
                .split()
            )
        except (OSError, ValueError):
            direct = ()
        for child in direct:
            if child in seen:
                continue
            seen.add(child)
            result.append(child)
            pending.append(child)
    return tuple(result)


def _process_tree_memory(pid: int) -> dict[str, int | None]:
    rows = [_process_memory(candidate) for candidate in (pid, *_child_pids(pid))]
    result: dict[str, int | None] = {}
    for key in ("rss_bytes", "pss_bytes", "uss_bytes"):
        values = [value for row in rows if (value := row[key]) is not None]
        result[key] = sum(values) if values else None
    return result


def _round_up(value: int, quantum: int = 64 * MIB) -> int:
    return ((value + quantum - 1) // quantum) * quantum


def _derived_limits(peak_resources: Mapping[str, int]) -> dict[str, dict[str, int]]:
    """Derive declared limits from an observed clean calibration peak."""

    return {
        key.removesuffix("_bytes"): {
            "observed_peak_bytes": value,
            "soft_limit_bytes": _round_up((value * 105 + 99) // 100),
            "hard_limit_bytes": _round_up((value * 120 + 99) // 100),
        }
        for key, value in peak_resources.items()
        if value > 0
    }


def _command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_complete_tranche.py"),
        "--tranche",
        args.tranche,
        "--database-url",
        args.database_url,
        "--output-root",
        str(args.output_root),
        "--document-workers",
        str(args.document_workers),
        "--closure-workers",
        str(args.closure_workers),
        "--owner-partitions",
        str(args.owner_partitions),
        "--parser-workers",
        str(args.parser_workers),
        "--worker-budget",
        str(args.worker_budget),
    ]
    if args.max_source_files is not None:
        command.extend(("--max-source-files", str(args.max_source_files)))
    if args.max_file_bytes is not None:
        command.extend(("--max-file-bytes", str(args.max_file_bytes)))
    for path in args.input_path or ():
        command.extend(("--input-path", str(path.resolve())))
    if args.offline:
        command.append("--offline")
    if args.skip_legal_follow:
        command.append("--skip-legal-follow")
    if args.calibration:
        command.append("--calibration")
    return command


def _verify_explicit_publication(args: argparse.Namespace) -> dict[str, Any]:
    """Verify one explicit source reached the final publication boundary."""

    input_paths = tuple(path.resolve() for path in args.input_path or ())
    if not input_paths:
        return {"state": "not_requested"}
    if any(not path.is_file() for path in input_paths):
        return {
            "state": "not_verified",
            "reason": "publication verification requires explicit files",
        }

    output_dir = args.output_root.resolve() / args.tranche.lower()
    projection_path = output_dir / "source_projection" / "manifest.json"
    compilation_path = output_dir / "local_pnf_compilation.json"
    if not projection_path.exists() or not compilation_path.exists():
        return {
            "state": "not_verified",
            "reason": "missing projection or compilation receipt",
        }
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    compilation = json.loads(compilation_path.read_text(encoding="utf-8"))
    expected_hashes = sorted(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths
    )
    projected_hashes = sorted(
        str(row.get("raw_sha256") or "")
        for row in projection.get("documents") or ()
        if isinstance(row, Mapping)
    )
    document_refs = tuple(
        str(value) for value in compilation.get("document_refs") or ()
    )
    if projected_hashes != expected_hashes or len(document_refs) != len(input_paths):
        return {
            "state": "not_verified",
            "reason": "source projection or compiled document count disagrees with explicit input",
            "expected_raw_sha256": expected_hashes,
            "projected_raw_sha256": projected_hashes,
            "document_refs": list(document_refs),
        }

    try:
        import psycopg

        with psycopg.connect(args.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document_ref, occurrence_state
                    FROM corpus.document_occurrence
                    WHERE corpus_ref = %s AND document_ref = ANY(%s)
                    ORDER BY document_ref
                    """,
                    (str(compilation["corpus_ref"]), list(document_refs)),
                )
                occurrences = [(str(row[0]), str(row[1])) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT document_ref, COUNT(*)
                    FROM execution.document_compilation_build
                    WHERE document_ref = ANY(%s)
                    GROUP BY document_ref
                    ORDER BY document_ref
                    """,
                    (list(document_refs),),
                )
                builds = [(str(row[0]), int(row[1])) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT document_ref, COUNT(*), BOOL_AND(octet_length(ordered_digest) = 32)
                    FROM execution.artifact_manifest
                    WHERE document_ref = ANY(%s)
                    GROUP BY document_ref
                    ORDER BY document_ref
                    """,
                    (list(document_refs),),
                )
                manifests = [
                    (str(row[0]), int(row[1]), bool(row[2]))
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT document_ref, COUNT(*)
                    FROM execution.document_projection_manifest
                    WHERE document_ref = ANY(%s)
                    GROUP BY document_ref
                    ORDER BY document_ref
                    """,
                    (list(document_refs),),
                )
                projections = [(str(row[0]), int(row[1])) for row in cursor.fetchall()]
    except Exception as error:
        return {
            "state": "not_verified",
            "reason": f"database verification failed: {error}",
        }

    expected_refs = sorted(document_refs)
    verified = (
        sorted(row[0] for row in occurrences) == expected_refs
        and all(state == "compiled" for _ref, state in occurrences)
        and builds == [(ref, 1) for ref in expected_refs]
        and len(manifests) == len(expected_refs)
        and all(count > 0 and digest_valid for _ref, count, digest_valid in manifests)
        and projections == [(ref, 1) for ref in expected_refs]
    )
    return {
        "state": "verified" if verified else "not_verified",
        "corpus_ref": compilation["corpus_ref"],
        "document_refs": list(document_refs),
        "occurrences": occurrences,
        "builds": builds,
        "artifact_manifests": manifests,
        "projection_manifests": projections,
        "expected_raw_sha256": expected_hashes,
    }


def main() -> int:
    args = _parse_args()
    acceptance_root = args.acceptance_root.resolve()
    acceptance_root.mkdir(parents=True, exist_ok=True)
    checkpoints = acceptance_root / "resource-checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    stdout_path = acceptance_root / "stdout.log"
    stderr_path = acceptance_root / "stderr.log"
    rss_path = acceptance_root / "rss.jsonl"
    receipt_path = acceptance_root / "acceptance-receipt.json"

    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": args.database_url,
            "SENSIBLAW_DOCUMENT_RETENTION_MODE": "production_compact",
            "SENSIBLAW_RESOURCE_CHECKPOINT_DIR": str(checkpoints),
            "SENSIBLAW_RESOURCE_CHECKPOINT_ALL": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    if args.calibration:
        # Calibration observes the complete curve. The compiler's ordinary
        # 5/6 GiB diagnostic guard remains a last-resort safety boundary, but
        # the historical acceptance cap must not truncate the measurement.
        environment.pop("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", None)
        environment.pop("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", None)
    else:
        environment.update(
            {
                "SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB": str(args.soft_memory_mib),
                "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB": str(args.hard_memory_mib),
            }
        )
    command = _command(args)
    started_at = datetime.now(UTC).isoformat()
    peak_resources = {"rss_bytes": 0, "pss_bytes": 0, "uss_bytes": 0}
    sample_count = 0
    hard_limit = args.hard_memory_mib * MIB
    observed_hard_breach = False

    _atomic_json(
        receipt_path,
        {
            "schema_version": "sl.strict_tranche_acceptance.v0_2",
            "state": "started",
            "accepted": False,
            "started_at": started_at,
            "command": command,
        },
    )
    process: subprocess.Popen[bytes] | None = None
    stop = threading.Event()
    terminal_signal: int | None = None
    returncode: int | None = None

    def _signal_handler(signum: int, _frame: Any) -> None:
        nonlocal terminal_signal
        terminal_signal = signum
        if process is not None and process.poll() is None:
            process.terminate()

    old_handlers = {
        signum: signal.signal(signum, _signal_handler)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)

            def sample() -> None:
                nonlocal sample_count, observed_hard_breach
                assert process is not None
                with rss_path.open("a", encoding="utf-8") as stream:
                    while not stop.wait(args.sample_seconds):
                        resources = _process_tree_memory(process.pid)
                        for key, value in resources.items():
                            if value is not None:
                                peak_resources[key] = max(peak_resources[key], value)
                        sample_count += 1
                        observed_hard_breach = observed_hard_breach or (resources["rss_bytes"] or 0) > hard_limit
                        stream.write(
                            json.dumps(
                                {
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "pid": process.pid,
                                    "process_tree_rss_bytes": resources["rss_bytes"],
                                    "process_tree_pss_bytes": resources["pss_bytes"],
                                    "process_tree_uss_bytes": resources["uss_bytes"],
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        stream.flush()

            sampler = threading.Thread(target=sample, name="acceptance-memory", daemon=True)
            sampler.start()
            returncode = process.wait()
            stop.set()
            sampler.join(timeout=max(1.0, args.sample_seconds * 2))
    finally:
        stop.set()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    checkpoint_files = sorted(
        str(path.relative_to(acceptance_root)) for path in checkpoints.glob("*.json")
    )
    run_succeeded = (
        returncode == 0
        and terminal_signal is None
        and (args.calibration or not observed_hard_breach)
    )
    accepted = not args.calibration and run_succeeded
    failure_reason = None
    if args.calibration and run_succeeded:
        failure_reason = None
    elif terminal_signal is not None:
        failure_reason = f"acceptance harness received signal {terminal_signal}"
    elif returncode != 0:
        failure_reason = f"tranche runner exited with status {returncode}"
    elif observed_hard_breach:
        failure_reason = "observed process-tree RSS exceeded the hard limit"
    if observed_hard_breach and not checkpoint_files:
        accepted = False
        failure_reason = "hard memory breach had no resource checkpoint"
    publication = (
        {"state": "not_requested", "publication_mode": "rolled_back"}
        if args.calibration
        else (_verify_explicit_publication(args) if returncode == 0 else {"state": "not_run"})
    )
    if not args.calibration and publication["state"] == "not_verified":
        accepted = False
        failure_reason = "explicit input publication verification failed"

    receipt = {
        "schema_version": "sl.strict_tranche_acceptance.v0_2",
        "state": (
            "calibrated"
            if args.calibration and run_succeeded
            else ("completed" if accepted else ("signalled" if terminal_signal is not None else "failed"))
        ),
        "accepted": accepted,
        "failure_reason": failure_reason,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "command": command,
        "returncode": returncode,
        "signal": terminal_signal,
        "repository": {
            "commit": _git_value("rev-parse", "HEAD"),
            "branch": _git_value("branch", "--show-current"),
            "status_porcelain": _git_value("status", "--porcelain"),
        },
        "environment": {
            key: environment.get(key)
            for key in (
                "SENSIBLAW_DOCUMENT_RETENTION_MODE",
                "SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB",
                "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB",
                "SENSIBLAW_RESOURCE_CHECKPOINT_DIR",
                "SENSIBLAW_RESOURCE_CHECKPOINT_ALL",
            )
        },
        "database_url_redacted": args.database_url.split("@")[-1],
        "explicit_input_paths": [
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else None,
            }
            for path in args.input_path or ()
        ],
        "migration_sha256": _migration_hashes(),
        "publication_verification": publication,
        "resources": {
            "sample_count": sample_count,
            "peak_process_tree_rss_bytes": peak_resources["rss_bytes"],
            "peak_process_tree_pss_bytes": peak_resources["pss_bytes"],
            "peak_process_tree_uss_bytes": peak_resources["uss_bytes"],
            "soft_limit_bytes": args.soft_memory_mib * MIB,
            "hard_limit_bytes": hard_limit,
            "hard_limit_observed": observed_hard_breach,
        },
        "calibration": (
            {
                "publication_mode": "rolled_back",
                "derived_limits": _derived_limits(peak_resources),
                "trial_count": 1,
                "minimum_required_trials": 3,
                "state": "single_trial_requires_two_matching_repeats",
            }
            if args.calibration
            else None
        ),
        "artifacts": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "rss_samples": str(rss_path),
            "resource_checkpoints": checkpoint_files,
            "tranche_output_root": str(args.output_root.resolve()),
        },
    }
    _atomic_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if run_succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
