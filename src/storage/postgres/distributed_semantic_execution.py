"""PostgreSQL execution strategy for strict semantic acceptance.

The reducer is intentionally not implemented here.  This module owns only the
distributed control plane: immutable job manifests, leases, fence admission,
ordered owner replay, and sealed finalisation/publication checkpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import multiprocessing as mp
import os
import pickle
import time
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from src.policy.carriers.canonical import canonical_sha256


AUTHORITY_BACKEND = "postgresql"
STRICT_EXECUTION_CONTRACT = "postgresql-leased-exact-execution:v1"


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


@dataclass(frozen=True)
class ImmutableJobManifest:
    job_ref: str
    run_ref: str
    document_ref: str
    owner_ref: str
    input_revision: int
    input_payload: Mapping[str, Any]
    input_sha256: str

    @classmethod
    def build(
        cls,
        *,
        job_ref: str,
        run_ref: str,
        document_ref: str,
        owner_ref: str,
        input_revision: int,
        input_payload: Mapping[str, Any],
    ) -> "ImmutableJobManifest":
        if input_revision < 0:
            raise ValueError("input_revision must be non-negative")
        digest = canonical_sha256(dict(input_payload))
        return cls(
            job_ref=job_ref,
            run_ref=run_ref,
            document_ref=document_ref,
            owner_ref=owner_ref,
            input_revision=input_revision,
            input_payload=dict(input_payload),
            input_sha256=digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_ref": self.job_ref,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "owner_ref": self.owner_ref,
            "input_revision": self.input_revision,
            "input_payload": dict(self.input_payload),
            "input_sha256": self.input_sha256,
        }

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "ImmutableJobManifest":
        result = cls.build(
            job_ref=str(row["job_ref"]),
            run_ref=str(row["run_ref"]),
            document_ref=str(row["document_ref"]),
            owner_ref=str(row["owner_ref"]),
            input_revision=int(row["input_revision"]),
            input_payload=dict(row.get("input_payload") or {}),
        )
        if result.input_sha256 != str(row.get("input_sha256")):
            raise ValueError("immutable job manifest digest mismatch")
        return result


@dataclass(frozen=True)
class Lease:
    manifest: ImmutableJobManifest
    worker_ref: str
    fence_token: str
    attempt_ref: str
    lease_epoch: int = 0
    expected_owner_revision: int = 0
    backend_pid: int | None = None


def create_run(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    kernel_key: str | None = None,
    worker_budget: int | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO execution.semantic_run
            (run_ref, document_ref, authority_backend, lifecycle, kernel_key, kernel_contract, worker_budget)
        VALUES (%s, %s, %s, 'created', %s, %s, %s)
        ON CONFLICT (run_ref) DO UPDATE SET
            document_ref = EXCLUDED.document_ref,
            authority_backend = EXCLUDED.authority_backend,
            kernel_key = COALESCE(EXCLUDED.kernel_key, semantic_run.kernel_key),
            kernel_contract = COALESCE(EXCLUDED.kernel_contract, semantic_run.kernel_contract),
            worker_budget = COALESCE(EXCLUDED.worker_budget, semantic_run.worker_budget)
        """,
        (run_ref, document_ref, AUTHORITY_BACKEND, kernel_key, STRICT_EXECUTION_CONTRACT, worker_budget),
    )


def register_kernel(
    cursor: Any, *, run_ref: str, kernel_key: str, worker_budget: int, metadata: Mapping[str, Any] | None = None
) -> None:
    if not kernel_key or worker_budget < 1:
        raise ValueError("kernel registration requires a key and positive worker budget")
    cursor.execute(
        """
        INSERT INTO execution.semantic_kernel_registration
            (run_ref, kernel_key, kernel_contract, worker_budget, metadata)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (run_ref) DO UPDATE SET
            kernel_key = EXCLUDED.kernel_key,
            kernel_contract = EXCLUDED.kernel_contract,
            worker_budget = EXCLUDED.worker_budget,
            metadata = EXCLUDED.metadata
        """,
        (run_ref, kernel_key, STRICT_EXECUTION_CONTRACT, worker_budget, _json(metadata or {})),
    )


def record_lifecycle(cursor: Any, *, run_ref: str, lifecycle: str, detail: Mapping[str, Any] | None = None) -> None:
    event_ref = f"lifecycle:{run_ref}:{lifecycle}:{uuid4().hex}"
    cursor.execute(
        "INSERT INTO execution.semantic_lifecycle_event (event_ref, run_ref, lifecycle, detail) VALUES (%s, %s, %s, %s::jsonb)",
        (event_ref, run_ref, lifecycle, _json(detail or {})),
    )
    cursor.execute(
        "UPDATE execution.semantic_run SET lifecycle = %s, updated_at = CURRENT_TIMESTAMP, lifecycle_history = lifecycle_history || %s::jsonb WHERE run_ref = %s",
        (lifecycle, _json([{"lifecycle": lifecycle, "detail": dict(detail or {})}]), run_ref),
    )


def enqueue_canonical_closure_jobs(
    cursor: Any, manifests: Iterable[ImmutableJobManifest]
) -> int:
    rows = []
    for manifest in manifests:
        rows.append(
            (
                manifest.job_ref,
                manifest.run_ref,
                manifest.document_ref,
                manifest.owner_ref,
                manifest.input_revision,
                _json(manifest.to_dict()),
                _digest(manifest.input_payload),
            )
        )
    if rows:
        cursor.executemany(
            """
            INSERT INTO execution.semantic_closure_job
                (job_ref, run_ref, document_ref, owner_ref, input_revision,
                 input_manifest, input_sha256)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (job_ref) DO NOTHING
            """,
            rows,
        )
    return len(rows)


def lease_next_job(
    cursor: Any, *, run_ref: str, worker_ref: str, lease_seconds: int = 60
) -> Lease | None:
    """Atomically claim one ready or expired job and create its attempt."""

    cursor.execute(
        """
        SELECT job_ref, run_ref, document_ref, owner_ref, input_revision,
               input_manifest, encode(input_sha256, 'hex'), lease_epoch,
               expected_owner_revision, worker_pid, backend_pid
        FROM execution.semantic_closure_job
        WHERE run_ref = %s
          AND (state = 'open' OR (state = 'leased' AND lease_expires_at < CURRENT_TIMESTAMP))
        ORDER BY input_revision, job_ref
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """,
        (run_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    job_ref, row_run, document_ref, owner_ref, input_revision, payload, input_sha, lease_epoch, expected_revision, _worker_pid, backend_pid = row
    manifest_row = dict(
        job_ref=job_ref,
        run_ref=row_run,
        document_ref=document_ref,
        owner_ref=owner_ref,
        input_revision=input_revision,
        input_payload=(payload or {}).get("input_payload", {}),
        input_sha256=input_sha,
    )
    manifest = ImmutableJobManifest.from_dict(manifest_row)
    token = uuid4().hex
    attempt_ref = f"attempt:{run_ref}:{job_ref}:{token}"
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET state = 'leased', lease_owner = %s, lease_token = %s,
            lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
            lease_epoch = lease_epoch + 1, expected_owner_revision = %s,
            attempts = attempts + 1
        WHERE job_ref = %s
        """,
        (worker_ref, token, lease_seconds, expected_revision, job_ref),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_strict_job_attempt
            (attempt_ref, job_ref, worker_ref, lease_token, input_sha256, state,
             lease_epoch, worker_pid, backend_pid)
        VALUES (%s, %s, %s, %s, %s, 'leased', %s, %s, %s)
        """,
        (attempt_ref, job_ref, worker_ref, token, _digest(manifest.input_payload), int(lease_epoch) + 1, os.getpid(), int(backend_pid) if backend_pid else None),
    )
    return Lease(manifest, worker_ref, token, attempt_ref, int(lease_epoch) + 1, int(expected_revision), int(backend_pid) if backend_pid else None)


def renew_lease(cursor: Any, *, lease: Lease, lease_seconds: int = 60) -> bool:
    """Extend a lease only while its epoch and fence are still current."""
    cursor.execute(
        """UPDATE execution.semantic_closure_job
           SET lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
               renewals = renewals + 1
         WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
           AND state = 'leased'""",
        (lease_seconds, lease.manifest.job_ref, lease.fence_token, lease.lease_epoch),
    )
    return cursor.rowcount == 1


def semantic_delta_admission(
    cursor: Any,
    *,
    lease: Lease,
    delta_ref: str,
    prior_revision: int,
    resulting_revision: int,
    payload: Mapping[str, Any],
) -> str:
    """Persist an immutable delta and admit it exactly once under its fence.

    ``duplicate`` is safe replay; ``stale`` means a different fence attempted
    to write the same owner revision and must never mutate the owner.
    """

    if resulting_revision != prior_revision + 1:
        raise ValueError("semantic delta revisions must advance by one")
    if prior_revision != lease.expected_owner_revision:
        return "stale"
    cursor.execute(
        "SELECT fence_token FROM execution.semantic_strict_delta_admission WHERE delta_ref = %s",
        (delta_ref,),
    )
    existing_delta = cursor.fetchone()
    if existing_delta is not None:
        return "duplicate" if str(existing_delta[0]) == lease.fence_token else "stale"
    cursor.execute(
        "SELECT delta_ref, fence_token FROM execution.semantic_strict_delta_admission WHERE run_ref = %s AND owner_ref = %s AND resulting_revision = %s",
        (lease.manifest.run_ref, lease.manifest.owner_ref, resulting_revision),
    )
    existing_revision = cursor.fetchone()
    if existing_revision is not None:
        return "stale"
    cursor.execute(
        """
        INSERT INTO execution.semantic_immutable_delta
            (delta_ref, run_ref, document_ref, owner_ref, resulting_revision,
             prior_revision, payload, payload_sha256, job_ref, lease_epoch,
             expected_owner_revision)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        ON CONFLICT (delta_ref) DO NOTHING
        """,
        (
            delta_ref, lease.manifest.run_ref, lease.manifest.document_ref,
            lease.manifest.owner_ref, resulting_revision, prior_revision,
            _json(payload), _digest(payload), lease.manifest.job_ref,
            lease.lease_epoch, lease.expected_owner_revision,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_strict_delta_admission
            (delta_ref, run_ref, owner_ref, resulting_revision, prior_revision,
             fence_token, lease_epoch)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (delta_ref) DO NOTHING
        RETURNING delta_ref
        """,
        (delta_ref, lease.manifest.run_ref, lease.manifest.owner_ref, resulting_revision, prior_revision, lease.fence_token, lease.lease_epoch),
    )
    row = cursor.fetchone()
    return "accepted" if row is not None else "stale"


def replay_accepted_deltas(
    cursor: Any,
    *,
    run_ref: str,
    owner_ref: str,
    apply: Callable[[Mapping[str, Any], int], None],
    starting_revision: int = 0,
) -> int:
    """Replay accepted deltas exactly once in owner-revision order."""

    cursor.execute(
        """
        SELECT d.payload, d.resulting_revision
        FROM execution.semantic_immutable_delta d
        JOIN execution.semantic_strict_delta_admission a USING (delta_ref)
        WHERE d.run_ref = %s AND d.owner_ref = %s AND d.resulting_revision > %s
        ORDER BY d.resulting_revision
        """,
        (run_ref, owner_ref, starting_revision),
    )
    expected = starting_revision + 1
    count = 0
    rows = cursor.fetchall()
    for payload, revision in rows:
        if int(revision) != expected:
            raise ValueError(f"non-contiguous accepted owner revision: expected {expected}, got {revision}")
        apply(payload, int(revision))
        cursor.execute(
            """
            INSERT INTO execution.semantic_owner_revision_history
                (run_ref, owner_ref, revision)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (run_ref, owner_ref, int(revision)),
        )
        expected += 1
        count += 1
    return count


class DistributedSemanticWorker:
    """Lease closure manifests and persist worker output through fences."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        run_ref: str,
        worker_ref: str,
        execute: Callable[[ImmutableJobManifest], Mapping[str, Any]],
        lease_seconds: int = 60,
    ) -> None:
        self.connection_factory = connection_factory
        self.run_ref = run_ref
        self.worker_ref = worker_ref
        self.execute = execute
        self.lease_seconds = lease_seconds

    def run_once(self) -> str:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = lease_next_job(cursor, run_ref=self.run_ref, worker_ref=self.worker_ref, lease_seconds=self.lease_seconds)
            if lease is None:
                return "idle"
            try:
                delta = dict(self.execute(lease.manifest))
            except Exception as error:
                failed = self.connection_factory()
                try:
                    with failed.transaction():
                        with failed.cursor() as cursor:
                            cursor.execute("UPDATE execution.semantic_strict_job_attempt SET state = 'failed', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s", (lease.attempt_ref,))
                            cursor.execute("UPDATE execution.semantic_closure_job SET state = 'open', lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL WHERE job_ref = %s AND lease_token = %s", (lease.manifest.job_ref, lease.fence_token))
                finally:
                    failed.close()
                raise error
            with connection.transaction():
                with connection.cursor() as cursor:
                    status = semantic_delta_admission(
                        cursor, lease=lease,
                        delta_ref=str(delta["delta_ref"]),
                        prior_revision=int(delta["prior_revision"]),
                        resulting_revision=int(delta["resulting_revision"]),
                        payload=dict(delta.get("payload") or {}),
                    )
                    cursor.execute(
                        """
                        UPDATE execution.semantic_strict_job_attempt
                        SET state = 'completed', output_sha256 = %s, completed_at = CURRENT_TIMESTAMP
                        WHERE attempt_ref = %s
                        """,
                        (_digest(delta), lease.attempt_ref),
                    )
                    cursor.execute(
                        """UPDATE execution.semantic_closure_job SET state = 'completed' WHERE job_ref = %s AND lease_token = %s""",
                        (lease.manifest.job_ref, lease.fence_token),
                    )
                    cursor.execute("UPDATE execution.semantic_strict_job_attempt SET state = %s, output_sha256 = %s, completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s", ("completed" if status != "stale" else "stale", _digest(delta), lease.attempt_ref))
                    cursor.execute("UPDATE execution.semantic_closure_job SET state = 'completed' WHERE job_ref = %s AND lease_token = %s", (lease.manifest.job_ref, lease.fence_token))
                    return status
        finally:
            connection.close()

    def run_until_idle(self) -> dict[str, int]:
        counts = {"accepted": 0, "duplicate": 0, "stale": 0, "idle": 0}
        while True:
            status = self.run_once()
            counts[status] = counts.get(status, 0) + 1
            if status == "idle":
                return counts


@dataclass(frozen=True)
class WorkerReceipt:
    worker_ref: str
    worker_pid: int
    backend_pid: int | None
    application_name: str
    leases: int
    renewals: int
    accepted: int
    duplicates: int
    stale: int
    retries: int
    failures: int

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _process_worker_main(
    database_url: str,
    run_ref: str,
    worker_ref: str,
    execute: Callable[[ImmutableJobManifest], Mapping[str, Any]],
    lease_seconds: int,
    result_queue: Any,
) -> None:
    """Spawn target: no coordinator state or owner heap is inherited."""
    application_name = f"sensiblaw-strict:{run_ref}:{worker_ref}"
    import psycopg
    connection = psycopg.connect(database_url, application_name=application_name)
    stats = dict(worker_ref=worker_ref, worker_pid=os.getpid(), backend_pid=None,
                 application_name=application_name, leases=0, renewals=0,
                 accepted=0, duplicates=0, stale=0, retries=0, failures=0)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            stats["backend_pid"] = int(cursor.fetchone()[0])
        # psycopg starts a transaction for the backend-pid probe.  End it
        # before entering the worker's independent lease transactions so the
        # durable receipt and lease state cannot be rolled back on close.
        connection.commit()
        while True:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = lease_next_job(cursor, run_ref=run_ref, worker_ref=worker_ref, lease_seconds=lease_seconds)
            if lease is None:
                break
            stats["leases"] += 1
            try:
                # Renewal is deliberately performed before admission. A real
                # long-running kernel can call the same public seam periodically.
                with connection.transaction():
                    with connection.cursor() as cursor:
                        if renew_lease(cursor, lease=lease, lease_seconds=lease_seconds):
                            stats["renewals"] += 1
                delta = dict(execute(lease.manifest))
                with connection.transaction():
                    with connection.cursor() as cursor:
                        status = semantic_delta_admission(cursor, lease=lease,
                            delta_ref=str(delta["delta_ref"]), prior_revision=int(delta["prior_revision"]),
                            resulting_revision=int(delta["resulting_revision"]), payload=dict(delta.get("payload") or {}))
                        stats["duplicates" if status == "duplicate" else status] += 1
                        cursor.execute("UPDATE execution.semantic_strict_job_attempt SET state = %s, output_sha256 = %s, completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s AND lease_epoch = %s", ("stale" if status == "stale" else "completed", _digest(delta), lease.attempt_ref, lease.lease_epoch))
                        cursor.execute("UPDATE execution.semantic_closure_job SET state = 'completed' WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s", (lease.manifest.job_ref, lease.fence_token, lease.lease_epoch))
            except Exception:
                stats["failures"] += 1
                stats["retries"] += 1
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("UPDATE execution.semantic_strict_job_attempt SET state = 'failed', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s", (lease.attempt_ref,))
                        cursor.execute("UPDATE execution.semantic_closure_job SET state = 'open', lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL, retry_count = retry_count + 1 WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s", (lease.manifest.job_ref, lease.fence_token, lease.lease_epoch))
                raise
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO execution.semantic_worker_receipt
                    (receipt_ref, run_ref, document_ref, worker_ref, worker_pid, backend_pid, application_name, leases, renewals, accepted, duplicates, stale, retries, failures, payload)
                    VALUES (%s,%s,(SELECT document_ref FROM execution.semantic_run WHERE run_ref=%s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (run_ref, worker_ref) DO UPDATE SET payload=EXCLUDED.payload, leases=EXCLUDED.leases, renewals=EXCLUDED.renewals, accepted=EXCLUDED.accepted, duplicates=EXCLUDED.duplicates, stale=EXCLUDED.stale, retries=EXCLUDED.retries, failures=EXCLUDED.failures""",
                    (f"worker-receipt:{run_ref}:{worker_ref}", run_ref, run_ref, worker_ref, stats["worker_pid"], stats["backend_pid"], application_name, stats["leases"], stats["renewals"], stats["accepted"], stats["duplicates"], stats["stale"], stats["retries"], stats["failures"], _json(stats)))
        result_queue.put(stats)
    except Exception as error:
        # Keep the parent diagnostic useful even when a child fails before it
        # can persist its normal receipt.
        stats["error"] = repr(error)
        result_queue.put(stats)
        raise
    finally:
        connection.close()


class ProcessPostgresWorkerPool:
    """Strict process-backed pool; each worker owns one PostgreSQL session."""

    def __init__(self, *, database_url: str, run_ref: str, worker_count: int,
                 execute: Callable[[ImmutableJobManifest], Mapping[str, Any]], lease_seconds: int = 60) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        try:
            pickle.dumps(execute)
        except (pickle.PicklingError, AttributeError, TypeError) as error:
            raise TypeError("strict process worker executor must be spawn-picklable") from error
        self.database_url, self.run_ref, self.worker_count = database_url, run_ref, worker_count
        self.execute, self.lease_seconds = execute, lease_seconds

    def run_until_idle(self) -> dict[str, Any]:
        context = mp.get_context("spawn")
        queue = context.Queue()
        processes = [context.Process(target=_process_worker_main, args=(self.database_url, self.run_ref, f"{self.run_ref}:worker:{i}", self.execute, self.lease_seconds, queue), name=f"sensiblaw-strict-worker-{i}") for i in range(self.worker_count)]
        for process in processes:
            process.start()
        for process in processes:
            process.join()
        receipts = []
        while True:
            try:
                receipts.append(queue.get_nowait())
            except Exception:
                break
        if any(process.exitcode not in (0, None) for process in processes):
            errors = [receipt.get("error") for receipt in receipts if receipt.get("error")]
            detail = "; ".join(str(error) for error in errors) or "child exited without acknowledgement"
            raise RuntimeError(f"strict PostgreSQL worker failed; durable leases remain recoverable: {detail}")
        return {"worker_pids": [int(p.get("worker_pid")) for p in receipts], "backend_pids": [int(p["backend_pid"]) for p in receipts if p.get("backend_pid")], "receipts": receipts}


def execute_serialized_streaming_job(manifest: ImmutableJobManifest) -> Mapping[str, Any]:
    """Reference strict kernel for the operational streaming declaration.

    The input is the immutable job manifest, so the spawned process does not
    need the coordinator's owner or closure heap.
    """
    from src.pnf.streaming_fixed_point import OwnerKey, SolverJob
    from src.pnf.streaming_operator_executor import solve_operator_job
    row = dict(manifest.input_payload)
    job = SolverJob(
        owner_key=OwnerKey(**dict(row["owner_key"])),
        declaration_ref=str(row["declaration_ref"]),
        input_revision=int(row["input_revision"]),
        input_refs=tuple(row.get("input_refs") or ()),
        input_payload=dict(row.get("input_payload") or {}),
        rule_set_revision=str(row["rule_set_revision"]),
        coverage_requirements=tuple(row.get("coverage_requirements") or ()),
        assumptions=tuple(row.get("assumptions") or ()),
        priority=int(row.get("priority", 100)),
    )
    from src.pnf.streaming_fixed_point import PythonClosureExecutor
    receipt = PythonClosureExecutor({job.declaration_ref: solve_operator_job}).execute(job)
    return {"delta_ref": receipt.receipt_ref, "prior_revision": manifest.input_revision,
            "resulting_revision": manifest.input_revision + 1, "payload": receipt.to_dict()}


class DistributedFinalizationWorker:
    """Consume sealed manifests/cursors and stage/commit publication."""

    def __init__(self, *, connection_factory: Callable[[], Any], worker_ref: str):
        self.connection_factory = connection_factory
        self.worker_ref = worker_ref

    def checkpoint(self, cursor: Any, *, run_ref: str, owner_ref: str, cursor_revision: int, manifest: Mapping[str, Any]) -> str:
        checkpoint_ref = f"finalization:{run_ref}:{owner_ref}:{cursor_revision}"
        digest = _digest(manifest)
        supplied_digest = manifest.get("manifest_sha256")
        if supplied_digest is not None and bytes.fromhex(str(supplied_digest)) != digest:
            raise ValueError("finalization manifest digest mismatch")
        cursor.execute("SELECT encode(manifest_sha256, 'hex') FROM execution.semantic_finalization_checkpoint WHERE checkpoint_ref = %s", (checkpoint_ref,))
        existing = cursor.fetchone()
        if existing is not None and str(existing[0]) != digest.hex():
            raise ValueError("finalization checkpoint digest mismatch")
        cursor.execute(
            """
            INSERT INTO execution.semantic_finalization_checkpoint
                (checkpoint_ref, run_ref, owner_ref, cursor_revision, sealed_manifest, manifest_sha256, state)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, 'sealed')
            ON CONFLICT (checkpoint_ref) DO NOTHING
            """,
            (checkpoint_ref, run_ref, owner_ref, cursor_revision, _json(manifest), digest),
        )
        return checkpoint_ref

    def stage_then_commit(self, *, run_ref: str, document_ref: str, manifest: Mapping[str, Any]) -> str:
        connection = self.connection_factory()
        publication_ref = f"publication:{run_ref}:{document_ref}"
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    digest = _digest(manifest)
                    cursor.execute("SELECT encode(manifest_sha256, 'hex') FROM execution.semantic_publication WHERE publication_ref = %s", (publication_ref,))
                    existing = cursor.fetchone()
                    if existing is not None and str(existing[0]) != digest.hex():
                        raise ValueError("publication manifest digest mismatch")
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_publication
                            (publication_ref, run_ref, document_ref, state, manifest, manifest_sha256)
                        VALUES (%s, %s, %s, 'staged', %s::jsonb, %s)
                        ON CONFLICT (publication_ref) DO UPDATE SET manifest = EXCLUDED.manifest
                        """,
                        (publication_ref, run_ref, document_ref, _json(manifest), digest),
                    )
                    cursor.execute(
                        """UPDATE execution.semantic_publication SET state = 'committed' WHERE publication_ref = %s""",
                        (publication_ref,),
                    )
            return publication_ref
        finally:
            connection.close()


def _fresh_publication_main(database_url: str, run_ref: str, document_ref: str,
                            manifest: Mapping[str, Any], queue: Any) -> None:
    """Fresh-process publication boundary used after closure workers exit."""
    worker = DistributedFinalizationWorker(
        connection_factory=lambda: __import__("psycopg").connect(
            database_url, application_name=f"sensiblaw-publish:{run_ref}"
        ),
        worker_ref=f"{run_ref}:publisher",
    )
    queue.put({"pid": os.getpid(), "publication_ref": worker.stage_then_commit(
        run_ref=run_ref, document_ref=document_ref, manifest=manifest
    )})


def publish_in_fresh_process(*, database_url: str, run_ref: str,
                             document_ref: str, manifest: Mapping[str, Any]) -> str:
    """Stage and atomically commit publication without inheriting owner state."""
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_fresh_publication_main,
                              args=(database_url, run_ref, document_ref, dict(manifest), queue),
                              name=f"sensiblaw-strict-publisher-{run_ref}")
    process.start()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError("fresh publication process failed")
    return str(queue.get()["publication_ref"])


__all__ = [
    "AUTHORITY_BACKEND",
    "STRICT_EXECUTION_CONTRACT",
    "ImmutableJobManifest",
    "Lease",
    "create_run",
    "register_kernel",
    "record_lifecycle",
    "enqueue_canonical_closure_jobs",
    "lease_next_job",
    "semantic_delta_admission",
    "renew_lease",
    "replay_accepted_deltas",
    "DistributedSemanticWorker",
    "WorkerReceipt",
    "ProcessPostgresWorkerPool",
    "execute_serialized_streaming_job",
    "publish_in_fresh_process",
    "DistributedFinalizationWorker",
]
