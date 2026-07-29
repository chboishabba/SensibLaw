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


def _resident_bytes(pid: int) -> int:
    try:
        pages = int(Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()[1])
        return pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        return 0


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


def _process_tree_rss(pid: int) -> int:
    return _resident_bytes(pid) + sum(
        _resident_bytes(child) for child in _child_pids(pid)
    )


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
            "SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB": str(args.soft_memory_mib),
            "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB": str(args.hard_memory_mib),
            "SENSIBLAW_RESOURCE_CHECKPOINT_DIR": str(checkpoints),
            "PYTHONUNBUFFERED": "1",
        }
    )
    command = _command(args)
    started_at = datetime.now(UTC).isoformat()
    peak_rss = 0
    sample_count = 0
    hard_limit = args.hard_memory_mib * MIB
    observed_hard_breach = False

    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        stop = threading.Event()

        def sample() -> None:
            nonlocal peak_rss, sample_count, observed_hard_breach
            with rss_path.open("a", encoding="utf-8") as stream:
                while not stop.wait(args.sample_seconds):
                    rss = _process_tree_rss(process.pid)
                    peak_rss = max(peak_rss, rss)
                    sample_count += 1
                    observed_hard_breach = observed_hard_breach or rss > hard_limit
                    stream.write(
                        json.dumps(
                            {
                                "observed_at": datetime.now(UTC).isoformat(),
                                "pid": process.pid,
                                "process_tree_rss_bytes": rss,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    stream.flush()

        sampler = threading.Thread(target=sample, name="acceptance-rss", daemon=True)
        sampler.start()
        returncode = process.wait()
        stop.set()
        sampler.join(timeout=max(1.0, args.sample_seconds * 2))

    checkpoint_files = sorted(
        str(path.relative_to(acceptance_root)) for path in checkpoints.glob("*.json")
    )
    accepted = returncode == 0 and not observed_hard_breach
    failure_reason = None
    if returncode != 0:
        failure_reason = f"tranche runner exited with status {returncode}"
    elif observed_hard_breach:
        failure_reason = "observed process-tree RSS exceeded the hard limit"
    if observed_hard_breach and not checkpoint_files:
        accepted = False
        failure_reason = "hard memory breach had no resource checkpoint"
    publication = (
        _verify_explicit_publication(args) if returncode == 0 else {"state": "not_run"}
    )
    if publication["state"] == "not_verified":
        accepted = False
        failure_reason = "explicit input publication verification failed"

    receipt = {
        "schema_version": "sl.strict_tranche_acceptance.v0_1",
        "accepted": accepted,
        "failure_reason": failure_reason,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "command": command,
        "returncode": returncode,
        "repository": {
            "commit": _git_value("rev-parse", "HEAD"),
            "branch": _git_value("branch", "--show-current"),
            "status_porcelain": _git_value("status", "--porcelain"),
        },
        "environment": {
            key: environment[key]
            for key in (
                "SENSIBLAW_DOCUMENT_RETENTION_MODE",
                "SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB",
                "SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB",
                "SENSIBLAW_RESOURCE_CHECKPOINT_DIR",
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
            "peak_process_tree_rss_bytes": peak_rss,
            "soft_limit_bytes": args.soft_memory_mib * MIB,
            "hard_limit_bytes": hard_limit,
            "hard_limit_observed": observed_hard_breach,
        },
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
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
