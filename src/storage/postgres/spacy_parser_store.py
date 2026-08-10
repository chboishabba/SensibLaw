"""Leasing and transactional admission for typed spaCy observations."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from src.policy.carriers.canonical import canonical_fields_sha256
from src.storage.postgres.spacy_parser_model import (
    DOCBIN_ENCODING,
    SEGMENTATION_CONTRACT,
    SOURCE_ENCODING,
    STREAMING_SPACY_CONTRACT,
    TOKEN_IDENTITY_CONTRACT,
    ParserExecutionSummary,
    ParserPartition,
    ParserStreamingPolicy,
    connect,
    typed_ref,
)


def register_execution(
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
    partitions: Sequence[ParserPartition],
) -> None:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
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
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_source
                        (source_ref, run_ref, document_ref, content_sha256,
                         byte_count, char_count, encoding_ref, locator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_ref) DO NOTHING
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
                for partition in partitions:
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
                        ON CONFLICT (partition_ref) DO NOTHING
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
                        total_partitions = GREATEST(
                            execution.semantic_parser_document_coverage.total_partitions,
                            EXCLUDED.total_partitions
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (run_ref, document_ref, len(partitions)),
                )
    finally:
        connection.close()


def lease_partitions(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    batch_size: int,
    lease_seconds: int,
) -> tuple[ParserPartition, ...]:
    connection = connect(database_url)
    leased: list[ParserPartition] = []
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.partition_ref, p.document_ref, p.source_ref,
                           s.locator, p.parser_contract_ref, p.partition_kind,
                           p.sequence_no, p.owner_start_char, p.owner_end_char,
                           p.context_start_char, p.context_end_char,
                           p.owner_start_byte, p.owner_end_byte,
                           p.context_start_byte, p.context_end_byte,
                           p.repair_depth, p.resolves_obligation_ref,
                           p.lease_epoch
                    FROM execution.semantic_parser_partition AS p
                    JOIN execution.semantic_parser_source AS s
                      ON s.source_ref = p.source_ref
                    WHERE p.run_ref = %s
                      AND (
                          p.state = 'ready'
                          OR (p.state = 'leased' AND p.lease_expires_at < CURRENT_TIMESTAMP)
                      )
                    ORDER BY p.sequence_no
                    FOR UPDATE OF p SKIP LOCKED
                    LIMIT %s
                    """,
                    (run_ref, batch_size),
                )
                rows = cursor.fetchall()
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
                for row in rows:
                    prior_epoch = int(row[17])
                    epoch = prior_epoch + 1
                    token = uuid4().hex
                    attempt_ref = f"parser-attempt:{row[0]}:{epoch}:{token}"
                    cursor.execute(
                        """
                        UPDATE execution.semantic_parser_attempt
                        SET state = 'stale', completed_at = CURRENT_TIMESTAMP,
                            error_reason = 'lease_expired'
                        WHERE partition_ref = %s AND state = 'leased'
                        """,
                        (row[0],),
                    )
                    cursor.execute(
                        """
                        UPDATE execution.semantic_parser_partition
                        SET state = 'leased', lease_owner = %s,
                            lease_token = %s, lease_epoch = %s,
                            lease_expires_at = CURRENT_TIMESTAMP
                                + (%s * INTERVAL '1 second'),
                            attempt_count = attempt_count + 1,
                            worker_pid = %s, backend_pid = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE partition_ref = %s
                        """,
                        (
                            worker_ref,
                            token,
                            epoch,
                            lease_seconds,
                            os.getpid(),
                            backend_pid,
                            row[0],
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_attempt
                            (attempt_ref, partition_ref, worker_ref, worker_pid,
                             backend_pid, lease_token, lease_epoch, state)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'leased')
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            attempt_ref,
                            row[0],
                            worker_ref,
                            os.getpid(),
                            backend_pid,
                            token,
                            epoch,
                        ),
                    )
                    leased.append(
                        ParserPartition(
                            partition_ref=str(row[0]),
                            run_ref=run_ref,
                            document_ref=str(row[1]),
                            source_ref=str(row[2]),
                            source_locator=str(row[3]),
                            parser_contract_ref=str(row[4]),
                            partition_kind=str(row[5]),
                            sequence_no=int(row[6]),
                            owner_start_char=int(row[7]),
                            owner_end_char=int(row[8]),
                            context_start_char=int(row[9]),
                            context_end_char=int(row[10]),
                            owner_start_byte=int(row[11]),
                            owner_end_byte=int(row[12]),
                            context_start_byte=int(row[13]),
                            context_end_byte=int(row[14]),
                            repair_depth=int(row[15]),
                            resolves_obligation_ref=(str(row[16]) if row[16] else None),
                            lease_token=token,
                            lease_epoch=epoch,
                            attempt_ref=attempt_ref,
                        )
                    )
    finally:
        connection.close()
    return tuple(leased)


def _symbol(kind: str, text: str) -> tuple[str, str, str]:
    value = str(text or "")
    return (typed_ref("parser-symbol:", kind, value), kind, value)


def _sentence_ref(partition: ParserPartition, start: int, end: int) -> str:
    return typed_ref(
        "parser-sentence:",
        partition.run_ref,
        partition.document_ref,
        SEGMENTATION_CONTRACT,
        start,
        end,
    )


def _token_ref(sentence_ref: str, start: int, end: int) -> str:
    return typed_ref("parser-token:", TOKEN_IDENTITY_CONTRACT, sentence_ref, start, end)


def _copy_rows(
    cursor: Any,
    *,
    table: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> None:
    if not rows:
        return
    temporary = "tmp_" + table.removeprefix("semantic_")
    column_sql = ", ".join(columns)
    cursor.execute(
        f"CREATE TEMP TABLE {temporary} "
        f"(LIKE execution.{table} INCLUDING DEFAULTS) ON COMMIT DROP"
    )
    cursor.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'execution' AND table_name = %s "
        "  AND is_nullable = 'NO'",
        (table,),
    )
    for (column,) in cursor.fetchall():
        if column not in columns:
            cursor.execute(
                f"ALTER TABLE {temporary} ALTER COLUMN {column} DROP NOT NULL"
            )
    with cursor.copy(f"COPY {temporary} ({column_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    cursor.execute(
        f"INSERT INTO execution.{table} ({column_sql}) "
        f"SELECT {column_sql} FROM {temporary} ON CONFLICT DO NOTHING"
    )


def seal_docbin(
    doc: Any,
    *,
    partition: ParserPartition,
    artifact_root: Path,
) -> tuple[str, Path, bytes, int]:
    from spacy.tokens import DocBin

    docbin = DocBin(store_user_data=False)
    docbin.add(doc)
    payload = docbin.to_bytes()
    digest = sha256(payload).digest()
    artifact_ref = typed_ref("parser-artifact:", partition.partition_ref, digest)
    path = artifact_root / "docbin" / digest.hex()[:2] / f"{digest.hex()}.spacy"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(f".tmp.{os.getpid()}")
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    if path.stat().st_size != len(payload):
        raise RuntimeError("spaCy cache artifact size changed")
    return artifact_ref, path, digest, len(payload)


def _create_boundary_repair(
    cursor: Any,
    *,
    partition: ParserPartition,
    start_char: int,
    end_char: int,
    start_byte: int,
    end_byte: int,
    policy: ParserStreamingPolicy,
) -> tuple[str, str | None]:
    obligation_ref = typed_ref(
        "parser-boundary-obligation:",
        partition.run_ref,
        partition.document_ref,
        "sentence_crosses_owner",
        start_char,
        end_char,
    )
    if partition.repair_depth >= policy.max_repair_depth:
        cursor.execute(
            """
            INSERT INTO execution.semantic_parser_boundary_obligation
                (obligation_ref, run_ref, document_ref, source_partition_ref,
                 obligation_kind, suspected_start_char, suspected_end_char, state)
            VALUES (%s, %s, %s, %s,
                    'sentence_crosses_owner', %s, %s, 'failed')
            ON CONFLICT (obligation_ref) DO UPDATE SET state = 'failed'
            """,
            (
                obligation_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                start_char,
                end_char,
            ),
        )
        return obligation_ref, None
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (partition.run_ref,),
    )
    cursor.execute(
        """
        SELECT coalesce(max(sequence_no), -1) + 1
        FROM execution.semantic_parser_partition
        WHERE run_ref = %s
        """,
        (partition.run_ref,),
    )
    sequence_no = int(cursor.fetchone()[0])
    repair_ref = typed_ref(
        "parser-partition:",
        STREAMING_SPACY_CONTRACT,
        partition.run_ref,
        partition.document_ref,
        partition.source_ref,
        partition.parser_contract_ref,
        "boundary_repair",
        obligation_ref,
        start_char,
        end_char,
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_partition
            (partition_ref, run_ref, document_ref, source_ref,
             parser_contract_ref, partition_kind, sequence_no,
             owner_start_char, owner_end_char,
             context_start_char, context_end_char,
             owner_start_byte, owner_end_byte,
             context_start_byte, context_end_byte,
             repair_depth, resolves_obligation_ref)
        VALUES (%s, %s, %s, %s, %s, 'boundary_repair', %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (partition_ref) DO NOTHING
        """,
        (
            repair_ref,
            partition.run_ref,
            partition.document_ref,
            partition.source_ref,
            partition.parser_contract_ref,
            sequence_no,
            start_char,
            end_char,
            partition.context_start_char,
            partition.context_end_char,
            start_byte,
            end_byte,
            partition.context_start_byte,
            partition.context_end_byte,
            partition.repair_depth + 1,
            obligation_ref,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_boundary_obligation
            (obligation_ref, run_ref, document_ref, source_partition_ref,
             repair_partition_ref, obligation_kind,
             suspected_start_char, suspected_end_char, state)
        VALUES (%s, %s, %s, %s, %s,
                'sentence_crosses_owner', %s, %s, 'open')
        ON CONFLICT (obligation_ref) DO NOTHING
        """,
        (
            obligation_ref,
            partition.run_ref,
            partition.document_ref,
            partition.partition_ref,
            repair_ref,
            start_char,
            end_char,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_outbox
            (event_ref, event_type_ref, run_ref, document_ref,
             partition_ref, obligation_ref)
        VALUES (%s, 'parser.boundary-obligation.opened.v1',
                %s, %s, %s, %s)
        ON CONFLICT (event_ref) DO NOTHING
        """,
        (
            typed_ref("parser-event:", obligation_ref, "opened"),
            partition.run_ref,
            partition.document_ref,
            partition.partition_ref,
            obligation_ref,
        ),
    )
    return obligation_ref, repair_ref


def refresh_coverage(cursor: Any, *, run_ref: str, document_ref: str) -> str:
    cursor.execute(
        """
        SELECT count(*),
               count(*) FILTER (WHERE state = 'completed'),
               count(*) FILTER (WHERE state = 'failed')
        FROM execution.semantic_parser_partition
        WHERE run_ref = %s AND document_ref = %s
        """,
        (run_ref, document_ref),
    )
    total, completed, failed_partitions = (int(value) for value in cursor.fetchone())
    cursor.execute(
        """
        SELECT count(*) FILTER (WHERE state = 'open'),
               count(*) FILTER (WHERE state = 'failed')
        FROM execution.semantic_parser_boundary_obligation
        WHERE run_ref = %s AND document_ref = %s
        """,
        (run_ref, document_ref),
    )
    open_obligations, failed_obligations = (int(value) for value in cursor.fetchone())
    failed = failed_partitions > 0 or failed_obligations > 0
    state = (
        "failed"
        if failed
        else ("complete" if completed == total and open_obligations == 0 else "open")
    )
    cursor.execute(
        """
        UPDATE execution.semantic_parser_document_coverage AS coverage
        SET total_partitions = %s,
            completed_partitions = %s,
            open_boundary_obligations = %s,
            tokenization = coalesce(cap.tokenization, FALSE),
            sentence_segmentation = coalesce(cap.sentence_segmentation, FALSE),
            part_of_speech = coalesce(cap.part_of_speech, FALSE),
            morphology = coalesce(cap.morphology, FALSE),
            dependencies = coalesce(cap.dependencies, FALSE),
            named_entities = coalesce(cap.named_entities, FALSE),
            state = %s,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT bool_and(tokenization) AS tokenization,
                   bool_and(sentence_segmentation) AS sentence_segmentation,
                   bool_and(part_of_speech) AS part_of_speech,
                   bool_and(morphology) AS morphology,
                   bool_and(dependencies) AS dependencies,
                   bool_and(named_entities) AS named_entities
            FROM execution.semantic_parser_partition_receipt
            WHERE run_ref = %s AND document_ref = %s
        ) AS cap
        WHERE coverage.run_ref = %s AND coverage.document_ref = %s
        """,
        (
            total,
            completed,
            open_obligations,
            state,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
        ),
    )
    if state == "complete":
        cursor.execute(
            """
            INSERT INTO execution.semantic_parser_outbox
                (event_ref, event_type_ref, run_ref, document_ref)
            VALUES (%s, 'parser.document-coverage.closed.v1', %s, %s)
            ON CONFLICT (event_ref) DO NOTHING
            """,
            (
                typed_ref("parser-event:", run_ref, document_ref, "coverage-closed"),
                run_ref,
                document_ref,
            ),
        )
    return state


def commit_doc(
    database_url: str,
    *,
    partition: ParserPartition,
    doc: Any,
    policy: ParserStreamingPolicy,
    artifact_root: Path,
    pipeline: Any,
    elapsed_ns: int,
) -> None:
    pipe_names = tuple(pipeline.pipe_names)
    capabilities = {
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
    artifact = (
        seal_docbin(doc, partition=partition, artifact_root=artifact_root)
        if policy.cache_docbin
        else None
    )
    sentence_rows: list[tuple[Any, ...]] = []
    token_rows: list[tuple[Any, ...]] = []
    morph_rows: list[tuple[Any, ...]] = []
    entity_rows: list[tuple[Any, ...]] = []
    symbols: dict[str, tuple[str, str, str]] = {}
    crossing_sentences: list[tuple[int, int, int, int]] = []
    sentence_for_span: list[tuple[int, int, str]] = []
    sentence_spans = tuple(doc.sents) if doc.has_annotation("SENT_START") else (doc[:],)
    owned_sentence_ordinal = 0
    for span in sentence_spans:
        local_start = int(span.start_char)
        local_end = int(span.end_char)
        start_char = partition.context_start_char + local_start
        end_char = partition.context_start_char + local_end
        start_byte = partition.context_start_byte + len(
            doc.text[:local_start].encode("utf-8")
        )
        end_byte = partition.context_start_byte + len(
            doc.text[:local_end].encode("utf-8")
        )
        overlaps_owner = (
            start_char < partition.owner_end_char
            and end_char > partition.owner_start_char
        )
        if not overlaps_owner:
            continue
        if not (
            start_char >= partition.owner_start_char
            and end_char <= partition.owner_end_char
        ):
            crossing_sentences.append((start_char, end_char, start_byte, end_byte))
            continue
        sentence_ref = _sentence_ref(partition, start_char, end_char)
        sentence_rows.append(
            (
                sentence_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                owned_sentence_ordinal,
                start_char,
                end_char,
                SEGMENTATION_CONTRACT,
                "owned",
            )
        )
        sentence_for_span.append((start_char, end_char, sentence_ref))
        local_tokens = tuple(span)
        token_refs = {
            token.i: _token_ref(
                sentence_ref,
                partition.context_start_char + int(token.idx),
                partition.context_start_char + int(token.idx + len(token.text)),
            )
            for token in local_tokens
        }
        for local_ordinal, token in enumerate(local_tokens):
            token_start = partition.context_start_char + int(token.idx)
            token_end = partition.context_start_char + int(token.idx + len(token.text))
            head_start = partition.context_start_char + int(token.head.idx)
            head_end = partition.context_start_char + int(
                token.head.idx + len(token.head.text)
            )
            token_symbols = (
                _symbol("orth", token.text),
                _symbol("lemma", token.lemma_ or token.text),
                _symbol("pos", token.pos_),
                _symbol("tag", token.tag_),
                _symbol("dependency", token.dep_),
            )
            for symbol in token_symbols:
                symbols[symbol[0]] = symbol
            orth, lemma, pos, tag, dependency = token_symbols
            token_ref = token_refs[token.i]
            token_rows.append(
                (
                    token_ref,
                    partition.run_ref,
                    partition.document_ref,
                    partition.partition_ref,
                    sentence_ref,
                    local_ordinal,
                    token_start,
                    token_end,
                    orth[0],
                    lemma[0],
                    pos[0],
                    tag[0],
                    dependency[0],
                    token_refs.get(token.head.i),
                    head_start,
                    head_end,
                )
            )
            morph_ordinal = 0
            for feature, raw_values in sorted(token.morph.to_dict().items()):
                feature_symbol = _symbol("morph_feature", feature)
                symbols[feature_symbol[0]] = feature_symbol
                values = (
                    raw_values
                    if isinstance(raw_values, (list, tuple))
                    else (raw_values,)
                )
                for value in values:
                    value_symbol = _symbol("morph_value", str(value))
                    symbols[value_symbol[0]] = value_symbol
                    morph_rows.append(
                        (
                            token_ref,
                            feature_symbol[0],
                            value_symbol[0],
                            morph_ordinal,
                        )
                    )
                    morph_ordinal += 1
        owned_sentence_ordinal += 1
    for entity in getattr(doc, "ents", ()):
        start_char = partition.context_start_char + int(entity.start_char)
        end_char = partition.context_start_char + int(entity.end_char)
        if not (
            start_char >= partition.owner_start_char
            and end_char <= partition.owner_end_char
        ):
            continue
        entity_type = _symbol("entity_type", entity.label_)
        symbols[entity_type[0]] = entity_type
        sentence_ref = next(
            (
                ref
                for sentence_start, sentence_end, ref in sentence_for_span
                if start_char >= sentence_start and end_char <= sentence_end
            ),
            None,
        )
        entity_ref = typed_ref(
            "parser-entity:",
            partition.run_ref,
            partition.document_ref,
            start_char,
            end_char,
            entity_type[0],
        )
        entity_rows.append(
            (
                entity_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                sentence_ref,
                start_char,
                end_char,
                entity_type[0],
            )
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
                    return
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
                    return
                _copy_rows(
                    cursor,
                    table="semantic_parser_symbol",
                    columns=("symbol_ref", "symbol_kind", "symbol_text"),
                    rows=tuple(symbols.values()),
                )
                _copy_rows(
                    cursor,
                    table="semantic_parser_sentence",
                    columns=(
                        "sentence_ref",
                        "run_ref",
                        "document_ref",
                        "partition_ref",
                        "local_sentence_ordinal",
                        "start_char",
                        "end_char",
                        "segmentation_contract_ref",
                        "ownership_state",
                    ),
                    rows=sentence_rows,
                )
                _copy_rows(
                    cursor,
                    table="semantic_parser_token",
                    columns=(
                        "token_ref",
                        "run_ref",
                        "document_ref",
                        "partition_ref",
                        "sentence_ref",
                        "local_token_ordinal",
                        "start_char",
                        "end_char",
                        "orth_ref",
                        "lemma_ref",
                        "pos_ref",
                        "tag_ref",
                        "dependency_ref",
                        "head_token_ref",
                        "head_start_char",
                        "head_end_char",
                    ),
                    rows=token_rows,
                )
                _copy_rows(
                    cursor,
                    table="semantic_parser_token_morphology",
                    columns=("token_ref", "feature_ref", "value_ref", "ordinal"),
                    rows=morph_rows,
                )
                _copy_rows(
                    cursor,
                    table="semantic_parser_entity_span",
                    columns=(
                        "entity_ref",
                        "run_ref",
                        "document_ref",
                        "partition_ref",
                        "sentence_ref",
                        "start_char",
                        "end_char",
                        "entity_type_ref",
                    ),
                    rows=entity_rows,
                )
                for start_char, end_char, start_byte, end_byte in crossing_sentences:
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
                        UPDATE execution.semantic_parser_boundary_obligation
                        SET state = 'resolved', resolved_at = CURRENT_TIMESTAMP
                        WHERE obligation_ref = %s
                          AND EXISTS (
                              SELECT 1
                              FROM execution.semantic_parser_sentence
                              WHERE partition_ref = %s
                          )
                        """,
                        (
                            partition.resolves_obligation_ref,
                            partition.partition_ref,
                        ),
                    )
                artifact_ref: str | None = None
                if artifact is not None:
                    artifact_ref, artifact_path, artifact_digest, artifact_bytes = (
                        artifact
                    )
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
                receipt_digest = bytes.fromhex(
                    canonical_fields_sha256(
                        STREAMING_SPACY_CONTRACT,
                        partition.partition_ref,
                        partition.lease_epoch,
                        len(sentence_rows),
                        len(token_rows),
                        len(entity_rows),
                        len(crossing_sentences),
                        elapsed_ns,
                        artifact_ref,
                    )
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
                        len(sentence_rows),
                        len(token_rows),
                        len(entity_rows),
                        len(crossing_sentences),
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
                    SET state = 'completed', lease_owner = NULL,
                        lease_token = NULL, lease_expires_at = NULL,
                        sentence_count = %s, token_count = %s,
                        entity_count = %s, boundary_obligation_count = %s,
                        elapsed_ns = %s, completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE partition_ref = %s AND state = 'leased'
                      AND lease_token = %s AND lease_epoch = %s
                    """,
                    (
                        len(sentence_rows),
                        len(token_rows),
                        len(entity_rows),
                        len(crossing_sentences),
                        elapsed_ns,
                        partition.partition_ref,
                        partition.lease_token,
                        partition.lease_epoch,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "parser partition fence changed during completion"
                    )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_attempt
                    SET state = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE attempt_ref = %s
                    """,
                    (partition.attempt_ref,),
                )
                for sentence_row in sentence_rows:
                    sentence_ref = str(sentence_row[0])
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_outbox
                            (event_ref, event_type_ref, run_ref, document_ref,
                             partition_ref, sentence_ref)
                        VALUES (%s, 'parser.sentence.committed.v1',
                                %s, %s, %s, %s)
                        ON CONFLICT (event_ref) DO NOTHING
                        """,
                        (
                            typed_ref("parser-event:", sentence_ref, "committed"),
                            partition.run_ref,
                            partition.document_ref,
                            partition.partition_ref,
                            sentence_ref,
                        ),
                    )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_outbox
                        (event_ref, event_type_ref, run_ref, document_ref,
                         partition_ref)
                    VALUES (%s, 'parser.partition.completed.v1', %s, %s, %s)
                    ON CONFLICT (event_ref) DO NOTHING
                    """,
                    (
                        typed_ref(
                            "parser-event:",
                            partition.partition_ref,
                            "completed",
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
    finally:
        connection.close()


def fail_partition(
    database_url: str,
    *,
    partition: ParserPartition,
    error: BaseException,
) -> None:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_partition
                    SET state = 'failed', last_error_reason = %s,
                        lease_owner = NULL, lease_token = NULL,
                        lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE partition_ref = %s AND state = 'leased'
                      AND lease_token = %s AND lease_epoch = %s
                    """,
                    (
                        type(error).__name__,
                        partition.partition_ref,
                        partition.lease_token,
                        partition.lease_epoch,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_attempt
                    SET state = 'failed', error_reason = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE attempt_ref = %s
                    """,
                    (type(error).__name__, partition.attempt_ref),
                )
                refresh_coverage(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                )
    finally:
        connection.close()


def recover_expired(database_url: str, *, run_ref: str) -> int:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_attempt AS attempt
                    SET state = 'stale', completed_at = CURRENT_TIMESTAMP,
                        error_reason = 'lease_expired'
                    FROM execution.semantic_parser_partition AS partition
                    WHERE partition.run_ref = %s
                      AND partition.state = 'leased'
                      AND partition.lease_expires_at < CURRENT_TIMESTAMP
                      AND attempt.partition_ref = partition.partition_ref
                      AND attempt.lease_epoch = partition.lease_epoch
                      AND attempt.state = 'leased'
                    """,
                    (run_ref,),
                )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_partition
                    SET state = 'ready', lease_owner = NULL, lease_token = NULL,
                        lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE run_ref = %s AND state = 'leased'
                      AND lease_expires_at < CURRENT_TIMESTAMP
                    """,
                    (run_ref,),
                )
                return cursor.rowcount
    finally:
        connection.close()


def execution_state(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[str, int, int, int]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       count(partition.partition_ref)
                           FILTER (WHERE partition.state = 'ready'),
                       count(partition.partition_ref)
                           FILTER (WHERE partition.state = 'leased'),
                       count(partition.partition_ref)
                           FILTER (WHERE partition.state = 'failed')
                FROM execution.semantic_parser_document_coverage AS coverage
                LEFT JOIN execution.semantic_parser_partition AS partition
                  ON partition.run_ref = coverage.run_ref
                 AND partition.document_ref = coverage.document_ref
                WHERE coverage.run_ref = %s AND coverage.document_ref = %s
                GROUP BY coverage.state
                """,
                (run_ref, document_ref),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("parser coverage row is missing")
            return str(row[0]), int(row[1]), int(row[2]), int(row[3])
    finally:
        connection.close()


def execution_summary(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    parser_contract_ref: str,
) -> ParserExecutionSummary:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       (SELECT count(*)
                        FROM execution.semantic_parser_sentence
                        WHERE run_ref = %s AND document_ref = %s),
                       (SELECT count(*)
                        FROM execution.semantic_parser_token
                        WHERE run_ref = %s AND document_ref = %s),
                       (SELECT count(*)
                        FROM execution.semantic_parser_partition
                        WHERE run_ref = %s AND document_ref = %s),
                       (SELECT count(*)
                        FROM execution.semantic_parser_entity_span
                        WHERE run_ref = %s AND document_ref = %s),
                       (SELECT count(*)
                        FROM execution.semantic_parser_boundary_obligation
                        WHERE run_ref = %s AND document_ref = %s)
                FROM execution.semantic_parser_document_coverage AS coverage
                WHERE coverage.run_ref = %s AND coverage.document_ref = %s
                """,
                (
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                ),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("parser execution summary is missing")
    return ParserExecutionSummary(
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        parser_contract_ref=parser_contract_ref,
        coverage_state=str(row[0]),
        sentence_count=int(row[1]),
        token_count=int(row[2]),
        partition_count=int(row[3]),
        entity_count=int(row[4]),
        boundary_obligation_count=int(row[5]),
    )


__all__ = [
    "commit_doc",
    "execution_state",
    "execution_summary",
    "fail_partition",
    "lease_partitions",
    "recover_expired",
    "refresh_coverage",
    "register_execution",
    "seal_docbin",
]
