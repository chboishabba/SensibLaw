"""Strict acceptance policy for the PostgreSQL leased execution strategy."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Iterable, Mapping, Protocol

AUTHORITY_BACKEND = "postgresql"
STRICT_EXECUTION_CONTRACT = "postgresql-leased-exact-execution:v1"


def _execution_module() -> Any:
    from src.storage.postgres import distributed_semantic_execution

    return distributed_semantic_execution


def _canonical_digest(value: object) -> str:
    from src.policy.carriers.canonical import canonical_sha256
    return canonical_sha256(value)


class StrictExecutionError(RuntimeError):
    """A strict run could not prove its PostgreSQL authority contract."""

    def __init__(self, reason: str, *, diagnostic_path: str | None = None, kernel_key: str | None = None):
        self.reason = reason
        self.diagnostic_path = diagnostic_path
        self.kernel_key = kernel_key
        suffix = f" ({diagnostic_path})" if diagnostic_path else ""
        super().__init__(reason + suffix)


class StrictWorkerPool(Protocol):
    """Internal seam for durable strict worker orchestration."""

    def run_until_idle(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PostgresExecutionContext:
    run_ref: str
    document_ref: str
    authority_backend: str
    row_counts: Mapping[str, int]
    owner_revision: int
    lifecycle: str
    obligations: Mapping[str, int]
    kernel_key: str | None = None
    worker_budget: int | None = None
    build_key_sha256: str | None = None
    operation_contract_ref: str | None = None
    round_ordinal: int = 0
    fixed_point_certificate: Mapping[str, Any] | None = None

    @classmethod
    def from_cursor(cls, cursor: Any, *, run_ref: str, document_ref: str) -> "PostgresExecutionContext":
        cursor.execute(
            """SELECT authority_backend, owner_revision, lifecycle, kernel_key, worker_budget,
                      build_key_sha256, operation_contract_ref, round_ordinal, fixed_point_certificate
                 FROM execution.semantic_run
                WHERE run_ref = %s AND document_ref = %s""",
            (run_ref, document_ref),
        )
        row = cursor.fetchone()
        if row is None:
            raise StrictExecutionError("postgresql_authority_missing", kernel_key="strict.execution_context")
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM execution.semantic_strict_owner_stream WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_closure_job WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_job_attempt a JOIN execution.semantic_closure_job j USING (job_ref) WHERE j.run_ref = %s),
              (SELECT count(*) FROM execution.semantic_immutable_delta WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_strict_delta_admission WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_finalization_checkpoint WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_publication WHERE run_ref = %s AND state = 'committed'),
              (SELECT count(*) FROM execution.semantic_kernel_registration WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_lifecycle_event WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_owner_revision_history WHERE run_ref = %s)
            """,
            (run_ref,) * 10,
        )
        counts_row = cursor.fetchone() or (0,) * 10
        names = ("owner_stream", "jobs", "attempts", "immutable_deltas", "fenced_admissions", "finalization_checkpoints", "committed_publications", "kernel_registrations", "lifecycle_events", "revision_history")
        counts = dict(zip(names, (int(value or 0) for value in counts_row), strict=True))
        cursor.execute(
            """SELECT count(*) FROM execution.semantic_closure_job WHERE run_ref = %s AND state IN ('open', 'leased')""",
            (run_ref,),
        )
        open_jobs = int((cursor.fetchone() or (0,))[0])
        return cls(
            run_ref=run_ref,
            document_ref=document_ref,
            authority_backend=str(row[0]),
            owner_revision=int(row[1]),
            lifecycle=str(row[2]),
            row_counts=counts,
            obligations={"open_or_leased_jobs": open_jobs},
            kernel_key=str(row[3]) if row[3] else None,
            worker_budget=int(row[4]) if row[4] is not None else None,
            build_key_sha256=str(row[5]) if row[5] else None,
            operation_contract_ref=str(row[6]) if row[6] else None,
            round_ordinal=int(row[7] or 0),
            fixed_point_certificate=dict(row[8]) if row[8] else None,
        )


def assert_strict_context(context: PostgresExecutionContext) -> None:
    if context.authority_backend != AUTHORITY_BACKEND:
        raise StrictExecutionError("postgresql_authority_missing", kernel_key="strict.execution_context")
    if context.row_counts["owner_stream"] < 1 or context.row_counts["kernel_registrations"] < 1:
        raise StrictExecutionError("postgresql_authority_missing", kernel_key="strict.execution_context")
    if context.row_counts["immutable_deltas"] != context.row_counts["fenced_admissions"]:
        raise StrictExecutionError("strict_revision_admission_invalid", kernel_key="strict.admission")
    if context.obligations["open_or_leased_jobs"]:
        raise StrictExecutionError("strict_obligations_unresolved", kernel_key="strict.closure_gate")
    if not context.kernel_key or not context.worker_budget or context.worker_budget < 1:
        raise StrictExecutionError("unregistered_kernel", kernel_key=context.kernel_key or "strict.kernel")
    if not context.build_key_sha256 or not context.operation_contract_ref:
        raise StrictExecutionError("strict_authority_identity_missing", kernel_key="strict.execution_context")
    if not context.fixed_point_certificate or context.fixed_point_certificate.get("state") != "reached":
        raise StrictExecutionError("strict_fixed_point_incomplete", kernel_key="strict.closure_gate")


def connect_postgres(database_url: str) -> Any:
    """Open the strict authority connection without silently falling back."""

    if not database_url:
        raise StrictExecutionError("postgresql_authority_missing", kernel_key="strict.connection")
    try:
        import psycopg
        return psycopg.connect(database_url)
    except Exception as error:
        raise StrictExecutionError("postgresql_authority_missing", diagnostic_path=str(error), kernel_key="strict.connection") from error


class PostgresLeasedExecution:
    """Execution-only strategy that delegates semantic application to a caller."""

    def __init__(self, *, database_url: str, run_ref: str, document_ref: str, worker_count: int, kernel_key: str = "streaming_closure", build_key_sha256: str = "unknown", operation_contract_ref: str = STRICT_EXECUTION_CONTRACT, max_rounds: int = 64) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        self.database_url = database_url
        self.run_ref = run_ref
        self.document_ref = document_ref
        self.worker_count = worker_count
        self.kernel_key = kernel_key
        self.build_key_sha256 = build_key_sha256
        self.operation_contract_ref = operation_contract_ref
        self.max_rounds = max_rounds

    def connection_factory(self) -> Any:
        return connect_postgres(self.database_url)

    def begin(self, *, owner_ref: str) -> None:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    module = _execution_module()
                    module.create_run(cursor, run_ref=self.run_ref, document_ref=self.document_ref, kernel_key=self.kernel_key, worker_budget=self.worker_count)
                    cursor.execute("UPDATE execution.semantic_run SET build_key_sha256 = %s, operation_contract_ref = %s, max_rounds = %s WHERE run_ref = %s", (self.build_key_sha256, self.operation_contract_ref, self.max_rounds, self.run_ref))
                    cursor.execute("INSERT INTO execution.semantic_strict_owner_stream (run_ref, owner_ref) VALUES (%s, %s) ON CONFLICT DO NOTHING", (self.run_ref, owner_ref))
                    module.register_kernel(cursor, run_ref=self.run_ref, kernel_key=self.kernel_key, worker_budget=self.worker_count)
                    module.record_lifecycle(cursor, run_ref=self.run_ref, lifecycle="closure.reducing", detail={"owner_ref": owner_ref})
        finally:
            connection.close()

    def run_frontier(
        self,
        manifests: Iterable[Any],
        *,
        execute: Callable[[Any], Mapping[str, Any]],
        apply: Callable[[Mapping[str, Any], int], None],
        owner_ref: str,
        starting_revision: int = 0,
    ) -> dict[str, int]:
        """Persist, lease, admit, and deterministically replay one frontier."""

        self.begin(owner_ref=owner_ref)
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    count = _execution_module().enqueue_canonical_closure_jobs(cursor, manifests)
            receipts = {"enqueued": count, "accepted": 0, "duplicate": 0, "stale": 0, "workers": self.worker_count}
            pool = _execution_module().ProcessPostgresWorkerPool(
                database_url=self.database_url, run_ref=self.run_ref,
                worker_count=self.worker_count, execute=execute,
            )
            round_ordinal = 0
            current_revision = starting_revision
            while round_ordinal < self.max_rounds:
                round_ordinal += 1
                worker_receipt = pool.run_until_idle()
                receipts["workers"] = len(worker_receipt["worker_pids"])
                receipts.setdefault("worker_pids", []).extend(worker_receipt["worker_pids"])
                receipts.setdefault("backend_pids", []).extend(worker_receipt["backend_pids"])
                for worker in worker_receipt["receipts"]:
                    for key in ("accepted", "duplicates", "stale"):
                        target = key.rstrip("s") if key == "duplicates" else key
                        receipts[target] = receipts.get(target, 0) + int(worker.get(key, 0))
                with connection.transaction():
                    with connection.cursor() as cursor:
                        replayed = _execution_module().replay_accepted_deltas(cursor, run_ref=self.run_ref, owner_ref=owner_ref, apply=apply, starting_revision=current_revision)
                        current_revision += replayed
                        cursor.execute("UPDATE execution.semantic_strict_owner_stream SET current_revision = %s WHERE run_ref = %s AND owner_ref = %s", (current_revision, self.run_ref, owner_ref))
                        cursor.execute("UPDATE execution.semantic_run SET owner_revision = %s WHERE run_ref = %s", (current_revision, self.run_ref))
                        # A fenced loser is durable evidence that the same
                        # immutable job must be awakened against the revision
                        # just replayed. Rebuild only its revision-bearing
                        # manifest fields; the coordinator still performs no
                        # semantic work.
                        cursor.execute("""
                            SELECT j.job_ref, j.input_manifest
                            FROM execution.semantic_closure_job j
                            WHERE j.run_ref = %s AND j.state = 'completed'
                              AND EXISTS (SELECT 1 FROM execution.semantic_strict_job_attempt a WHERE a.job_ref = j.job_ref AND a.state = 'stale')
                              AND NOT EXISTS (SELECT 1 FROM execution.semantic_immutable_delta d JOIN execution.semantic_strict_delta_admission ad ON ad.delta_ref = d.delta_ref AND ad.run_ref = d.run_ref WHERE d.job_ref = j.job_ref)
                        """, (self.run_ref,))
                        awakened = 0
                        for job_ref, raw_manifest in cursor.fetchall():
                            manifest = dict(raw_manifest or {})
                            payload = dict(manifest.get("input_payload") or {})
                            manifest["input_revision"] = current_revision
                            payload["input_revision"] = current_revision
                            manifest["input_payload"] = payload
                            cursor.execute("""
                                UPDATE execution.semantic_closure_job
                                SET state = 'open', input_revision = %s, input_manifest = %s::jsonb,
                                    input_sha256 = %s, expected_owner_revision = %s,
                                    lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL
                                WHERE job_ref = %s
                            """, (current_revision, json.dumps(manifest, sort_keys=True), _execution_module()._digest(payload), current_revision, job_ref))
                            awakened += 1
                        cursor.execute("""
                            SELECT count(*) FROM execution.semantic_closure_job
                            WHERE run_ref = %s AND state IN ('open', 'leased', 'failed')
                        """, (self.run_ref,))
                        open_jobs = int(cursor.fetchone()[0])
                        if open_jobs == 0 and awakened == 0:
                            round_manifest = {
                                "round_ref": f"round:{self.run_ref}:{round_ordinal}",
                                "run_ref": self.run_ref,
                                "document_ref": self.document_ref,
                                "round_ordinal": round_ordinal,
                                "input_owner_revision": current_revision - replayed,
                                "output_owner_revision": current_revision,
                                "job_count": count,
                                "delta_count": replayed,
                                "changed_owner_count": 1 if replayed else 0,
                                "awakened_job_count": 0,
                            }
                            cursor.execute("""INSERT INTO execution.semantic_round_manifest
                                (round_ref, run_ref, document_ref, round_ordinal, input_owner_revision,
                                 output_owner_revision, job_count, delta_count, changed_owner_count,
                                 awakened_job_count, manifest, manifest_sha256, state)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s::jsonb,%s,'committed')
                                ON CONFLICT (round_ref) DO NOTHING""", (
                                round_manifest["round_ref"], self.run_ref, self.document_ref,
                                round_ordinal, round_manifest["input_owner_revision"], current_revision,
                                count, replayed, round_manifest["changed_owner_count"],
                                json.dumps(round_manifest, sort_keys=True),
                                bytes.fromhex(_canonical_digest(round_manifest)),
                            ))
                            zero_round = {**round_manifest,
                                "round_ref": f"round:{self.run_ref}:{round_ordinal + 1}",
                                "round_ordinal": round_ordinal + 1,
                                "input_owner_revision": current_revision,
                                "output_owner_revision": current_revision,
                                "job_count": 0, "delta_count": 0,
                                "changed_owner_count": 0, "awakened_job_count": 0}
                            cursor.execute("""INSERT INTO execution.semantic_round_manifest
                                (round_ref, run_ref, document_ref, round_ordinal, input_owner_revision,
                                 output_owner_revision, job_count, delta_count, changed_owner_count,
                                 awakened_job_count, manifest, manifest_sha256, state)
                                VALUES (%s,%s,%s,%s,%s,%s,0,0,0,0,%s::jsonb,%s,'fixed_point')
                                ON CONFLICT (round_ref) DO NOTHING""", (
                                zero_round["round_ref"], self.run_ref, self.document_ref,
                                round_ordinal + 1, current_revision, current_revision,
                                json.dumps(zero_round, sort_keys=True),
                                bytes.fromhex(_canonical_digest(zero_round)),
                            ))
                            certificate = {"state": "reached", "round_count": round_ordinal + 1,
                                          "zero_change_round": round_ordinal + 1,
                                          "owner_revision": current_revision}
                            cursor.execute("UPDATE execution.semantic_run SET round_ordinal = %s, fixed_point_certificate = %s::jsonb WHERE run_ref = %s", (round_ordinal + 1, json.dumps(certificate, sort_keys=True), self.run_ref))
                            _execution_module().record_lifecycle(cursor, run_ref=self.run_ref, lifecycle="closure.fixed-point-certified", detail=certificate)
                            receipts["replayed"] = current_revision - starting_revision
                            return receipts
                # The next round sees the awakened jobs through PostgreSQL.
            raise StrictExecutionError("strict_fixed_point_incomplete: maximum rounds exhausted", kernel_key="strict.closure_gate")
        finally:
            connection.close()

    def finalize(self, *, owner_ref: str, manifest: Mapping[str, Any]) -> str:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    context = PostgresExecutionContext.from_cursor(cursor, run_ref=self.run_ref, document_ref=self.document_ref)
                    assert_strict_context(context)
                    cursor.execute("UPDATE execution.semantic_run SET sealed = TRUE, lifecycle = 'finalization.sealed' WHERE run_ref = %s", (self.run_ref,))
                    worker = _execution_module().DistributedFinalizationWorker(connection_factory=self.connection_factory, worker_ref=f"{self.run_ref}:finalizer")
                    worker.checkpoint(cursor, run_ref=self.run_ref, owner_ref=owner_ref, cursor_revision=context.owner_revision, manifest=manifest)
            return _execution_module().publish_in_fresh_process(
                database_url=self.database_url,
                run_ref=self.run_ref,
                document_ref=self.document_ref,
                manifest=manifest,
            )
        finally:
            connection.close()


def strict_execution_metadata() -> dict[str, str]:
    return {
        "execution_strategy": STRICT_EXECUTION_CONTRACT,
        "authority_backend": AUTHORITY_BACKEND,
        "local_replay": "forbidden",
        "kernel_contract": STRICT_EXECUTION_CONTRACT,
        "worker_backend": "spawned-postgresql-processes",
        "lease_ttl_seconds": "60",
        "max_rounds": "64",
        "retention": "retained-by-default",
    }


__all__ = ["StrictExecutionError", "StrictWorkerPool", "PostgresExecutionContext", "PostgresLeasedExecution", "assert_strict_context", "connect_postgres", "strict_execution_metadata"]
