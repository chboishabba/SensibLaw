#!/usr/bin/env python3
"""Kill a coordinator while typed workers are actively computing.

The probe proves that spawned PostgreSQL workers arm ``PDEATHSIG`` before
opening their database sessions.  After the coordinator alone is killed, every
worker and multiprocessing descendant must exit.  Expired leases are then
fenced stale and reopened, and a replacement coordinator completes the same
stable jobs.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import pickle
import signal
import subprocess
import sys
import time
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.streaming_fixed_point import OwnerKey, SolverJob, SolverReceipt  # noqa: E402
from src.runtime.strict_postgres_execution import PostgresLeasedExecution  # noqa: E402
from src.storage.postgres import distributed_semantic_execution as execution  # noqa: E402
from src.storage.postgres.deterministic_admission_execution import (  # noqa: E402
    DeterministicAdmissionWorkerPool,
    install_deterministic_admission_execution,
)
from src.storage.postgres.distributed_semantic_execution import (  # noqa: E402
    ImmutableJobManifest,
    execute_serialized_streaming_job,
)
from src.storage.postgres.typed_execution_pool import (  # noqa: E402
    install_typed_execution_pool,
)
from src.storage.postgres.typed_process_supervision import (  # noqa: E402
    install_typed_process_supervision,
)


class ShortLeaseWorkerPool(DeterministicAdmissionWorkerPool):
    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        worker_count: int,
        execute: Any,
    ) -> None:
        super().__init__(
            database_url=database_url,
            run_ref=run_ref,
            worker_count=worker_count,
            execute=execute,
            lease_seconds=2,
        )


def _slow_execute(manifest: ImmutableJobManifest):
    marker_root = Path(os.environ["SENSIBLAW_TYPED_ACTIVE_MARKER_ROOT"])
    marker_root.mkdir(parents=True, exist_ok=True)
    (marker_root / f"worker-{os.getpid()}.active").touch()
    time.sleep(600)
    return execute_serialized_streaming_job(manifest)


def _connect(database_url: str) -> Any:
    import psycopg

    return psycopg.connect(database_url)


def _install() -> None:
    install_typed_execution_pool()
    install_typed_process_supervision()
    install_deterministic_admission_execution()
    execution.ProcessPostgresWorkerPool = ShortLeaseWorkerPool


def _manifests(
    *,
    run_ref: str,
    document_ref: str,
    owner_ref: str,
    count: int,
) -> tuple[ImmutableJobManifest, ...]:
    rows: list[ImmutableJobManifest] = []
    for ordinal in range(count):
        job = SolverJob(
            owner_key=OwnerKey(
                document_ref,
                f"scope:{ordinal}",
                "semantic.normative_relation",
            ),
            declaration_ref="declaration:typed-parent-death:v1",
            input_revision=0,
            input_refs=(f"observation:{ordinal}",),
            input_payload={"observation_delta": {"observations": ()}},
            rule_set_revision="rules:typed-parent-death:v1",
            coverage_requirements=("scope",),
        )
        rows.append(
            ImmutableJobManifest.build(
                job_ref=job.job_ref,
                run_ref=run_ref,
                document_ref=document_ref,
                owner_ref=owner_ref,
                input_revision=0,
                input_payload=job.to_dict(),
            )
        )
    return tuple(rows)


def _run(
    args: argparse.Namespace,
    *,
    execute: Any,
) -> list[tuple[int, str]]:
    _install()
    applied: list[tuple[int, str]] = []

    def apply(receipt: SolverReceipt, revision: int) -> None:
        applied.append((revision, receipt.job_ref))

    strategy = PostgresLeasedExecution(
        database_url=args.database_url,
        run_ref=args.run_ref,
        document_ref=args.document_ref,
        worker_count=args.workers,
        max_rounds=4,
    )
    strategy.run_frontier(
        _manifests(
            run_ref=args.run_ref,
            document_ref=args.document_ref,
            owner_ref=args.owner_ref,
            count=args.work_items,
        ),
        execute=execute,
        apply=apply,
        owner_ref=args.owner_ref,
    )
    return applied


def _descendants(pid: int) -> set[int]:
    path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        direct = {int(value) for value in path.read_text().split()}
    except (OSError, ValueError):
        return set()
    result = set(direct)
    for child in tuple(direct):
        result.update(_descendants(child))
    return result


def _wait_for_exit(pids: set[int], *, timeout_seconds: float) -> list[int]:
    deadline = time.monotonic() + timeout_seconds
    living = sorted(pid for pid in pids if Path(f"/proc/{pid}").exists())
    while living and time.monotonic() < deadline:
        time.sleep(0.1)
        living = sorted(pid for pid in pids if Path(f"/proc/{pid}").exists())
    return living


def _recover_expired(database_url: str, run_ref: str) -> int:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_strict_job_attempt AS attempt
                    SET state = 'stale', completed_at = CURRENT_TIMESTAMP
                    FROM execution.semantic_closure_job AS job
                    WHERE attempt.job_ref = job.job_ref
                      AND job.run_ref = %s
                      AND job.state = 'leased'
                      AND job.lease_expires_at < CURRENT_TIMESTAMP
                      AND attempt.state = 'leased'
                      AND attempt.lease_epoch = job.lease_epoch
                    """,
                    (run_ref,),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_closure_job
                    SET state = 'open', lease_owner = NULL,
                        lease_token = NULL, lease_expires_at = NULL,
                        retry_count = retry_count + 1
                    WHERE run_ref = %s AND state = 'leased'
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    """,
                    (run_ref,),
                )
                return cursor.rowcount
    finally:
        connection.close()


def _counts(database_url: str, run_ref: str) -> dict[str, int]:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) FILTER (WHERE state = 'open'),
                    count(*) FILTER (WHERE state = 'leased'),
                    count(*) FILTER (WHERE state = 'computed'),
                    count(*) FILTER (WHERE state = 'completed')
                FROM execution.semantic_closure_job
                WHERE run_ref = %s
                """,
                (run_ref,),
            )
            open_count, leased, computed, completed = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FILTER (WHERE attempt.state = 'stale'),
                       count(*)
                FROM execution.semantic_strict_job_attempt AS attempt
                JOIN execution.semantic_closure_job AS job USING (job_ref)
                WHERE job.run_ref = %s
                """,
                (run_ref,),
            )
            stale, attempts = cursor.fetchone()
            return {
                "open": int(open_count or 0),
                "leased": int(leased or 0),
                "computed": int(computed or 0),
                "completed": int(completed or 0),
                "stale_attempts": int(stale or 0),
                "attempts": int(attempts or 0),
            }
    finally:
        connection.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-ref", default=f"typed-parent-death:{uuid4().hex}")
    parser.add_argument("--document-ref", default="document:typed-parent-death")
    parser.add_argument("--owner-ref", default="owner:typed-parent-death")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--work-items", type=int, default=8)
    parser.add_argument("--coordinator-child", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    marker_root = args.artifact_root / "active-workers"
    if args.coordinator_child:
        os.environ["SENSIBLAW_TYPED_ACTIVE_MARKER_ROOT"] = str(marker_root)
        os.environ["SENSIBLAW_COORDINATOR_LEASE_SECONDS"] = "3"
        _run(args, execute=_slow_execute)
        return 0

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--database-url",
        args.database_url,
        "--artifact-root",
        str(args.artifact_root),
        "--run-ref",
        args.run_ref,
        "--document-ref",
        args.document_ref,
        "--owner-ref",
        args.owner_ref,
        "--workers",
        str(args.workers),
        "--work-items",
        str(args.work_items),
        "--coordinator-child",
    ]
    child = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        markers = tuple(marker_root.glob("worker-*.active"))
        if len(markers) >= args.workers:
            break
        if child.poll() is not None:
            raise RuntimeError("coordinator exited before workers became active")
        time.sleep(0.1)
    else:
        child.kill()
        raise RuntimeError("typed workers did not enter active computation")

    before = _counts(args.database_url, args.run_ref)
    if before["leased"] < args.workers or before["completed"]:
        child.kill()
        raise RuntimeError("unexpected database state at active-computation boundary")

    descendants = _descendants(child.pid)
    os.kill(child.pid, signal.SIGKILL)
    child.wait(timeout=10)
    surviving = _wait_for_exit(descendants, timeout_seconds=10)
    if surviving:
        raise RuntimeError(
            f"parent-death supervision left worker descendants alive: {surviving}"
        )

    time.sleep(2.5)
    recovered = _recover_expired(args.database_url, args.run_ref)
    if recovered < args.workers:
        raise RuntimeError(
            f"expected at least {args.workers} expired leases, recovered {recovered}"
        )
    after_recovery = _counts(args.database_url, args.run_ref)
    if after_recovery["leased"] != 0:
        raise RuntimeError("expired typed worker leases remain leased")
    if after_recovery["stale_attempts"] < args.workers:
        raise RuntimeError("expired typed attempts were not fenced stale")

    time.sleep(1.0)
    os.environ["SENSIBLAW_COORDINATOR_LEASE_SECONDS"] = "3"
    applied = _run(args, execute=execute_serialized_streaming_job)
    expected_jobs = sorted(
        manifest.job_ref
        for manifest in _manifests(
            run_ref=args.run_ref,
            document_ref=args.document_ref,
            owner_ref=args.owner_ref,
            count=args.work_items,
        )
    )
    if applied != list(enumerate(expected_jobs, start=1)):
        raise RuntimeError("replacement changed canonical admission order")
    final = _counts(args.database_url, args.run_ref)
    if final["completed"] != args.work_items:
        raise RuntimeError("replacement did not complete every typed job")
    if final["open"] or final["leased"] or final["computed"]:
        raise RuntimeError("replacement left unresolved typed job state")

    report = {
        "schema_version": "sensiblaw.typed-worker-parent-death.v1",
        "state": "passed",
        "run_ref": args.run_ref,
        "work_items": args.work_items,
        "active_workers_before_kill": len(markers),
        "observed_descendant_count": len(descendants),
        "orphan_worker_count": len(surviving),
        "recovered_expired_leases": recovered,
        "stale_attempts": final["stale_attempts"],
        "completed_after_resume": final["completed"],
        "recomputed_completed_work": 0,
        "text_serialization": False,
    }
    report_path = args.artifact_root / "typed-worker-parent-death-report.pkl"
    report_path.write_bytes(pickle.dumps(report, protocol=5))
    print(
        "typed-worker-parent-death-probe "
        f"state=passed active={len(markers)} descendants={len(descendants)} "
        f"orphans=0 recovered={recovered} completed={final['completed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
