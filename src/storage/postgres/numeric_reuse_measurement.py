"""Controlled corpus-learning measurements for strict numeric compilation."""

from __future__ import annotations

from src.storage.postgres.numeric_incremental_runtime_store import (
    NumericIncrementalRuntimeStore,
)
from src.storage.postgres.spacy_parser_model import connect


NUMERIC_COMPILER_CONSUMER_REF = "compiler:numeric-pnf"
NUMERIC_COMPILER_QUERY_REF = "compile"


def _sha256_hex_bytes(value: str, field: str) -> bytes:
    if len(value) != 64:
        raise ValueError(f"{field} must be a 64-character SHA-256 hex digest")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if len(decoded) != 32:
        raise ValueError(f"{field} must decode to 32 bytes")
    return decoded


def record_numeric_compiler_reuse_measurement(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text_sha256: str,
    compiler_config_sha256: str,
) -> int:
    """Record one controlled strict-compiler observation.

    Run/document integer ids are PostgreSQL-local coordinates and are looked up
    from the stable refs. Workload and compiler-configuration identity are kept
    separate so repeated source work under a changed compiler cannot be used to
    claim a learning non-increase theorem.
    """

    authority_digest = _sha256_hex_bytes(
        canonical_text_sha256, "canonical_text_sha256"
    )
    config_digest = _sha256_hex_bytes(
        compiler_config_sha256, "compiler_config_sha256"
    )
    workload_digest = NumericIncrementalRuntimeStore.controlled_workload_digest(
        authority_digest=authority_digest,
        consumer_ref=NUMERIC_COMPILER_CONSUMER_REF,
        query_ref=NUMERIC_COMPILER_QUERY_REF,
    )

    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT run_identity.run_id,document_identity.document_id
                  FROM execution.semantic_pnf_run_identity AS run_identity
                  CROSS JOIN execution.semantic_pnf_document_identity AS document_identity
                 WHERE run_identity.run_ref=%s
                   AND document_identity.document_ref=%s
                """,
                (run_ref, document_ref),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    "numeric run/document identity is unavailable for reuse measurement"
                )
            run_id, document_id = int(row[0]), int(row[1])
    finally:
        connection.close()

    runtime = NumericIncrementalRuntimeStore(database_url)
    return runtime.record_controlled_reuse_measurement(
        run_id=run_id,
        document_id=document_id,
        workload_ref=f"numeric-document:{document_ref}",
        workload_digest=workload_digest,
        consumer_ref=NUMERIC_COMPILER_CONSUMER_REF,
        compiler_config_digest=config_digest,
    )


__all__ = [
    "NUMERIC_COMPILER_CONSUMER_REF",
    "NUMERIC_COMPILER_QUERY_REF",
    "record_numeric_compiler_reuse_measurement",
]
