"""Commit one leased spaCy partition through the canonical direct sentence path.

Parser partition/coverage rows remain the durable scheduling carrier, but sentence,
token and entity observation rows are never materialised. Observed counts are kept
in the partition receipt; semantic support is admitted through stable source evidence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.pnf.direct_sentence_compiler import compile_packed_sentence
from src.pnf.direct_sentence_publication import resolve_direct_publications
from src.pnf.numeric_hyperfabric import numeric_digest
from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.storage.postgres.direct_sentence_admission import (
    register_and_lease_sentence_work_batch,
)
from src.storage.postgres.numeric_hyperfabric_store import _load_profile
from src.storage.postgres.numeric_sentence_evidence_admission import EvidenceSupportCursor
from src.storage.postgres.resolved_direct_sentence_admission import (
    publish_preleased_resolved_direct_sentence,
)
from src.storage.postgres.spacy_parser_model import (
    DOCBIN_ENCODING,
    ParserPartition,
    ParserStreamingPolicy,
    connect,
    typed_ref,
)
from src.storage.postgres.spacy_parser_store import (
    _create_boundary_repair,
    refresh_coverage,
    seal_docbin,
)


def _capabilities(pipeline: Any) -> dict[str, bool]:
    pipe_names = tuple(pipeline.pipe_names)
    return {
        "tokenization": True,
        "sentence_segmentation": any(
            name in pipe_names for name in ("parser", "senter", "sentencizer")
        ),
        "part_of_speech": any(
            name in pipe_names for name in ("tagger", "morphologizer")
        ),
        "morphology": any(name in pipe_names for name in ("tagger", "morphologizer")),
        "dependencies": "parser" in pipe_names,
        "named_entities": "ner" in pipe_names,
    }


def _require_direct_capabilities(capabilities: dict[str, bool]) -> None:
    missing = tuple(
        name
        for name in ("sentence_segmentation", "part_of_speech", "dependencies")
        if not capabilities[name]
    )
    if missing:
        raise RuntimeError(
            "direct numeric PNF requires parser capabilities: " + ", ".join(missing)
        )


def commit_direct_partition(
    database_url: str,
    *,
    partition: ParserPartition,
    doc: Any,
    policy: ParserStreamingPolicy,
    artifact_root: Path,
    pipeline: Any,
    elapsed_ns: int,
) -> int:
    """Publish a leased partition and complete its durable scheduling fence."""

    capabilities = _capabilities(pipeline)
    _require_direct_capabilities(capabilities)
    packed = pack_spacy_partition(partition, doc)
    compiled = tuple(compile_packed_sentence(fibre=fibre) for fibre in packed.sentences)
    if any(receipt.database_crossings != 0 for receipt in compiled):
        raise RuntimeError("direct local sentence solve reported a database crossing")
    token_count = sum(len(fibre.tokens) for fibre in packed.sentences)
    entity_count = sum(
        1
        for entity in getattr(doc, "ents", ())
        if partition.context_start_char + int(entity.start_char) >= partition.owner_start_char
        and partition.context_start_char + int(entity.end_char) <= partition.owner_end_char
    )
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
                    raise RuntimeError("leased direct partition disappeared")
                state, lease_token, lease_epoch = row
                if str(state) == "completed":
                    return 0
                if (
                    str(state) != "leased"
                    or str(lease_token) != partition.lease_token
                    or int(lease_epoch) != partition.lease_epoch
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

                publications = resolve_direct_publications(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                    fibres=packed.sentences,
                    directs=compiled,
                )
                profile = _load_profile(cursor)
                sentence_leases = register_and_lease_sentence_work_batch(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                    fibres=packed.sentences,
                )
                publication_cursor = EvidenceSupportCursor(
                    cursor,
                    defer_interface_ancestors=True,
                    reuse_sentence_stages=True,
                )
                for lease, publication in zip(
                    sentence_leases,
                    publications,
                    strict=True,
                ):
                    publish_preleased_resolved_direct_sentence(
                        publication_cursor,
                        lease=lease,
                        publication=publication,
                        profile=profile,
                    )

                for start_char, end_char, start_byte, end_byte in packed.boundary_obligations:
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
                            fibre.start_char <= suspected_start
                            and fibre.end_char >= suspected_end
                            for fibre in packed.sentences
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
                    b"direct-partition-receipt:v1",
                    partition.partition_ref.encode("utf-8"),
                    partition.lease_epoch,
                    len(packed.sentences),
                    token_count,
                    entity_count,
                    len(packed.boundary_obligations),
                    elapsed_ns,
                    artifact[2] if artifact is not None else b"",
                )
                receipt_ref = "parser-receipt:" + receipt_digest.hex()
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        len(packed.sentences),
                        token_count,
                        entity_count,
                        len(packed.boundary_obligations),
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
                        len(packed.sentences),
                        token_count,
                        entity_count,
                        len(packed.boundary_obligations),
                        elapsed_ns,
                        partition.partition_ref,
                        partition.lease_token,
                        partition.lease_epoch,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("direct partition fence changed during completion")
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
                        (event_ref, event_type_ref, run_ref, document_ref, partition_ref)
                    VALUES (%s, 'parser.partition.completed.v1', %s, %s, %s)
                    ON CONFLICT (event_ref) DO NOTHING
                    """,
                    (
                        typed_ref(
                            "parser-event:",
                            partition.partition_ref,
                            "direct-completed",
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
                return len(packed.sentences)
    finally:
        connection.close()


__all__ = ["commit_direct_partition"]
