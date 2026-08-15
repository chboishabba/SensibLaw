#!/usr/bin/env python3
"""Kill strict closure after typed computation and before canonical admission.

The first coordinator runs real supervised process workers, waits until every
result is committed in ``computed`` state, then pauses before owner revisions
are allocated.  The parent kills only that coordinator, proves that every
process descendant exits, waits for the coordinator lease to expire, and starts
a replacement.  The replacement must admit the staged rows without creating
another semantic attempt.
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
    _admit_all_computed,
    install_deterministic_admission_execution,
)
from src.storage.postgres.distributed_semantic_execution import (  # noqa: E402
    ImmutableJobManifest,
    execute_serialized_streaming_job,
)
from src.storage.postgres.typed_execution_pool import (  # noqa: E402
    TypedProcessPostgresWorkerPool,
    install_typed_execution_pool,
)
from src.storage.postgres.typed_process_supervision import (  # noqa: E402
    install_typed_process_supervision,
)


class PausedAdmissionWorkerPool(DeterministicAdmissionWorkerPool):
    """Expose the durable computed/admission boundary for destructive testing."""

    def run_until_idle(self) -> dict[str, Any]:
        # Execute and commit all worker results while deliberately bypassing
        # canonical admission until the marker has been observed by the parent.
        result = TypedProcessPostgresWorkerPool.run_until_idle(self)
        marker = Path(os.environ["SENSIBLAW_TYPED_STAGE_MARKER"])
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        time.sleep(float(os.environ.get("SENSIBLAW_TYPED_STAGE_PAUSE_SECONDS", "600")))

        def connection_factory() -> Any:
            import psycopg

            return psycopg.connect(self.database_url)

        admitted = _admit_all_computed(connection_factory, run_ref=self.run_ref)
        result["receipts"].append(
            {
                "worker_ref": f"{self.run_ref}:canonical-admission",
                "accepted": admitted,
                "duplicates": 0,
                "stale": 0,
                "admission_only": True,
            }
        )
        return result


def _connect(database_url: str) -> Any:
    import psycopg

    return psycopg.connect(database_url)


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
            declaration_ref="declaration:typed-stage-kill:v2",
            input_revision=0,
            input_refs=(f"observation:{ordinal}",),
            input_payload={"observation_delta": {"observations": ()}},
            rule_set_revision="rules:typed-stage-kill:v2",
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


def _install(*, paused: bool) -> None:
    install_typed_execution_pool()
    install_typed_process_supervision()
    install_deterministic_admission_execution()
    if paused:
        execution.ProcessPostgresWorkerPool = PausedAdmissionWorkerPool


def _run_strategy(args: argparse.Namespace, *, paused: bool) -> list[tuple[int, str]]:
    _install(paused=paused)
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
        execute=execute_serialized_streaming_job,
        apply=apply,
        owner_ref=args.owner_ref,
    )
    return applied


def _counts(database_url: str, run_ref: str) -> dict[str, int]:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) FILTER (WHERE state = 'computed'),
                    count(*) FILTER (WHERE state = 'completed')
                FROM execution.semantic_closure_job
                WHERE run_ref = %s
                """,
                (run_ref,),
            )
            computed, completed = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*)
                FROM execution.semantic_strict_job_attempt attempt
                JOIN execution.semantic_closure_job job USING (job_ref)
                WHERE job.run_ref = %s
                """,
                (run_ref,),
            )
            attempts = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT count(*)
                FROM execution.semantic_strict_delta_admission
                WHERE run_ref = %s
                """,
                (run_ref,),
            )
            admissions = int(cursor.fetchone()[0])
            return {
                "computed": int(computed or 0),
                "completed": int(completed or 0),
                "attempts": attempts,
                "admissions": admissions,
            }
    finally:
        connection.close()


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


def _survivors(pids: set[int]) -> list[int]:
    return sorted(pid for pid in pids if Path(f"/proc/{pid}").exists())


def _wait_for_exit(pids: set[int], *, timeout_seconds: float) -> list[int]:
    deadline = time.monotonic() + timeout_seconds
    living = _survivors(pids)
    while living and time.monotonic() < deadline:
        time.sleep(0.1)
        living = _survivors(pids)
    return living


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-ref", default=f"typed-stage-kill:{uuid4().hex}")
    parser.add_argument("--document-ref", default="document:typed-stage-kill")
    parser.add_argument("--owner-ref", default="owner:typed-stage-kill")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--work-items", type=int, default=8)
    parser.add_argument("--coordinator-child", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    marker = args.artifact_root / "all-results-computed"
    if args.coordinator_child:
        os.environ["SENSIBLAW_TYPED_STAGE_MARKER"] = str(marker)
        os.environ["SENSIBLAW_TYPED_STAGE_PAUSE_SECONDS"] = "600"
        os.environ["SENSIBLAW_COORDINATOR_LEASE_SECONDS"] = "3"
        _run_strategy(args, paused=True)
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
    before: dict[str, int] | None = None
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("coordinator exited before staged-result boundary")
        if marker.exists():
            candidate = _counts(args.database_url, args.run_ref)
            if candidate["computed"] == args.work_items:
                before = candidate
                break
        time.sleep(0.1)
    if before is None:
        child.kill()
        raise RuntimeError("typed workers did not reach the computed boundary")
    if before["admissions"] != 0 or before["completed"] != 0:
        child.kill()
        raise RuntimeError("canonical admission occurred before kill boundary")

    descendants = _descendants(child.pid)
    os.kill(child.pid, signal.SIGKILL)
    child.wait(timeout=10)
    surviving = _wait_for_exit(descendants, timeout_seconds=10)
    if surviving:
        raise RuntimeError(
            f"coordinator death left process descendants alive: {surviving}"
        )

    # The replacement may acquire coordinator authority only after expiry.
    time.sleep(3.5)
    os.environ["SENSIBLAW_COORDINATOR_LEASE_SECONDS"] = "3"
    applied = _run_strategy(args, paused=False)
    after = _counts(args.database_url, args.run_ref)
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
        raise RuntimeError("replacement coordinator changed canonical admission order")
    if after["attempts"] != before["attempts"]:
        raise RuntimeError("replacement coordinator recomputed staged semantic work")
    if after["computed"] != 0 or after["completed"] != args.work_items:
        raise RuntimeError("replacement coordinator did not settle every staged job")
    if after["admissions"] != args.work_items:
        raise RuntimeError("replacement coordinator did not admit every staged delta")

    report = {
        "schema_version": "sensiblaw.typed-staging-kill-probe.v2",
        "state": "passed",
        "run_ref": args.run_ref,
        "work_items": args.work_items,
        "attempts_before_kill": before["attempts"],
        "attempts_after_resume": after["attempts"],
        "recomputed_staged_work": 0,
        "canonical_admissions": after["admissions"],
        "observed_descendant_count": len(descendants),
        "orphan_worker_count": len(surviving),
        "text_serialization": False,
    }
    report_path = args.artifact_root / "typed-staging-kill-report.pkl"
    report_path.write_bytes(pickle.dumps(report, protocol=5))
    print(
        "typed-staging-kill-probe "
        f"state=passed work_items={args.work_items} "
        f"descendants={len(descendants)} orphans=0 "
        "recomputed=0 canonical_order=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
