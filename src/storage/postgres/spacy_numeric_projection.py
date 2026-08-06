"""Numeric projection of one completed spaCy ``Doc``.

The mutable ``Doc`` is consumed once. Lexical strings are interned in one
transaction, parser observations are stored with BIGINT ids, dependency heads
are numeric foreign keys, and morphology is deduplicated into numeric sets.
Legacy textual refs are emitted only as compatibility labels and are never
used by strict execution joins.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

from src.pnf.numeric_hyperfabric import SymbolKind, numeric_digest
from src.storage.postgres.numeric_symbol_store import (
    SymbolValue,
    intern_morph_sets,
    intern_symbols,
    symbol_id,
)
from src.storage.postgres.spacy_parser_model import (
    DOCBIN_ENCODING,
    SEGMENTATION_CONTRACT,
    ParserPartition,
    ParserStreamingPolicy,
    byte_offsets,
    connect,
)
from src.storage.postgres.spacy_parser_store import (
    _copy_rows,
    _create_boundary_repair,
    refresh_coverage,
    seal_docbin,
)


class NumericHeadProjectionError(RuntimeError):
    """A declared non-root dependency head was not committed."""


@dataclass(frozen=True, slots=True)
class _RawSentence:
    sentence_ref: str
    sentence_digest: bytes
    ordinal: int
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class _RawToken:
    token_ref: str
    token_digest: bytes
    sentence_ref: str
    ordinal: int
    start_char: int
    end_char: int
    orth: str
    lemma: str
    pos: str
    tag: str
    dependency: str
    head_is_self: bool
    head_start_char: int
    head_end_char: int
    morphology: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _RawEntity:
    entity_ref: str
    entity_digest: bytes
    sentence_ref: str | None
    start_char: int
    end_char: int
    entity_type: str


def _compat_ref(prefix: str, digest: bytes) -> str:
    return prefix + digest.hex()


def _pipeline_capabilities(pipeline: Any) -> dict[str, bool]:
    pipe_names = tuple(pipeline.pipe_names)
    return {
        "tokenization": True,
        "sentence_segmentation": any(
            name in pipe_names for name in ("parser", "senter", "sentencizer")
        ),
        "part_of_speech": any(
            name in pipe_names for name in ("tagger", "morphologizer")
        ),
        "morphology": any(
            name in pipe_names for name in ("tagger", "morphologizer")
        ),
        "dependencies": "parser" in pipe_names,
        "named_entities": "ner" in pipe_names,
    }


def _require_numeric_pnf_capabilities(capabilities: Mapping[str, bool]) -> None:
    missing = tuple(
        name
        for name in ("sentence_segmentation", "part_of_speech", "dependencies")
        if not bool(capabilities.get(name, False))
    )
    if missing:
        raise RuntimeError(
            "strict numeric PNF requires parser capabilities: "
            + ", ".join(missing)
        )


def _project_numeric_heads(
    raw_tokens: tuple[_RawToken, ...],
    token_rows_by_ref: Mapping[str, tuple[int, int, int]],
) -> tuple[tuple[int, int], ...]:
    """Resolve dependency heads without inventing root self-loops."""

    token_id_by_span: dict[tuple[int, int], int] = {}
    for token_id, start_char, end_char in token_rows_by_ref.values():
        span = (start_char, end_char)
        previous = token_id_by_span.setdefault(span, token_id)
        if previous != token_id:
            raise NumericHeadProjectionError(
                f"duplicate committed token span {span!r}"
            )

    updates: list[tuple[int, int]] = []
    for raw in raw_tokens:
        committed = token_rows_by_ref.get(raw.token_ref)
        if committed is None:
            raise NumericHeadProjectionError(
                f"numeric token row missing for {raw.token_ref}"
            )
        token_id, start_char, end_char = committed
        token_span = (start_char, end_char)
        declared_head_span = (raw.head_start_char, raw.head_end_char)
        if raw.head_is_self:
            if declared_head_span != token_span:
                raise NumericHeadProjectionError(
                    "explicit parser root has a non-self head span: "
                    f"token={token_span!r} head={declared_head_span!r}"
                )
            head_token_id = token_id
        else:
            head_token_id = token_id_by_span.get(declared_head_span)
            if head_token_id is None:
                raise NumericHeadProjectionError(
                    "declared non-root dependency head is absent: "
                    f"token={token_span!r} head={declared_head_span!r}"
                )
            if head_token_id == token_id:
                raise NumericHeadProjectionError(
                    "non-root dependency resolved to its own token id"
                )
        updates.append((head_token_id, token_id))
    return tuple(updates)


def _collect_doc(
    partition: ParserPartition,
    doc: Any,
) -> tuple[
    tuple[_RawSentence, ...],
    tuple[_RawToken, ...],
    tuple[_RawEntity, ...],
    tuple[tuple[int, int, int, int], ...],
    tuple[SymbolValue, ...],
]:
    sentence_spans = (
        tuple(doc.sents) if doc.has_annotation("SENT_START") else (doc[:],)
    )
    requested_byte_offsets: set[int] = {0, len(doc.text)}
    for span in sentence_spans:
        requested_byte_offsets.update((int(span.start_char), int(span.end_char)))
        for token in span:
            requested_byte_offsets.update(
                (
                    int(token.idx),
                    int(token.idx + len(token.text)),
                    int(token.head.idx),
                    int(token.head.idx + len(token.head.text)),
                )
            )
    local_bytes = byte_offsets(doc.text, tuple(requested_byte_offsets))

    sentences: list[_RawSentence] = []
    tokens: list[_RawToken] = []
    crossings: list[tuple[int, int, int, int]] = []
    symbols: set[SymbolValue] = set()
    owned_ordinal = 0
    sentence_bounds: list[tuple[int, int, str]] = []

    for span in sentence_spans:
        local_start = int(span.start_char)
        local_end = int(span.end_char)
        start_char = partition.context_start_char + local_start
        end_char = partition.context_start_char + local_end
        start_byte = partition.context_start_byte + local_bytes[local_start]
        end_byte = partition.context_start_byte + local_bytes[local_end]
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
            crossings.append((start_char, end_char, start_byte, end_byte))
            continue

        sentence_digest = numeric_digest(
            partition.run_ref.encode("utf-8"),
            partition.document_ref.encode("utf-8"),
            start_char,
            end_char,
            2,
        )
        sentence_ref = _compat_ref("parser-sentence:", sentence_digest)
        sentences.append(
            _RawSentence(
                sentence_ref=sentence_ref,
                sentence_digest=sentence_digest,
                ordinal=owned_ordinal,
                start_char=start_char,
                end_char=end_char,
            )
        )
        sentence_bounds.append((start_char, end_char, sentence_ref))

        for ordinal, token in enumerate(span):
            token_start = partition.context_start_char + int(token.idx)
            token_end = partition.context_start_char + int(
                token.idx + len(token.text)
            )
            head_start = partition.context_start_char + int(token.head.idx)
            head_end = partition.context_start_char + int(
                token.head.idx + len(token.head.text)
            )
            morphology: list[tuple[str, str]] = []
            for feature, raw_values in sorted(token.morph.to_dict().items()):
                values = (
                    raw_values
                    if isinstance(raw_values, (list, tuple))
                    else (raw_values,)
                )
                for value in values:
                    morphology.append((str(feature), str(value)))
                    symbols.add(
                        SymbolValue(SymbolKind.MORPH_FEATURE, str(feature))
                    )
                    symbols.add(SymbolValue(SymbolKind.MORPH_VALUE, str(value)))
            for kind, text in (
                (SymbolKind.ORTH, token.text),
                (SymbolKind.LEMMA, token.lemma_ or token.text),
                (SymbolKind.POS, token.pos_),
                (SymbolKind.TAG, token.tag_ or token.pos_),
                (SymbolKind.DEPENDENCY, token.dep_),
            ):
                symbols.add(SymbolValue(kind, str(text)))
            token_digest = numeric_digest(
                sentence_digest,
                token_start,
                token_end,
                ordinal,
            )
            tokens.append(
                _RawToken(
                    token_ref=_compat_ref("parser-token:", token_digest),
                    token_digest=token_digest,
                    sentence_ref=sentence_ref,
                    ordinal=ordinal,
                    start_char=token_start,
                    end_char=token_end,
                    orth=str(token.text),
                    lemma=str(token.lemma_ or token.text),
                    pos=str(token.pos_),
                    tag=str(token.tag_ or token.pos_),
                    dependency=str(token.dep_),
                    head_is_self=bool(token.head == token),
                    head_start_char=head_start,
                    head_end_char=head_end,
                    morphology=tuple(sorted(set(morphology))),
                )
            )
        owned_ordinal += 1

    entities: list[_RawEntity] = []
    for entity in getattr(doc, "ents", ()):
        start_char = partition.context_start_char + int(entity.start_char)
        end_char = partition.context_start_char + int(entity.end_char)
        if not (
            start_char >= partition.owner_start_char
            and end_char <= partition.owner_end_char
        ):
            continue
        sentence_ref = next(
            (
                ref
                for sentence_start, sentence_end, ref in sentence_bounds
                if start_char >= sentence_start and end_char <= sentence_end
            ),
            None,
        )
        symbols.add(SymbolValue(SymbolKind.ENTITY_TYPE, str(entity.label_)))
        entity_digest = numeric_digest(
            partition.run_ref.encode("utf-8"),
            partition.document_ref.encode("utf-8"),
            start_char,
            end_char,
            8,
        )
        entities.append(
            _RawEntity(
                entity_ref=_compat_ref("parser-entity:", entity_digest),
                entity_digest=entity_digest,
                sentence_ref=sentence_ref,
                start_char=start_char,
                end_char=end_char,
                entity_type=str(entity.label_),
            )
        )

    return (
        tuple(sentences),
        tuple(tokens),
        tuple(entities),
        tuple(crossings),
        tuple(symbols),
    )


def commit_numeric_doc(
    database_url: str,
    *,
    partition: ParserPartition,
    doc: Any,
    policy: ParserStreamingPolicy,
    artifact_root: Path,
    pipeline: Any,
    elapsed_ns: int,
) -> None:
    """Commit one bounded ``Doc`` through the numeric parser authority."""

    capabilities = _pipeline_capabilities(pipeline)
    _require_numeric_pnf_capabilities(capabilities)
    (
        sentences,
        raw_tokens,
        raw_entities,
        crossings,
        symbol_values,
    ) = _collect_doc(partition, doc)
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
                    return
                if (
                    str(state) != "leased"
                    or token != partition.lease_token
                    or int(epoch) != partition.lease_epoch
                ):
                    cursor.execute(
                        """
                        UPDATE execution.semantic_parser_attempt
                           SET state = 'stale',
                               completed_at = CURRENT_TIMESTAMP
                         WHERE attempt_ref = %s
                        """,
                        (partition.attempt_ref,),
                    )
                    return

                symbol_map = intern_symbols(cursor, symbol_values)
                sentence_rows = [
                    (
                        sentence.sentence_ref,
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                        sentence.ordinal,
                        sentence.start_char,
                        sentence.end_char,
                        SEGMENTATION_CONTRACT,
                        "owned",
                        sentence.sentence_digest,
                        2,
                    )
                    for sentence in sentences
                ]
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
                        "sentence_digest",
                        "representation_version",
                    ),
                    rows=sentence_rows,
                )

                morph_members_by_token: dict[
                    str, tuple[tuple[int, int], ...]
                ] = {}
                for raw in raw_tokens:
                    members = tuple(
                        sorted(
                            {
                                (
                                    symbol_id(
                                        symbol_map,
                                        SymbolKind.MORPH_FEATURE,
                                        feature,
                                    ),
                                    symbol_id(
                                        symbol_map,
                                        SymbolKind.MORPH_VALUE,
                                        value,
                                    ),
                                )
                                for feature, value in raw.morphology
                            }
                        )
                    )
                    morph_members_by_token[raw.token_ref] = members
                morph_ids = intern_morph_sets(
                    cursor,
                    tuple(morph_members_by_token.values()),
                )

                token_rows = [
                    (
                        raw.token_ref,
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                        raw.sentence_ref,
                        raw.ordinal,
                        raw.start_char,
                        raw.end_char,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        raw.head_start_char,
                        raw.head_end_char,
                        raw.token_digest,
                        symbol_id(symbol_map, SymbolKind.ORTH, raw.orth),
                        symbol_id(symbol_map, SymbolKind.LEMMA, raw.lemma),
                        symbol_id(symbol_map, SymbolKind.POS, raw.pos),
                        symbol_id(symbol_map, SymbolKind.TAG, raw.tag),
                        symbol_id(
                            symbol_map,
                            SymbolKind.DEPENDENCY,
                            raw.dependency,
                        ),
                        morph_ids.get(morph_members_by_token[raw.token_ref]),
                        2,
                    )
                    for raw in raw_tokens
                ]
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
                        "token_digest",
                        "orth_symbol_id",
                        "lemma_symbol_id",
                        "pos_symbol_id",
                        "tag_symbol_id",
                        "dependency_symbol_id",
                        "morph_set_id",
                        "representation_version",
                    ),
                    rows=token_rows,
                )

                cursor.execute(
                    """
                    SELECT token_ref, token_id, start_char, end_char
                      FROM execution.semantic_parser_token
                     WHERE run_ref = %s
                       AND document_ref = %s
                       AND partition_ref = %s
                       AND representation_version = 2
                    """,
                    (
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                    ),
                )
                token_rows_by_ref = {
                    str(token_ref): (
                        int(token_id),
                        int(start_char),
                        int(end_char),
                    )
                    for token_ref, token_id, start_char, end_char in cursor.fetchall()
                }
                cursor.executemany(
                    """
                    UPDATE execution.semantic_parser_token
                       SET head_token_id = %s
                     WHERE token_id = %s
                    """,
                    _project_numeric_heads(raw_tokens, token_rows_by_ref),
                )

                entity_rows = [
                    (
                        entity.entity_ref,
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                        entity.sentence_ref,
                        entity.start_char,
                        entity.end_char,
                        None,
                        entity.entity_digest,
                        symbol_id(
                            symbol_map,
                            SymbolKind.ENTITY_TYPE,
                            entity.entity_type,
                        ),
                        2,
                    )
                    for entity in raw_entities
                ]
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
                        "entity_digest",
                        "entity_type_symbol_id",
                        "representation_version",
                    ),
                    rows=entity_rows,
                )

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
                        UPDATE execution.semantic_parser_boundary_obligation
                           SET state = 'resolved',
                               resolved_at = CURRENT_TIMESTAMP
                         WHERE obligation_ref = %s
                           AND EXISTS (
                               SELECT 1
                                 FROM execution.semantic_parser_sentence
                                WHERE partition_ref = %s
                                  AND start_char <= (
                                      SELECT suspected_start_char
                                        FROM execution.semantic_parser_boundary_obligation
                                       WHERE obligation_ref = %s
                                  )
                                  AND end_char >= (
                                      SELECT suspected_end_char
                                        FROM execution.semantic_parser_boundary_obligation
                                       WHERE obligation_ref = %s
                                  )
                           )
                        """,
                        (
                            partition.resolves_obligation_ref,
                            partition.partition_ref,
                            partition.resolves_obligation_ref,
                            partition.resolves_obligation_ref,
                        ),
                    )

                artifact_ref: str | None = None
                if artifact is not None:
                    (
                        artifact_ref,
                        artifact_path,
                        artifact_digest,
                        artifact_bytes,
                    ) = artifact
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
                        "parser partition fence changed during numeric completion"
                    )
                cursor.execute(
                    """
                    UPDATE execution.semantic_parser_attempt
                       SET state = 'completed',
                           completed_at = CURRENT_TIMESTAMP
                     WHERE attempt_ref = %s
                    """,
                    (partition.attempt_ref,),
                )
                for sentence in sentences:
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_outbox
                            (event_ref, event_type_ref, run_ref, document_ref,
                             partition_ref, sentence_ref)
                        VALUES (
                            %s, 'parser.sentence.committed.v1',
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (event_ref) DO NOTHING
                        """,
                        (
                            _compat_ref(
                                "parser-event:",
                                numeric_digest(sentence.sentence_digest, 1),
                            ),
                            partition.run_ref,
                            partition.document_ref,
                            partition.partition_ref,
                            sentence.sentence_ref,
                        ),
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
    finally:
        connection.close()


__all__ = [
    "NumericHeadProjectionError",
    "commit_numeric_doc",
]
