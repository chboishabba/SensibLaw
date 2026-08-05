"""Transactional work-item durability for bounded document execution.

A worker may own computation temporarily; PostgreSQL owns progress durably.
Each completed unit commits its immutable artifact, receipt, nested stage cursor,
work state and outbox event before returning success to a coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import json
import os
from pathlib import Path
import signal
from typing import Any, Iterable, Mapping
from uuid import uuid4

from src.policy.carriers.canonical import canonical_sha256


DURABLE_WORK_CONTRACT = "postgres-durable-work-item:v1"
PARENT_DEATH_CONTRACT = "linux-pdeathsig:v1"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


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
        return canonical_sha256(dict(self.input_manifest))

    @property
    def stage_instance_ref(self) -> str:
        return "stage-instance:" + canonical_sha256(
            {
                "run_ref": self.run_ref,
                "document_ref": self.document_ref,
                "stage_contract_ref": self.stage_contract_ref,
                "operation_ref": self.operation_ref,
                "input_identity": dict(self.input_manifest).get("stage_input_identity", {}),
            }
        )

    @property
    def work_ref(self) -> str:
        return "work-item:" + canonical_sha256(
            {
                "run_ref": self.run_ref,
                "document_ref": self.document_ref,
                "stage_contract_ref": self.stage_contract_ref,
                "operation_ref": self.operation_ref,
                "partition_ref": self.partition_ref,
                "input_sha256": self.input_sha256,
            }
        )

    def to_dict(self) -> dict[str, Any]:
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
                                (run_ref, document_ref, authority_backend, lifecycle,
                                 kernel_key, kernel_contract, worker_budget)
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
                        stage_identity = {
                            "run_ref": spec.run_ref,
                            "document_ref": spec.document_ref,
                            "stage_contract_ref": spec.stage_contract_ref,
                            "operation_ref": spec.operation_ref,
                        }
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_stage_instance
                                (stage_instance_ref, run_ref, document_ref,
                                 stage_contract_ref, operation_ref, input_manifest_sha256)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (stage_instance_ref) DO NOTHING
                            """,
                            (
                                spec.stage_instance_ref,
                                spec.run_ref,
                                spec.document_ref,
                                spec.stage_contract_ref,
                                spec.operation_ref,
                                _digest(stage_identity),
                            ),
                        )
                        cursor.execute(
                            """
                            INSERT INTO execution.semantic_work_item
                                (work_ref, stage_instance_ref, run_ref, document_ref,
                                 stage_contract_ref, operation_ref, partition_ref,
                                 ordinal, input_manifest, input_sha256, state)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'ready')
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
                                _json(spec.input_manifest),
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
                    SELECT state, lease_epoch
                    FROM execution.semantic_work_item
                    WHERE work_ref = %s
                    FOR UPDATE
                    """,
                    (spec.work_ref,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("durable work item was not registered before dispatch")
                state, prior_epoch = str(row[0]), int(row[1])
                if state == "completed":
                    return None
                if state == "leased":
                    cursor.execute(
                        "SELECT lease_expires_at < CURRENT_TIMESTAMP FROM execution.semantic_work_item WHERE work_ref = %s",
                        (spec.work_ref,),
                    )
                    expired = bool(cursor.fetchone()[0])
                    if not expired:
                        return None
                token = uuid4().hex
                epoch = prior_epoch + 1
                attempt_ref = f"work-attempt:{spec.work_ref}:{epoch}:{token}"
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'leased', lease_owner = %s, lease_token = %s,
                        lease_epoch = %s,
                        lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                        attempt_count = attempt_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE work_ref = %s AND state <> 'completed'
                    """,
                    (spec.worker_ref, token, epoch, spec.lease_seconds, spec.work_ref),
                )
                if cursor.rowcount != 1:
                    return None
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_work_attempt_v2
                        (attempt_ref, work_ref, worker_ref, worker_pid, backend_pid,
                         lease_token, lease_epoch, state)
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
                return WorkLease(spec, token, epoch, attempt_ref)
    finally:
        connection.close()


def _artifact_path(spec: DurableWorkSpec, output_sha256: str) -> Path:
    return spec.artifact_root / output_sha256[:2] / f"{output_sha256}.json"


def _write_artifact(spec: DurableWorkSpec, value: Any) -> tuple[Path, bytes, int]:
    encoded = (_json(value) + "\n").encode("utf-8")
    digest = bytes.fromhex(canonical_sha256(value))
    path = _artifact_path(spec, digest.hex())
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    if path.stat().st_size != len(encoded):
        raise RuntimeError("durable work artifact size mismatch")
    return path, digest, len(encoded)


def complete_leased_work(lease: WorkLease, value: Any, *, worker_pid: int) -> dict[str, Any]:
    spec = lease.spec
    path, output_digest, byte_count = _write_artifact(spec, value)
    artifact_ref = "artifact-segment:" + output_digest.hex()
    receipt_payload = {
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
    }
    receipt_ref = "work-receipt:" + canonical_sha256(receipt_payload)
    cursor_payload = {
        "stage_instance_ref": spec.stage_instance_ref,
        "committed_ordinal": spec.ordinal,
        "last_work_ref": spec.work_ref,
    }
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
                    raise RuntimeError("durable work item disappeared before completion")
                state, token, epoch = str(row[0]), row[1], int(row[2])
                if state == "completed":
                    return {**receipt_payload, "admission_state": "duplicate"}
                if token != lease.lease_token or epoch != lease.lease_epoch:
                    cursor.execute(
                        "UPDATE execution.semantic_work_attempt_v2 SET state = 'stale', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s",
                        (lease.attempt_ref,),
                    )
                    return {**receipt_payload, "admission_state": "stale"}
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_artifact_segment
                        (artifact_ref, run_ref, document_ref, stage_contract_ref,
                         operation_ref, work_ref, content_sha256, byte_count,
                         media_type, encoding_ref, locator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                            'application/json', 'canonical-json:v1', %s)
                    ON CONFLICT (artifact_ref) DO NOTHING
                    """,
                    (
                        artifact_ref,
                        spec.run_ref,
                        spec.document_ref,
                        spec.stage_contract_ref,
                        spec.operation_ref,
                        spec.work_ref,
                        output_digest,
                        byte_count,
                        str(path),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_work_receipt
                        (receipt_ref, work_ref, run_ref, payload, payload_sha256)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (work_ref) DO NOTHING
                    """,
                    (receipt_ref, spec.work_ref, spec.run_ref, _json(receipt_payload), _digest(receipt_payload)),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'completed', output_artifact_ref = %s,
                        output_sha256 = %s, completed_at = CURRENT_TIMESTAMP,
                        lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE work_ref = %s AND lease_token = %s AND lease_epoch = %s
                    """,
                    (artifact_ref, output_digest, spec.work_ref, lease.lease_token, lease.lease_epoch),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("durable work fence changed during completion")
                cursor.execute(
                    "UPDATE execution.semantic_work_attempt_v2 SET state = 'completed', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s",
                    (lease.attempt_ref,),
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_stage_cursor
                        (stage_instance_ref, run_ref, document_ref, stage_contract_ref,
                         operation_ref, committed_ordinal, completed_work_count,
                         cursor_manifest, cursor_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s::jsonb, %s)
                    ON CONFLICT (stage_instance_ref) DO UPDATE SET
                        committed_ordinal = GREATEST(semantic_stage_cursor.committed_ordinal, EXCLUDED.committed_ordinal),
                        completed_work_count = (
                            SELECT count(*) FROM execution.semantic_work_item
                            WHERE stage_instance_ref = EXCLUDED.stage_instance_ref
                              AND state = 'completed'
                        ),
                        cursor_manifest = EXCLUDED.cursor_manifest,
                        cursor_sha256 = EXCLUDED.cursor_sha256,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        spec.stage_instance_ref,
                        spec.run_ref,
                        spec.document_ref,
                        spec.stage_contract_ref,
                        spec.operation_ref,
                        spec.ordinal,
                        _json(cursor_payload),
                        _digest(cursor_payload),
                    ),
                )
    finally:
        connection.close()
    return {**receipt_payload, "admission_state": "accepted"}


def load_completed_work(spec: DurableWorkSpec) -> Any | None:
    connection = _connect(spec.database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT encode(w.output_sha256, 'hex'), a.locator, a.byte_count
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
    expected_digest, locator, byte_count = str(row[0]), Path(str(row[1])), int(row[2])
    encoded = locator.read_bytes()
    if len(encoded) != byte_count:
        raise RuntimeError("durable work artifact byte count mismatch")
    value = json.loads(encoded)
    if canonical_sha256(value) != expected_digest:
        raise RuntimeError("durable work artifact digest mismatch")
    return value


def recover_expired_work(database_url: str, *, run_ref: str) -> int:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'retryable', lease_owner = NULL, lease_token = NULL,
                        lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE run_ref = %s AND state = 'leased'
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    """,
                    (run_ref,),
                )
                recovered = cursor.rowcount
                cursor.execute(
                    "UPDATE execution.semantic_work_item SET state = 'ready' WHERE run_ref = %s AND state = 'retryable'",
                    (run_ref,),
                )
                return recovered
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
                        (run_ref, coordinator_ref, lease_token, lease_expires_at, backend_pid)
                    VALUES (%s, %s, %s,
                            CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'), pg_backend_pid())
                    ON CONFLICT (run_ref) DO UPDATE SET
                        coordinator_ref = EXCLUDED.coordinator_ref,
                        lease_token = EXCLUDED.lease_token,
                        lease_epoch = semantic_coordinator_lease.lease_epoch + 1,
                        lease_expires_at = EXCLUDED.lease_expires_at,
                        heartbeat_at = CURRENT_TIMESTAMP,
                        backend_pid = EXCLUDED.backend_pid,
                        acquired_at = CURRENT_TIMESTAMP
                    WHERE semantic_coordinator_lease.lease_expires_at < CURRENT_TIMESTAMP
                    RETURNING lease_token, lease_epoch
                    """,
                    (run_ref, coordinator_ref, token, lease_seconds),
                )
                row = cursor.fetchone()
                return (str(row[0]), int(row[1])) if row is not None else None
    finally:
        connection.close()


def linux_parent_death_initializer() -> None:
    """Terminate a local pool worker if its creating coordinator disappears."""

    if os.name != "posix" or not Path("/proc/self").exists():
        return
    parent_before = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_pdeathsig = 1
    if libc.prctl(pr_set_pdeathsig, signal.SIGTERM) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != parent_before or parent_before == 1:
        os.kill(os.getpid(), signal.SIGTERM)


__all__ = [
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
