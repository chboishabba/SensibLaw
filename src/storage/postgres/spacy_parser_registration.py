"""Register one immutable parser plan or reuse the existing durable plan."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.storage.postgres.spacy_parser_model import (
    SOURCE_ENCODING,
    STREAMING_SPACY_CONTRACT,
    ParserPartition,
    connect,
)


def register_or_reuse_execution(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    source_path: Path,
    source_digest: bytes,
    source_bytes: int,
    source_chars: int,
    parser_contract_ref: str,
    proposed_partitions: Sequence[ParserPartition],
) -> bool:
    """Register a new plan, or validate and reuse the existing one.

    Returns ``True`` only when this transaction created the initial plan.
    Physical parser tuning is not semantic identity: after the first partition
    is registered, later invocations never replace or extend the plan merely
    because current target/context settings differ.
    """

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (run_ref + "\x1f" + document_ref + "\x1fparser-plan",),
                )
                cursor.execute(
                    """
                    SELECT source_ref, content_sha256, byte_count, char_count,
                           encoding_ref, locator
                    FROM execution.semantic_parser_source
                    WHERE run_ref = %s AND document_ref = %s
                    FOR UPDATE
                    """,
                    (run_ref, document_ref),
                )
                source_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT count(*),
                           count(DISTINCT source_ref),
                           count(DISTINCT parser_contract_ref),
                           min(source_ref),
                           min(parser_contract_ref)
                    FROM execution.semantic_parser_partition
                    WHERE run_ref = %s AND document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                (
                    existing_count,
                    source_count,
                    contract_count,
                    existing_source_ref,
                    existing_contract_ref,
                ) = cursor.fetchone()
                existing_count = int(existing_count)
                if existing_count:
                    if source_row is None:
                        raise RuntimeError(
                            "parser partitions exist without registered source authority"
                        )
                    if int(source_count) != 1 or int(contract_count) != 1:
                        raise RuntimeError(
                            "parser partition plan contains mixed source or parser contracts"
                        )
                    if str(existing_source_ref) != source_ref:
                        raise RuntimeError("parser resume source identity changed")
                    if str(existing_contract_ref) != parser_contract_ref:
                        raise RuntimeError("parser resume contract identity changed")
                    (
                        registered_ref,
                        registered_digest,
                        registered_bytes,
                        registered_chars,
                        registered_encoding,
                        registered_locator,
                    ) = source_row
                    if (
                        str(registered_ref) != source_ref
                        or bytes(registered_digest) != source_digest
                        or int(registered_bytes) != source_bytes
                        or int(registered_chars) != source_chars
                        or str(registered_encoding) != SOURCE_ENCODING
                    ):
                        raise RuntimeError("parser resume source evidence changed")
                    if not Path(str(registered_locator)).is_file():
                        raise FileNotFoundError(
                            "registered parser source artifact is unavailable"
                        )
                    return False

                cursor.execute(
                    """
                    INSERT INTO execution.semantic_run
                        (run_ref, document_ref, authority_backend, lifecycle,
                         kernel_key, kernel_contract, worker_budget)
                    VALUES (%s, %s, 'postgresql', 'running',
                            'parser.streaming-spacy', %s, 1)
                    ON CONFLICT (run_ref) DO NOTHING
                    """,
                    (run_ref, document_ref, STREAMING_SPACY_CONTRACT),
                )
                if source_row is None:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_source
                            (source_ref, run_ref, document_ref, content_sha256,
                             byte_count, char_count, encoding_ref, locator)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            source_ref,
                            run_ref,
                            document_ref,
                            source_digest,
                            source_bytes,
                            source_chars,
                            SOURCE_ENCODING,
                            str(source_path),
                        ),
                    )
                else:
                    if (
                        str(source_row[0]) != source_ref
                        or bytes(source_row[1]) != source_digest
                        or int(source_row[2]) != source_bytes
                        or int(source_row[3]) != source_chars
                        or str(source_row[4]) != SOURCE_ENCODING
                    ):
                        raise RuntimeError("registered parser source identity changed")

                for partition in proposed_partitions:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_partition
                            (partition_ref, run_ref, document_ref, source_ref,
                             parser_contract_ref, partition_kind, sequence_no,
                             owner_start_char, owner_end_char,
                             context_start_char, context_end_char,
                             owner_start_byte, owner_end_byte,
                             context_start_byte, context_end_byte,
                             repair_depth)
                        VALUES (%s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            partition.partition_ref,
                            run_ref,
                            document_ref,
                            source_ref,
                            parser_contract_ref,
                            partition.partition_kind,
                            partition.sequence_no,
                            partition.owner_start_char,
                            partition.owner_end_char,
                            partition.context_start_char,
                            partition.context_end_char,
                            partition.owner_start_byte,
                            partition.owner_end_byte,
                            partition.context_start_byte,
                            partition.context_end_byte,
                            partition.repair_depth,
                        ),
                    )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_document_coverage
                        (run_ref, document_ref, total_partitions)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (run_ref, document_ref) DO UPDATE SET
                        total_partitions = EXCLUDED.total_partitions,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (run_ref, document_ref, len(proposed_partitions)),
                )
                return True
    finally:
        connection.close()


__all__ = ["register_or_reuse_execution"]
