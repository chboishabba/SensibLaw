#!/usr/bin/env python3
"""Prove committed bounded work survives SIGKILL of its coordinator.

The probe uses the real PostgreSQL work-item protocol and real process workers.
It is destructive only to the supplied run_ref.  The replacement coordinator
must reuse every committed unit and compute only work whose transaction never
committed.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.carriers.canonical import canonical_sha256  # noqa: E402
from src.runtime.durable_work_items import (  # noqa: E402
    DurableWorkSpec,
    complete_leased_work,
    lease_registered_work,
    linux_parent_death_initializer,
    load_completed_work,
    recover_expired_work,
    register_work_items,
)


def _connect(database_url: str) -> Any:
    import psycopg

    return psycopg.connect(database_url, autocommit=False)


def _specs(args: argparse.Namespace) -> tuple[DurableWorkSpec, ...]:
    return tuple(
        DurableWorkSpec(
            database_url=args.database_url,
            run_ref=args.run_ref,
            document_ref=args.document_ref,
            stage_contract_ref="coordinator-kill-probe:v1",
            operation_ref="probe.square",
            partition_ref=f"probe:{ordinal}",
            ordinal=ordinal,
            input_manifest={
                "stage_input_identity": {"probe": args.run_ref},
                "ordinal": ordinal,
                "value": ordinal,
            },
            artifact_root=args.artifact_root,
            worker_ref=f"{args.run_ref}:worker",
            lease_seconds=args.lease_seconds,
        )
        for ordinal in range(args.work_items)
    )


def _worker(spec_row: Mapping[str, Any], delay: float) -> dict[str, Any]:
    spec = DurableWorkSpec.from_dict(spec_row)
    cached = load_completed_work(spec)
    if cached is not None:
        return {"work_ref": spec.work_ref, "reused": True, "value": cached}
    lease = lease_registered_work(spec)
    if lease is None:
        for _ in range(100):
            cached = load_completed_work(spec)
            if cached is not None:
                return {"work_ref": spec.work_ref, "reused": True, "value": cached}
            time.sleep(0.05)
        raise RuntimeError("work remained leased without a committed result")
    time.sleep(delay)
    value = {"ordinal": spec.ordinal, "square": spec.ordinal * spec.ordinal}
    receipt = complete_leased_work(lease, value, worker_pid=os.getpid())
    return {
        "work_ref": spec.work_ref,
        "reused": receipt["admission_state"] == "duplicate",
        "value": value,
    }


def _coordinator(args: argparse.Namespace) -> int:
    specs = _specs(args)
    register_work_items(specs)
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=args.workers,
        mp_context=context,
        initializer=linux_parent_death_initializer,
    ) as pool:
        futures = [
            pool.submit(
                _worker,
                spec.to_dict(),
                args.fast_delay if ordinal < args.fast_items else args.slow_delay,
            )
            for ordinal, spec in enumerate(specs)
        ]
        for future in as_completed(futures):
            row = future.result()
            print(json.dumps(row, sort_keys=True), flush=True)
    return 0


def _completed(database_url: str, run_ref: str) -> tuple[int, list[str]]:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), coalesce(array_agg(work_ref ORDER BY ordinal), ARRAY[]::text[]) FROM execution.semantic_work_item WHERE run_ref = %s AND state = 'completed'",
                (run_ref,),
            )
            count, refs = cursor.fetchone()
            return int(count), [str(value) for value in refs]
    finally:
        connection.close()


def _manifest(database_url: str, run_ref: str) -> str:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT work_ref, encode(output_sha256, 'hex')
                FROM execution.semantic_work_item
                WHERE run_ref = %s AND state = 'completed'
                ORDER BY ordinal
                """,
                (run_ref,),
            )
            rows = [[str(work_ref), str(digest)] for work_ref, digest in cursor.fetchall()]
    finally:
        connection.close()
    return canonical_sha256(rows)


def _worker_pids(parent_pid: int) -> set[int]:
    path = Path(f"/proc/{parent_pid}/task/{parent_pid}/children")
    try:
        direct = {int(value) for value in path.read_text().split()}
    except (OSError, ValueError):
        return set()
    result = set(direct)
    for pid in tuple(direct):
        result.update(_worker_pids(pid))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-ref", default=f"durable-kill-probe:{os.getpid()}")
    parser.add_argument("--document-ref", default="probe-document")
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--work-items", type=int, default=12)
    parser.add_argument("--fast-items", type=int, default=4)
    parser.add_argument("--fast-delay", type=float, default=0.05)
    parser.add_argument("--slow-delay", type=float, default=30.0)
    parser.add_argument("--lease-seconds", type=int, default=2)
    parser.add_argument("--coordinator-child", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    if args.coordinator_child:
        return _coordinator(args)

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--database-url",
        args.database_url,
        "--run-ref",
        args.run_ref,
        "--document-ref",
        args.document_ref,
        "--artifact-root",
        str(args.artifact_root),
        "--workers",
        str(args.workers),
        "--work-items",
        str(args.work_items),
        "--fast-items",
        str(args.fast_items),
        "--fast-delay",
        str(args.fast_delay),
        "--slow-delay",
        str(args.slow_delay),
        "--lease-seconds",
        str(args.lease_seconds),
        "--coordinator-child",
    ]
    coordinator = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + 30
    committed_before_kill = 0
    committed_refs: list[str] = []
    while time.monotonic() < deadline:
        committed_before_kill, committed_refs = _completed(args.database_url, args.run_ref)
        if committed_before_kill >= args.fast_items:
            break
        if coordinator.poll() is not None:
            raise RuntimeError("coordinator exited before the kill boundary")
        time.sleep(0.1)
    if committed_before_kill < args.fast_items:
        coordinator.kill()
        raise RuntimeError("workers did not commit the required pre-kill units")

    descendants = _worker_pids(coordinator.pid)
    os.killpg(coordinator.pid, signal.SIGKILL)
    coordinator.wait(timeout=10)
    time.sleep(1)
    surviving = [pid for pid in descendants if Path(f"/proc/{pid}").exists()]
    if surviving:
        raise RuntimeError(f"parent-death contract left orphan workers: {surviving}")

    time.sleep(args.lease_seconds + 0.5)
    recovered = recover_expired_work(args.database_url, run_ref=args.run_ref)
    specs = _specs(args)
    context = mp.get_context("spawn")
    reused = 0
    with ProcessPoolExecutor(
        max_workers=args.workers,
        mp_context=context,
        initializer=linux_parent_death_initializer,
    ) as pool:
        futures = [pool.submit(_worker, spec.to_dict(), args.fast_delay) for spec in specs]
        for future in as_completed(futures):
            reused += int(bool(future.result()["reused"]))

    completed_after, final_refs = _completed(args.database_url, args.run_ref)
    if completed_after != args.work_items:
        raise RuntimeError("replacement coordinator did not complete all work")
    if not set(committed_refs).issubset(final_refs):
        raise RuntimeError("committed pre-kill work disappeared")
    if reused < committed_before_kill:
        raise RuntimeError("replacement coordinator recomputed committed work")

    report = {
        "schema_version": "sensiblaw.coordinator-kill-probe.v1",
        "state": "passed",
        "run_ref": args.run_ref,
        "committed_before_kill": committed_before_kill,
        "recovered_expired_leases": recovered,
        "reused_completed_work": reused,
        "recomputed_completed_work": 0,
        "completed_after_resume": completed_after,
        "manifest_sha256": _manifest(args.database_url, args.run_ref),
        "orphan_worker_count": 0,
    }
    report_path = args.artifact_root / "coordinator-kill-probe-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
