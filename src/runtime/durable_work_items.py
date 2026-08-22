"""Transactional durability for bounded work without JSON serialization.

A worker may own computation temporarily; PostgreSQL owns progress durably.
Completion commits a content-addressed binary artifact, typed receipt columns,
a contiguous stage cursor, fenced work state, and an outbox transition before
success is returned to the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import hashlib
import os
from pathlib import Path
import pickle
import signal
from typing import Any, Iterable, Mapping
from uuid import uuid4

from src.policy.carriers.canonical import canonical_fields_sha256, canonical_sha256

DURABLE_WORK_CONTRACT = "postgres-durable-work-item:v2"
PARENT_DEATH_CONTRACT = "linux-pdeathsig:v1"
BINARY_ARTIFACT_CONTRACT = "python-pickle:5"


def _canonical_sha256(value: object) -> str:
    from src.policy.carriers.canonical import canonical_sha256

    return canonical_sha256(value)


def _canonical_fields_sha256(*values: object) -> str:
    from src.policy.carriers.canonical import canonical_fields_sha256

    return canonical_fields_sha256(*values)


def _digest(value: object) -> bytes:
    return bytes.fromhex(_canonical_sha256(value))


def _connect(database_url: str) -> Any:
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise RuntimeError("psycopg is required for durable PostgreSQL work") from error
    return psycopg.connect(database_url, autocommit=False)


@dataclass(frozen=True)
class DurableWorkSpec:
    database_url: str
    run_ref: str
    document_ref: str
    stage_contract_ref: str
    operation_ref: str
    partition_ref: str
    ordinal: int
    input_manifest: Mapping[str, Any]
    artifact_root: Path
    worker_ref: str
    lease_seconds: int = 120

    def __post_init__(self) -> None:
        if self.ordinal < 0 or self.lease_seconds < 1:
            raise ValueError("durable work ordinal and lease duration must be valid")

    @property
    def input_sha256(self) -> str:
        return _canonical_sha256(dict(self.input_manifest))

    @property
    def stage_instance_ref(self) -> str:
        return "stage-instance:" + _canonical_fields_sha256(
            self.run_ref,
            self.document_ref,
            self.stage_contract_ref,
            self.operation_ref,
            dict(self.input_manifest).get("stage_input_identity", {}),
        )

    @property
    def work_ref(self) -> str:
        return "work-item:" + _canonical_fields_sha256(
            self.run_ref,
            self.document_ref,
            self.stage_contract_ref,
            self.operation_ref,
            self.partition_ref,
            self.input_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return an in-process/multiprocessing carrier, never a DB payload."""

        return {
            "database_url": self.database_url,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "stage_contract_ref": self.stage_contract_ref,
            "operation_ref": self.operation_ref,
            "partition_ref": self.partition_ref,
            "ordinal": self.ordinal,
            "input_manifest": dict(self.input_manifest),
            "artifact_root": str(self.artifact_root),
            "worker_ref": self.worker_ref,
            "lease_seconds": self.lease_seconds,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DurableWorkSpec":
        return cls(
            database_url=str(value["database_url"]),
            run_ref=str(value["run_ref"]),
            document_ref=str(value["document_ref"]),
            stage_contract_ref=str(value["stage_contract_ref"]),
            operation_ref=str(value["operation_ref"]),
            partition_ref=str(value["partition_ref"]),
            ordinal=int(value["ordinal"]),
            input_manifest=dict(value.get("input_manifest") or {}),
            artifact_root=Path(str(value["artifact_root"])),
            worker_ref=str(value["worker_ref"]),
            lease_seconds=int(value.get("lease_seconds") or 120),
        )


@dataclass(frozen=True)
class WorkLease:
    spec: DurableWorkSpec
    lease_token: str
    lease_epoch: int
    attempt_ref: str
    backend_pid: int | None = None


def register_work_items(specs: Iterable[DurableWorkSpec]) -> int:
    rows = tuple(specs)
    if not rows:
        return 0
    grouped: dict[str, list[DurableWorkSpec]] = {}
    for spec in rows:
        grouped.setdefault(spec.database_url, []).append(spec)
    for database_url, values in grouped.items():
        connection = _connect(database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    for spec in values:
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_run
                                (run_ref, document_ref, authority_backend,
                                 lifecycle, kernel_key, kernel_contract,
                                 worker_budget)
                            VALUES (%s, %s, 'postgresql', 'running', %s, %s, 1)
                            ON CONFLICT (run_ref) DO NOTHING
                            """,
                            (
                                spec.run_ref,
                                spec.document_ref,
                                spec.operation_ref,
                                DURABLE_WORK_CONTRACT,
                            ),
                        )
                        stage_digest = bytes.fromhex(
                            _canonical_fields_sha256(
                                spec.run_ref,
                                spec.document_ref,
                                spec.stage_contract_ref,
                                spec.operation_ref,
                                dict(spec.input_manifest).get(
                                    "stage_input_identity", {}
                                ),
                            )
                        )
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_stage_instance
                                (stage_instance_ref, run_ref, document_ref,
                                 stage_contract_ref, operation_ref,
                                 input_manifest_sha256)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (stage_instance_ref) DO NOTHING
                            """,
                            (
                                spec.stage_instance_ref,
                                spec.run_ref,
                                spec.document_ref,
                                spec.stage_contract_ref,
                                spec.operation_ref,
                                stage_digest,
                            ),
                        )
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_work_item
                                (work_ref, stage_instance_ref, run_ref,
                                 document_ref, stage_contract_ref, operation_ref,
                                 partition_ref, ordinal, input_manifest,
                                 input_sha256, state)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                                    NULL, %s, 'ready')
                            ON CONFLICT (work_ref) DO NOTHING
                            """,
                            (
                                spec.work_ref,
                                spec.stage_instance_ref,
                                spec.run_ref,
                                spec.document_ref,
                                spec.stage_contract_ref,
                                spec.operation_ref,
                                spec.partition_ref,
                                spec.ordinal,
                                bytes.fromhex(spec.input_sha256),
                            ),
                        )
        finally:
            connection.close()
    return len(rows)


def lease_registered_work(spec: DurableWorkSpec) -> WorkLease | None:
    connection = _connect(spec.database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT state, lease_epoch,
                           coalesce(lease_expires_at < CURRENT_TIMESTAMP, FALSE)
                    FROM execution.semantic_work_item
                    WHERE work_ref = %s
                    FOR UPDATE
                    """,
                    (spec.work_ref,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "durable work item was not registered before dispatch"
                    )
                state, prior_epoch, expired = str(row[0]), int(row[1]), bool(row[2])
                if state == "completed":
                    return None
                if state == "leased" and not expired:
                    return None
                if state not in {"ready", "retryable", "leased"}:
                    raise RuntimeError(f"durable work item is not runnable: {state}")
                token = uuid4().hex
                epoch = prior_epoch + 1
                attempt_ref = f"work-attempt:{spec.work_ref}:{epoch}:{token}"
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'leased', lease_owner = %s,
                        lease_token = %s, lease_epoch = %s,
                        lease_expires_at = CURRENT_TIMESTAMP
                            + (%s * INTERVAL '1 second'),
                        attempt_count = attempt_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE work_ref = %s
                      AND (
                        state IN ('ready', 'retryable')
                        OR (state = 'leased'
                            AND lease_expires_at < CURRENT_TIMESTAMP)
                      )
                    """,
                    (
                        spec.worker_ref,
                        token,
                        epoch,
                        spec.lease_seconds,
                        spec.work_ref,
                    ),
                )
                if cursor.rowcount != 1:
                    return None
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_work_attempt_v2
                        (attempt_ref, work_ref, worker_ref, worker_pid,
                         backend_pid, lease_token, lease_epoch, state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'leased')
                    """,
                    (
                        attempt_ref,
                        spec.work_ref,
                        spec.worker_ref,
                        os.getpid(),
                        backend_pid,
                        token,
                        epoch,
                    ),
                )
                return WorkLease(
                    spec=spec,
                    lease_token=token,
                    lease_epoch=epoch,
                    attempt_ref=attempt_ref,
                    backend_pid=backend_pid,
                )
    finally:
        connection.close()


def _artifact_path(spec: DurableWorkSpec, content_sha256: str) -> Path:
    return spec.artifact_root / content_sha256[:2] / f"{content_sha256}.pkl"


def _write_artifact(
    spec: DurableWorkSpec,
    value: Any,
) -> tuple[Path, bytes, bytes, int]:
    encoded = pickle.dumps(value, protocol=5)
    content_digest = hashlib.sha256(encoded).digest()
    output_digest = bytes.fromhex(_canonical_sha256(value))
    path = _artifact_path(spec, content_digest.hex())
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    stored = path.read_bytes()
    if len(stored) != len(encoded) or hashlib.sha256(stored).digest() != content_digest:
        raise RuntimeError("durable binary artifact changed while sealing")
    return path, content_digest, output_digest, len(encoded)


def _stage_cursor(cursor: Any, stage_instance_ref: str) -> tuple[int, int, int]:
    cursor.execute(
        """
        SELECT
            CASE
                WHEN count(*) = 0 THEN -1
                WHEN count(*) FILTER (WHERE state <> 'completed') = 0
                    THEN max(ordinal)
                ELSE min(ordinal) FILTER (WHERE state <> 'completed') - 1
            END,
            count(*) FILTER (WHERE state = 'completed'),
            count(*)
        FROM execution.semantic_work_item
        WHERE stage_instance_ref = %s
        """,
        (stage_instance_ref,),
    )
    row = cursor.fetchone() or (-1, 0, 0)
    return int(row[0]), int(row[1]), int(row[2])


def _receipt_row(
    *,
    lease: WorkLease,
    artifact_ref: str,
    output_digest: bytes,
    byte_count: int,
    worker_pid: int,
    admission_state: str,
) -> tuple[str, bytes]:
    spec = lease.spec
    receipt_ref = "work-receipt:" + _canonical_fields_sha256(
        DURABLE_WORK_CONTRACT,
        spec.work_ref,
        lease.attempt_ref,
        spec.input_sha256,
        output_digest,
        artifact_ref,
        byte_count,
        lease.lease_epoch,
        worker_pid,
        lease.backend_pid,
        admission_state,
    )
    digest = bytes.fromhex(
        _canonical_fields_sha256(
            receipt_ref,
            spec.work_ref,
            lease.attempt_ref,
            spec.input_sha256,
            output_digest,
            artifact_ref,
            byte_count,
            lease.lease_epoch,
            worker_pid,
            lease.backend_pid,
            admission_state,
        )
    )
    return receipt_ref, digest


def complete_leased_work(
    lease: WorkLease,
    value: Any,
    *,
    worker_pid: int,
) -> dict[str, Any]:
    spec = lease.spec
    path, content_digest, output_digest, byte_count = _write_artifact(spec, value)
    artifact_ref = "artifact-segment:" + _canonical_fields_sha256(
        spec.work_ref,
        content_digest,
        BINARY_ARTIFACT_CONTRACT,
    )
    connection = _connect(spec.database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT state, lease_token, lease_epoch
                    FROM execution.semantic_work_item
                    WHERE work_ref = %s
                    FOR UPDATE
                    """,
                    (spec.work_ref,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "durable work item disappeared before completion"
                    )
                state, token, epoch = str(row[0]), row[1], int(row[2])
                if state == "completed":
                    return {
                        "contract_ref": DURABLE_WORK_CONTRACT,
                        "work_ref": spec.work_ref,
                        "admission_state": "duplicate",
                    }
                if (
                    state != "leased"
                    or token != lease.lease_token
                    or epoch != lease.lease_epoch
                ):
                    cursor.execute(
                        """
                        UPDATE execution.semantic_work_attempt_v2
                        SET state = 'stale', completed_at = CURRENT_TIMESTAMP,
                            error_reason = 'lease_fence_changed'
                        WHERE attempt_ref = %s
                        """,
                        (lease.attempt_ref,),
                    )
                    return {
                        "contract_ref": DURABLE_WORK_CONTRACT,
                        "work_ref": spec.work_ref,
                        "admission_state": "stale",
                    }
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_artifact_segment
                        (artifact_ref, run_ref, document_ref,
                         stage_contract_ref, operation_ref, work_ref,
                         content_sha256, byte_count, media_type,
                         encoding_ref, locator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                            'application/x-python-pickle', %s, %s)
                    ON CONFLICT (artifact_ref) DO NOTHING
                    """,
                    (
                        artifact_ref,
                        spec.run_ref,
                        spec.document_ref,
                        spec.stage_contract_ref,
                        spec.operation_ref,
                        spec.work_ref,
                        content_digest,
                        byte_count,
                        BINARY_ARTIFACT_CONTRACT,
                        str(path),
                    ),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'completed', output_artifact_ref = %s,
                        output_sha256 = %s,
                        completed_at = CURRENT_TIMESTAMP,
                        lease_owner = NULL, lease_token = NULL,
                        lease_expires_at = NULL,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error = NULL,
                        last_error_reason = NULL
                    WHERE work_ref = %s AND state = 'leased'
                      AND lease_token = %s AND lease_epoch = %s
                    """,
                    (
                        artifact_ref,
                        output_digest,
                        spec.work_ref,
                        lease.lease_token,
                        lease.lease_epoch,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("durable work fence changed during completion")
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_attempt_v2
                    SET state = 'completed', completed_at = CURRENT_TIMESTAMP,
                        error = NULL, error_reason = NULL
                    WHERE attempt_ref = %s
                    """,
                    (lease.attempt_ref,),
                )
                receipt_ref, receipt_digest = _receipt_row(
                    lease=lease,
                    artifact_ref=artifact_ref,
                    output_digest=output_digest,
                    byte_count=byte_count,
                    worker_pid=worker_pid,
                    admission_state="accepted",
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_work_receipt
                        (receipt_ref, work_ref, run_ref, payload,
                         payload_sha256, attempt_ref, input_sha256,
                         output_sha256, artifact_ref, byte_count,
                         lease_epoch, worker_pid, backend_pid,
                         admission_state)
                    VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, 'accepted')
                    ON CONFLICT (work_ref) DO NOTHING
                    """,
                    (
                        receipt_ref,
                        spec.work_ref,
                        spec.run_ref,
                        receipt_digest,
                        lease.attempt_ref,
                        bytes.fromhex(spec.input_sha256),
                        output_digest,
                        artifact_ref,
                        byte_count,
                        lease.lease_epoch,
                        worker_pid,
                        lease.backend_pid,
                    ),
                )
                contiguous, completed, total = _stage_cursor(
                    cursor, spec.stage_instance_ref
                )
                cursor_digest = bytes.fromhex(
                    _canonical_fields_sha256(
                        spec.stage_instance_ref,
                        contiguous,
                        completed,
                        total,
                        spec.work_ref,
                        lease.lease_epoch,
                    )
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_stage_cursor
                        (stage_instance_ref, run_ref, document_ref,
                         stage_contract_ref, operation_ref,
                         committed_ordinal, completed_work_count,
                         cursor_manifest, cursor_sha256,
                         total_work_count, last_completed_work_ref,
                         cursor_revision)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s,
                            %s, %s, 1)
                    ON CONFLICT (stage_instance_ref) DO UPDATE SET
                        committed_ordinal = EXCLUDED.committed_ordinal,
                        completed_work_count = EXCLUDED.completed_work_count,
                        cursor_manifest = NULL,
                        cursor_sha256 = EXCLUDED.cursor_sha256,
                        total_work_count = EXCLUDED.total_work_count,
                        last_completed_work_ref = EXCLUDED.last_completed_work_ref,
                        cursor_revision = execution.semantic_stage_cursor.cursor_revision + 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        spec.stage_instance_ref,
                        spec.run_ref,
                        spec.document_ref,
                        spec.stage_contract_ref,
                        spec.operation_ref,
                        contiguous,
                        completed,
                        cursor_digest,
                        total,
                        spec.work_ref,
                    ),
                )
    finally:
        connection.close()
    return {
        "contract_ref": DURABLE_WORK_CONTRACT,
        "work_ref": spec.work_ref,
        "stage_instance_ref": spec.stage_instance_ref,
        "input_sha256": spec.input_sha256,
        "output_sha256": output_digest.hex(),
        "artifact_ref": artifact_ref,
        "byte_count": byte_count,
        "ordinal": spec.ordinal,
        "worker_pid": worker_pid,
        "lease_epoch": lease.lease_epoch,
        "admission_state": "accepted",
        "contiguous_stage_cursor": contiguous,
        "completed_work_count": completed,
        "total_work_count": total,
    }


def load_completed_work(spec: DurableWorkSpec) -> Any | None:
    connection = _connect(spec.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT encode(w.output_sha256, 'hex'),
                       encode(a.content_sha256, 'hex'),
                       a.locator, a.byte_count, a.encoding_ref
                FROM execution.semantic_work_item w
                JOIN execution.semantic_artifact_segment a
                  ON a.artifact_ref = w.output_artifact_ref
                WHERE w.work_ref = %s AND w.state = 'completed'
                """,
                (spec.work_ref,),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    expected_output, expected_content, locator, byte_count, encoding_ref = row
    if str(encoding_ref) != BINARY_ARTIFACT_CONTRACT:
        raise RuntimeError("unsupported durable binary artifact encoding")
    encoded = Path(str(locator)).read_bytes()
    if len(encoded) != int(byte_count):
        raise RuntimeError("durable binary artifact byte count mismatch")
    if hashlib.sha256(encoded).hexdigest() != str(expected_content):
        raise RuntimeError("durable binary artifact content digest mismatch")
    value = pickle.loads(encoded)
    if _canonical_sha256(value) != str(expected_output):
        raise RuntimeError("durable binary artifact semantic digest mismatch")
    return value


def recover_expired_work(database_url: str, *, run_ref: str) -> int:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_attempt_v2 AS attempt
                    SET state = 'stale', completed_at = CURRENT_TIMESTAMP,
                        error = NULL, error_reason = 'lease_expired'
                    FROM execution.semantic_work_item AS work
                    WHERE attempt.work_ref = work.work_ref
                      AND work.run_ref = %s
                      AND work.state = 'leased'
                      AND work.lease_expires_at < CURRENT_TIMESTAMP
                      AND attempt.state = 'leased'
                      AND attempt.lease_epoch = work.lease_epoch
                    """,
                    (run_ref,),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'ready', lease_owner = NULL,
                        lease_token = NULL, lease_expires_at = NULL,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error = NULL,
                        last_error_reason = 'lease_expired'
                    WHERE run_ref = %s AND state = 'leased'
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    """,
                    (run_ref,),
                )
                return cursor.rowcount
    finally:
        connection.close()


def acquire_coordinator_lease(
    database_url: str,
    *,
    run_ref: str,
    coordinator_ref: str,
    lease_seconds: int = 60,
) -> tuple[str, int] | None:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                token = uuid4().hex
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_coordinator_lease
                        (run_ref, coordinator_ref, lease_token,
                         lease_expires_at, backend_pid)
                    VALUES (%s, %s, %s,
                            CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                            pg_backend_pid())
                    ON CONFLICT (run_ref) DO UPDATE SET
                        coordinator_ref = EXCLUDED.coordinator_ref,
                        lease_token = EXCLUDED.lease_token,
                        lease_epoch = execution.semantic_coordinator_lease.lease_epoch + 1,
                        lease_expires_at = EXCLUDED.lease_expires_at,
                        heartbeat_at = CURRENT_TIMESTAMP,
                        backend_pid = EXCLUDED.backend_pid,
                        acquired_at = CURRENT_TIMESTAMP
                    WHERE execution.semantic_coordinator_lease.lease_expires_at
                          < CURRENT_TIMESTAMP
                    RETURNING lease_token, lease_epoch
                    """,
                    (run_ref, coordinator_ref, token, lease_seconds),
                )
                row = cursor.fetchone()
                return (str(row[0]), int(row[1])) if row is not None else None
    finally:
        connection.close()


def linux_parent_death_initializer() -> None:
    """Terminate a local worker when its creating coordinator disappears."""

    if os.name != "posix" or not Path("/proc/self").exists():
        return
    parent_before = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != parent_before or parent_before == 1:
        os.kill(os.getpid(), signal.SIGTERM)


__all__ = [
    "BINARY_ARTIFACT_CONTRACT",
    "DURABLE_WORK_CONTRACT",
    "PARENT_DEATH_CONTRACT",
    "DurableWorkSpec",
    "WorkLease",
    "acquire_coordinator_lease",
    "complete_leased_work",
    "lease_registered_work",
    "linux_parent_death_initializer",
    "load_completed_work",
    "recover_expired_work",
    "register_work_items",
]
