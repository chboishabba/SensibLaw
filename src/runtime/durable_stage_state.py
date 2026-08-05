"""Compact parent manifests and nested stage resume receipts.

Parent aggregation never owns child payloads durably.  It commits a manifest of
already-authoritative child work references, while stage failure remains
orthogonal to successful constituent work.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _connect(database_url: str) -> Any:
    import psycopg

    return psycopg.connect(database_url, autocommit=False)


def commit_stage_manifest(
    database_url: str,
    *,
    stage_instance_ref: str,
    run_ref: str,
    document_ref: str,
    child_work_refs: Sequence[str],
    logical_output_ref: str,
) -> str:
    ordered = tuple(sorted(str(value) for value in child_work_refs))
    manifest = {
        "stage_instance_ref": stage_instance_ref,
        "child_work_refs": ordered,
        "logical_output_ref": logical_output_ref,
        "descendant_payload_bytes_reconstructed": 0,
    }
    manifest_ref = "stage-manifest:" + canonical_sha256(manifest)
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_work_item
                    WHERE stage_instance_ref = %s AND state = 'completed'
                      AND work_ref = ANY(%s)
                    """,
                    (stage_instance_ref, list(ordered)),
                )
                completed = int(cursor.fetchone()[0])
                if completed != len(ordered):
                    raise RuntimeError("parent manifest references non-completed child work")
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_stage_manifest
                        (manifest_ref, stage_instance_ref, run_ref, document_ref,
                         child_work_refs, manifest_sha256, state, committed_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, 'committed', CURRENT_TIMESTAMP)
                    ON CONFLICT (stage_instance_ref, manifest_sha256) DO NOTHING
                    """,
                    (
                        manifest_ref,
                        stage_instance_ref,
                        run_ref,
                        document_ref,
                        _json(ordered),
                        _digest(manifest),
                    ),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_stage_instance
                    SET state = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE stage_instance_ref = %s
                    """,
                    (stage_instance_ref,),
                )
    finally:
        connection.close()
    return manifest_ref


def record_stage_failure(
    database_url: str,
    *,
    stage_instance_ref: str,
    error: Mapping[str, Any],
) -> dict[str, Any]:
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_stage_instance
                    SET state = 'completed_with_failures', updated_at = CURRENT_TIMESTAMP
                    WHERE stage_instance_ref = %s
                    """,
                    (stage_instance_ref,),
                )
                cursor.execute(
                    """
                    SELECT count(*) FILTER (WHERE state = 'completed'),
                           count(*) FILTER (WHERE state <> 'completed')
                    FROM execution.semantic_work_item
                    WHERE stage_instance_ref = %s
                    """,
                    (stage_instance_ref,),
                )
                completed, incomplete = cursor.fetchone()
    finally:
        connection.close()
    return {
        "stage_instance_ref": stage_instance_ref,
        "state": "completed_with_failures",
        "completed_work_count": int(completed),
        "incomplete_work_count": int(incomplete),
        "error": dict(error),
        "successful_work_preserved": True,
    }


def nested_resume_receipt(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.stage_instance_ref, s.stage_contract_ref, s.operation_ref,
                       s.state, coalesce(c.committed_ordinal, -1),
                       count(w.work_ref) FILTER (WHERE w.state = 'completed'),
                       count(w.work_ref) FILTER (WHERE w.state = 'leased'),
                       count(w.work_ref) FILTER (WHERE w.state IN ('ready', 'retryable')),
                       count(w.work_ref) FILTER (WHERE w.state = 'failed')
                FROM execution.semantic_stage_instance s
                LEFT JOIN execution.semantic_stage_cursor c USING (stage_instance_ref)
                LEFT JOIN execution.semantic_work_item w USING (stage_instance_ref)
                WHERE s.run_ref = %s AND s.document_ref = %s
                GROUP BY s.stage_instance_ref, s.stage_contract_ref,
                         s.operation_ref, s.state, c.committed_ordinal
                ORDER BY s.stage_contract_ref, s.operation_ref
                """,
                (run_ref, document_ref),
            )
            stages = [
                {
                    "stage_instance_ref": str(row[0]),
                    "stage_contract_ref": str(row[1]),
                    "operation_ref": str(row[2]),
                    "state": str(row[3]),
                    "committed_ordinal": int(row[4]),
                    "completed_work_count": int(row[5]),
                    "leased_work_count": int(row[6]),
                    "ready_work_count": int(row[7]),
                    "failed_work_count": int(row[8]),
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()
    payload = {
        "schema_version": "sensiblaw.nested-resume-receipt.v1",
        "run_ref": run_ref,
        "document_ref": document_ref,
        "stages": stages,
    }
    payload["receipt_ref"] = "nested-resume:" + canonical_sha256(payload)
    return payload


__all__ = [
    "commit_stage_manifest",
    "nested_resume_receipt",
    "record_stage_failure",
]
