"""Typed parent manifests and nested stage resume receipts.

Parent aggregation commits only references to already-authoritative child work.
No child population, cursor, failure, or receipt is serialized through JSON.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_fields_sha256


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
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT work_ref, output_sha256
                    FROM execution.semantic_work_item
                    WHERE stage_instance_ref = %s AND state = 'completed'
                      AND work_ref = ANY(%s)
                    ORDER BY work_ref
                    """,
                    (stage_instance_ref, list(ordered)),
                )
                rows = tuple(cursor.fetchall())
                if len(rows) != len(ordered):
                    raise RuntimeError(
                        "parent manifest references non-completed child work"
                    )
                observed_refs = tuple(str(row[0]) for row in rows)
                if observed_refs != ordered:
                    raise RuntimeError("parent manifest child identity changed")
                digest_hex = canonical_fields_sha256(
                    stage_instance_ref,
                    logical_output_ref,
                    [
                        (str(work_ref), bytes(output_sha256))
                        for work_ref, output_sha256 in rows
                    ],
                    0,
                )
                manifest_ref = "stage-manifest:" + digest_hex
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_stage_manifest
                        (manifest_ref, stage_instance_ref, run_ref,
                         document_ref, child_work_refs, manifest_sha256,
                         state, committed_at, child_count,
                         logical_output_ref,
                         descendant_payload_bytes_reconstructed)
                    VALUES (%s, %s, %s, %s, NULL, %s, 'committed',
                            CURRENT_TIMESTAMP, %s, %s, 0)
                    ON CONFLICT (stage_instance_ref, manifest_sha256)
                    DO NOTHING
                    """,
                    (
                        manifest_ref,
                        stage_instance_ref,
                        run_ref,
                        document_ref,
                        bytes.fromhex(digest_hex),
                        len(rows),
                        logical_output_ref,
                    ),
                )
                cursor.executemany(
                    """
                    INSERT INTO execution.semantic_stage_manifest_child
                        (manifest_ref, ordinal, work_ref, output_sha256)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (manifest_ref, ordinal) DO NOTHING
                    """,
                    [
                        (manifest_ref, ordinal, work_ref, output_sha256)
                        for ordinal, (work_ref, output_sha256) in enumerate(rows)
                    ],
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_stage_instance
                    SET state = 'completed', updated_at = CURRENT_TIMESTAMP,
                        last_error_reason = NULL,
                        completed_work_count = %s,
                        incomplete_work_count = 0
                    WHERE stage_instance_ref = %s
                    """,
                    (len(rows), stage_instance_ref),
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
    reason = str(
        error.get("reason")
        or error.get("error")
        or error.get("message")
        or "stage_failure"
    )
    connection = _connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) FILTER (WHERE state = 'completed'),
                           count(*) FILTER (WHERE state <> 'completed')
                    FROM execution.semantic_work_item
                    WHERE stage_instance_ref = %s
                    """,
                    (stage_instance_ref,),
                )
                completed, incomplete = cursor.fetchone() or (0, 0)
                cursor.execute(
                    """
                    UPDATE execution.semantic_stage_instance
                    SET state = 'completed_with_failures',
                        updated_at = CURRENT_TIMESTAMP,
                        last_error_reason = %s,
                        completed_work_count = %s,
                        incomplete_work_count = %s
                    WHERE stage_instance_ref = %s
                    """,
                    (
                        reason,
                        int(completed or 0),
                        int(incomplete or 0),
                        stage_instance_ref,
                    ),
                )
    finally:
        connection.close()
    return {
        "stage_instance_ref": stage_instance_ref,
        "state": "completed_with_failures",
        "completed_work_count": int(completed or 0),
        "incomplete_work_count": int(incomplete or 0),
        "error_reason": reason,
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
                SELECT s.stage_instance_ref, s.stage_contract_ref,
                       s.operation_ref, s.state,
                       coalesce(c.committed_ordinal, -1),
                       coalesce(c.cursor_revision, 0),
                       count(w.work_ref) FILTER (WHERE w.state = 'completed'),
                       count(w.work_ref) FILTER (WHERE w.state = 'leased'),
                       count(w.work_ref) FILTER (
                           WHERE w.state IN ('ready', 'retryable')
                       ),
                       count(w.work_ref) FILTER (WHERE w.state = 'failed'),
                       s.last_error_reason
                FROM execution.semantic_stage_instance s
                LEFT JOIN execution.semantic_stage_cursor c
                  USING (stage_instance_ref)
                LEFT JOIN execution.semantic_work_item w
                  USING (stage_instance_ref)
                WHERE s.run_ref = %s AND s.document_ref = %s
                GROUP BY s.stage_instance_ref, s.stage_contract_ref,
                         s.operation_ref, s.state, c.committed_ordinal,
                         c.cursor_revision, s.last_error_reason
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
                    "cursor_revision": int(row[5]),
                    "completed_work_count": int(row[6] or 0),
                    "leased_work_count": int(row[7] or 0),
                    "ready_work_count": int(row[8] or 0),
                    "failed_work_count": int(row[9] or 0),
                    "last_error_reason": str(row[10]) if row[10] else None,
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()
    receipt_ref = "nested-resume:" + canonical_fields_sha256(
        run_ref,
        document_ref,
        [
            (
                stage["stage_instance_ref"],
                stage["stage_contract_ref"],
                stage["operation_ref"],
                stage["state"],
                stage["committed_ordinal"],
                stage["cursor_revision"],
                stage["completed_work_count"],
                stage["leased_work_count"],
                stage["ready_work_count"],
                stage["failed_work_count"],
                stage["last_error_reason"],
            )
            for stage in stages
        ],
    )
    return {
        "schema_version": "sensiblaw.nested-resume-receipt.v2",
        "run_ref": run_ref,
        "document_ref": document_ref,
        "stages": stages,
        "receipt_ref": receipt_ref,
        "serialization": "forbidden",
    }


__all__ = [
    "commit_stage_manifest",
    "nested_resume_receipt",
    "record_stage_failure",
]
