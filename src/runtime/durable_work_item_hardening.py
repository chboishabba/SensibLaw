"""Safety hardening for durable work-item admission.

This module keeps the deterministic identities from :mod:`durable_work_items`
while tightening runnable-state selection, work-scoped artifact attribution,
contiguous stage cursors and expired-attempt accounting.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.policy.carriers.canonical import canonical_sha256
from src.runtime.durable_work_items import (
    DURABLE_WORK_CONTRACT,
    DurableWorkSpec,
    WorkLease,
    _connect,
    _digest,
    _json,
)


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
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_item
                    SET state = 'leased', lease_owner = %s, lease_token = %s,
                        lease_epoch = %s,
                        lease_expires_at = CURRENT_TIMESTAMP
                            + (%s * INTERVAL '1 second'),
                        attempt_count = attempt_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE work_ref = %s
                      AND (
                        state IN ('ready', 'retryable')
                        OR (
                            state = 'leased'
                            AND lease_expires_at < CURRENT_TIMESTAMP
                        )
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
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
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
                return WorkLease(spec, token, epoch, attempt_ref)
    finally:
        connection.close()


def _write_artifact(spec: DurableWorkSpec, value: Any) -> tuple[Path, bytes, int]:
    encoded = (_json(value) + "\n").encode("utf-8")
    digest = bytes.fromhex(canonical_sha256(value))
    path = spec.artifact_root / digest.hex()[:2] / f"{digest.hex()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    if path.stat().st_size != len(encoded):
        raise RuntimeError("durable work artifact size mismatch")
    return path, digest, len(encoded)


def _stage_cursor(cursor: Any, stage_instance_ref: str) -> tuple[int, int]:
    """Return highest contiguous completed ordinal and total completion count."""

    cursor.execute(
        """
        SELECT
            CASE
                WHEN count(*) = 0 THEN -1
                WHEN count(*) FILTER (WHERE state <> 'completed') = 0
                    THEN max(ordinal)
                ELSE min(ordinal) FILTER (WHERE state <> 'completed') - 1
            END AS contiguous_ordinal,
            count(*) FILTER (WHERE state = 'completed') AS completed_count
        FROM execution.semantic_work_item
        WHERE stage_instance_ref = %s
        """,
        (stage_instance_ref,),
    )
    row = cursor.fetchone()
    return int(row[0]), int(row[1])


def complete_leased_work(
    lease: WorkLease,
    value: Any,
    *,
    worker_pid: int,
) -> dict[str, Any]:
    spec = lease.spec
    path, output_digest, byte_count = _write_artifact(spec, value)
    artifact_ref = "artifact-segment:" + canonical_sha256(
        {"work_ref": spec.work_ref, "content_sha256": output_digest.hex()}
    )
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
                    return {**receipt_payload, "admission_state": "duplicate"}
                if (
                    state != "leased"
                    or token != lease.lease_token
                    or epoch != lease.lease_epoch
                ):
                    cursor.execute(
                        """
                        UPDATE execution.semantic_work_attempt_v2
                        SET state = 'stale', completed_at = CURRENT_TIMESTAMP
                        WHERE attempt_ref = %s
                        """,
                        (lease.attempt_ref,),
                    )
                    return {**receipt_payload, "admission_state": "stale"}
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_artifact_segment
                        (artifact_ref, run_ref, document_ref,
                         stage_contract_ref, operation_ref, work_ref,
                         content_sha256, byte_count, media_type,
                         encoding_ref, locator)
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
                    (
                        receipt_ref,
                        spec.work_ref,
                        spec.run_ref,
                        _json(receipt_payload),
                        _digest(receipt_payload),
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
                        updated_at = CURRENT_TIMESTAMP
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
                    SET state = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE attempt_ref = %s
                    """,
                    (lease.attempt_ref,),
                )
                contiguous_ordinal, completed_count = _stage_cursor(
                    cursor,
                    spec.stage_instance_ref,
                )
                cursor_payload = {
                    "stage_instance_ref": spec.stage_instance_ref,
                    "committed_ordinal": contiguous_ordinal,
                    "completed_work_count": completed_count,
                    "last_completed_work_ref": spec.work_ref,
                }
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_stage_cursor
                        (stage_instance_ref, run_ref, document_ref,
                         stage_contract_ref, operation_ref,
                         committed_ordinal, completed_work_count,
                         cursor_manifest, cursor_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (stage_instance_ref) DO UPDATE SET
                        committed_ordinal = EXCLUDED.committed_ordinal,
                        completed_work_count = EXCLUDED.completed_work_count,
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
                        contiguous_ordinal,
                        completed_count,
                        _json(cursor_payload),
                        _digest(cursor_payload),
                    ),
                )
    finally:
        connection.close()
    return {
        **receipt_payload,
        "admission_state": "accepted",
        "contiguous_stage_cursor": contiguous_ordinal,
        "completed_work_count": completed_count,
    }


def recover_expired_work(database_url: str, *, run_ref: str) -> int:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_work_attempt_v2 AS attempt
                    SET state = 'stale',
                        completed_at = CURRENT_TIMESTAMP,
                        error = jsonb_build_object('reason', 'lease_expired')
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
                        last_error = jsonb_build_object(
                            'reason', 'lease_expired'
                        )
                    WHERE run_ref = %s AND state = 'leased'
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    """,
                    (run_ref,),
                )
                return cursor.rowcount
    finally:
        connection.close()


__all__ = [
    "complete_leased_work",
    "lease_registered_work",
    "recover_expired_work",
]
