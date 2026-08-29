"""Direct partition commit: local semantic solve plus durable lifecycle only.

Unlike ``commit_numeric_doc`` this path never materialises parser sentence,
parser token, parser entity, or parser-token support rows.  spaCy observations
are consumed into stable local sentence certificates, published through the
semantic PNF evidence boundary, and then the existing durable partition fence
and coverage lifecycle is completed.
"""

from __future__ import annotations

import os
from pathlib import Path
from time import monotonic_ns
from typing import Any

from src.pnf.numeric_hyperfabric import numeric_digest
from src.storage.postgres.semantic_pnf_publication import publish_local_sentence
from src.storage.postgres.sentence_hyperfabric import compile_doc_sentences
from src.storage.postgres.spacy_numeric_projection import (
    _collect_doc,
    _compat_ref,
    _pipeline_capabilities,
    _require_numeric_pnf_capabilities,
)
from src.storage.postgres.spacy_parser_model import (
    DOCBIN_ENCODING,
    ParserPartition,
    ParserStreamingPolicy,
    connect,
)
from src.storage.postgres.spacy_parser_store import (
    _create_boundary_repair,
    refresh_coverage,
    seal_docbin,
)


def commit_direct_doc(
    database_url: str,
    *,
    partition: ParserPartition,
    doc: Any,
    policy: ParserStreamingPolicy,
    artifact_root: Path,
    pipeline: Any,
    elapsed_ns: int,
) -> int:
    """Publish one bounded spaCy doc with zero parser observation rows.

    Returns the number of sentence-local closures published for the partition.
    The durable partition receipt still records parser capabilities and counts;
    those counts describe the consumed observation, not persisted parser rows.
    """

    capabilities = _pipeline_capabilities(pipeline)
    _require_numeric_pnf_capabilities(capabilities)
    sentences, raw_tokens, raw_entities, crossings, _symbols = _collect_doc(
        partition, doc
    )
    compositions = compile_doc_sentences(partition=partition, doc=doc)
    if tuple(row.sentence_digest for row in compositions) != tuple(
        row.sentence_digest for row in sentences
    ):
        raise RuntimeError("direct sentence certificate diverged from owned spaCy surface")
    artifact = (
        seal_docbin(doc, partition=partition, artifact_root=artifact_root)
        if policy.cache_docbin
        else None
    )

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT state, lease_token, lease_epoch
                      FROM execution.semantic_parser_partition
                     WHERE partition_ref = %s
                     FOR UPDATE
                    """,
                    (partition.partition_ref,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("leased parser partition disappeared")
                state, token, epoch = row
                if str(state) == "completed":
                    return 0
                if (
                    str(state) != "leased"
                    or token != partition.lease_token
                    or int(epoch) != partition.lease_epoch
                ):
                    cursor.execute(
                        """
                        UPDATE execution.semantic_parser_attempt
                           SET state = 'stale', completed_at = CURRENT_TIMESTAMP
                         WHERE attempt_ref = %s
                        """,
                        (partition.attempt_ref,),
                    )
                    return 0

                published = 0
                for composition in compositions:
                    publish_local_sentence(
                        cursor,
                        run_ref=partition.run_ref,
                        document_ref=partition.document_ref,
                        composition=composition,
                    )
                    published += 1

                for start_char, end_char, start_byte, end_byte in crossings:
                    _create_boundary_repair(
                        cursor,
                        partition=partition,
                        start_char=start_char,
                        end_char=end_char,
                        start_byte=start_byte,
                        end_byte=end_byte,
                        policy=policy,
                    )

                if partition.resolves_obligation_ref:
                    cursor.execute(
                        """
                        SELECT suspected_start_char, suspected_end_char
                          FROM execution.semantic_parser_boundary_obligation
                         WHERE obligation_ref = %s
                        """,
                        (partition.resolves_obligation_ref,),
                    )
                    obligation = cursor.fetchone()
                    if obligation is not None:
                        suspected_start, suspected_end = map(int, obligation)
                        if any(
                            sentence.start_char <= suspected_start
                            and sentence.end_char >= suspected_end
                            for sentence in compositions
                        ):
                            cursor.execute(
                                """
                                UPDATE execution.semantic_parser_boundary_obligation
                                   SET state = 'resolved', resolved_at = CURRENT_TIMESTAMP
                                 WHERE obligation_ref = %s
                                """,
                                (partition.resolves_obligation_ref,),
                            )

                artifact_ref: str | None = None
                if artifact is not None:
                    artifact_ref, artifact_path, artifact_digest, artifact_bytes = artifact
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_artifact
                            (artifact_ref, partition_ref, content_sha256,
                             byte_count, encoding_ref, locator, cache_only)
                        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT (artifact_ref) DO NOTHING
                        """,
                        (
                            artifact_ref,
                            partition.partition_ref,
                            artifact_digest,
                            artifact_bytes,
                            DOCBIN_ENCODING,
                            str(artifact_path),
                        ),
                    )

                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
                receipt_digest = numeric_digest(
                    b"direct-semantic-partition-receipt-v1",
                    partition.lease_epoch,
                    len(sentences),
                    len(raw_tokens),
                    len(raw_entities),
                    len(crossings),
                    elapsed_ns,
                    artifact[2] if artifact is not None else b"",
                )
                receipt_ref = _compat_ref("parser-receipt:", receipt_digest)
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_partition_receipt
                        (receipt_ref, partition_ref, run_ref, document_ref,
                         parser_contract_ref, model_name, model_version,
                         tokenization, sentence_segmentation, part_of_speech,
                         morphology, dependencies, named_entities,
                         sentence_count, token_count, entity_count,
                         boundary_obligation_count, elapsed_ns,
                         worker_pid, backend_pid, docbin_artifact_ref,
                         receipt_sha256)
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (partition_ref) DO NOTHING
                    """,
                    (
                        receipt_ref,
                        partition.partition_ref,
                        partition.run_ref,
                        partition.document_ref,
                        partition.parser_contract_ref,
                        str(pipeline.meta.get("name") or "unknown"),
                        str(pipeline.meta.get("version") or "unknown"),
                        capabilities["tokenization"],
                        capabilities["sentence_segmentation"],
                        capabilities["part_of_speech"],
                        capabilities["morphology"],
                        capabilities["dependencies"],
                        capabilities["named_entities"],
                        len(sentences),
                        len(raw_tokens),
                        len(raw_entities),
                        len(crossings),
                        elapsed_ns,
                        os.getpid(),
                        backend_pid,
                        artifact_ref,
                        receipt_digest,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_partition
                       SET state = 'completed',
                           lease_owner = NULL,
                           lease_token = NULL,
                           lease_expires_at = NULL,
                           sentence_count = %s,
                           token_count = %s,
                           entity_count = %s,
                           boundary_obligation_count = %s,
                           elapsed_ns = %s,
                           completed_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE partition_ref = %s
                       AND state = 'leased'
                       AND lease_token = %s
                       AND lease_epoch = %s
                    """,
                    (
                        len(sentences),
                        len(raw_tokens),
                        len(raw_entities),
                        len(crossings),
                        elapsed_ns,
                        partition.partition_ref,
                        partition.lease_token,
                        partition.lease_epoch,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "parser partition fence changed during direct completion"
                    )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_attempt
                       SET state = 'completed', completed_at = CURRENT_TIMESTAMP
                     WHERE attempt_ref = %s
                    """,
                    (partition.attempt_ref,),
                )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_outbox
                        (event_ref, event_type_ref, run_ref, document_ref,
                         partition_ref)
                    VALUES (
                        %s, 'parser.partition.completed.v1', %s, %s, %s
                    )
                    ON CONFLICT (event_ref) DO NOTHING
                    """,
                    (
                        _compat_ref(
                            "parser-event:",
                            numeric_digest(
                                b"direct-semantic-partition-v1",
                                partition.partition_ref.encode("utf-8"),
                                partition.lease_epoch,
                            ),
                        ),
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                    ),
                )
                refresh_coverage(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                )
                return published
    finally:
        connection.close()


__all__ = ["commit_direct_doc"]
