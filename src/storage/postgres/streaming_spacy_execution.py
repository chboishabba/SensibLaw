"""Bounded spaCy execution projected once into typed PostgreSQL observations.

spaCy owns one mutable ``Doc`` workspace at a time.  The immutable source and
PostgreSQL rows are the durable authority.  Workers use ``Language.pipe`` with
one loaded model per process, commit each partition before leasing more work,
and never construct or serialize a document-sized parser mapping.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
import mmap
import os
from pathlib import Path
import re
import time
from time import monotonic_ns
from typing import Any
from uuid import uuid4

from src.policy.carriers.canonical import canonical_fields_sha256
from src.runtime.durable_work_items import linux_parent_death_initializer


STREAMING_SPACY_CONTRACT = "postgres-streaming-spacy:v1"
SEGMENTATION_CONTRACT = "spacy-sentence-boundaries:v1"
TOKEN_IDENTITY_CONTRACT = "source-coordinate-parser-token:v1"
DOCBIN_ENCODING = "spacy-docbin:v1"
SOURCE_ENCODING = "utf8-canonical-source:v1"


def _connect(database_url: str) -> Any:
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise RuntimeError("psycopg is required for typed parser execution") from error
    return psycopg.connect(database_url, autocommit=False)


def _ref(prefix: str, *fields: object) -> str:
    return prefix + canonical_fields_sha256(*fields)


@dataclass(frozen=True)
class ParserStreamingPolicy:
    """Physical parser scheduling policy with no semantic identity effect."""

    target_chars: int = 32_768
    context_chars: int = 2_048
    batch_size: int = 4
    lease_seconds: int = 180
    max_repair_depth: int = 2
    cache_docbin: bool = True

    def __post_init__(self) -> None:
        if self.target_chars < 1_024:
            raise ValueError("parser target_chars must be at least 1024")
        if self.context_chars < 0:
            raise ValueError("parser context_chars must be non-negative")
        if not 1 <= self.batch_size <= 64:
            raise ValueError("parser batch_size must be between 1 and 64")
        if self.lease_seconds < 1:
            raise ValueError("parser lease_seconds must be positive")
        if not 0 <= self.max_repair_depth <= 8:
            raise ValueError("parser max_repair_depth must be between zero and eight")


@dataclass(frozen=True)
class ParserPartition:
    partition_ref: str
    run_ref: str
    document_ref: str
    source_ref: str
    source_locator: str
    parser_contract_ref: str
    partition_kind: str
    sequence_no: int
    owner_start_char: int
    owner_end_char: int
    context_start_char: int
    context_end_char: int
    repair_depth: int
    resolves_obligation_ref: str | None
    lease_token: str
    lease_epoch: int
    attempt_ref: str

    @property
    def owner_length(self) -> int:
        return self.owner_end_char - self.owner_start_char


@dataclass(frozen=True)
class ParserExecutionSummary:
    run_ref: str
    document_ref: str
    source_ref: str
    parser_contract_ref: str
    sentence_count: int
    token_count: int
    partition_count: int
    entity_count: int
    boundary_obligation_count: int
    coverage_state: str


class _SentenceSequence(Sequence[Mapping[str, Any]]):
    def __init__(self, carrier: "PostgresSentenceCarrier", sentence_count: int):
        self._carrier = carrier
        self._sentence_count = sentence_count

    def __len__(self) -> int:
        return self._sentence_count

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        yield from self._carrier._iter_sentences()

    def __getitem__(self, index: int | slice) -> Any:
        if isinstance(index, slice):
            return tuple(self)[index]
        if index < 0:
            index += self._sentence_count
        if not 0 <= index < self._sentence_count:
            raise IndexError(index)
        return self._carrier._sentence_at(index)


class PostgresSentenceCarrier(Mapping[str, Any]):
    """Historical parser mapping shape backed by one-sentence SQL reads.

    This is a compatibility view, not parser authority.  Token ``index`` and
    ``head_index`` are stable source-character starts, so no document-wide
    renumbering or retained token population is required.
    """

    def __init__(
        self,
        *,
        database_url: str,
        canonical_text: str,
        summary: ParserExecutionSummary,
        parser_receipt: Mapping[str, Any],
    ) -> None:
        self.database_url = database_url
        self._text = canonical_text
        self.summary = summary
        self._parser_receipt = dict(parser_receipt)
        self._sentences = _SentenceSequence(self, summary.sentence_count)

    @property
    def sentence_count(self) -> int:
        return self.summary.sentence_count

    @property
    def token_count(self) -> int:
        return self.summary.token_count

    @property
    def partition_count(self) -> int:
        return self.summary.partition_count

    def __getitem__(self, key: str) -> Any:
        if key == "text":
            return self._text
        if key == "sents":
            return self._sentences
        if key == "parser_receipt":
            return self._parser_receipt
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("text", "sents", "parser_receipt"))

    def __len__(self) -> int:
        return 3

    def _sentence_rows(self, *, offset: int | None = None) -> Iterator[tuple[Any, ...]]:
        connection = _connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                query = """
                    SELECT sentence_ref, start_char, end_char, partition_ref
                    FROM execution.semantic_parser_sentence
                    WHERE run_ref = %s AND document_ref = %s
                    ORDER BY start_char, end_char, sentence_ref
                """
                parameters: list[Any] = [self.summary.run_ref, self.summary.document_ref]
                if offset is not None:
                    query += " LIMIT 1 OFFSET %s"
                    parameters.append(offset)
                cursor.execute(query, tuple(parameters))
                while row := cursor.fetchone():
                    yield row
        finally:
            connection.close()

    def _token_rows(self, sentence_ref: str) -> list[tuple[Any, ...]]:
        connection = _connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT t.token_ref, t.local_token_ordinal,
                           t.start_char, t.end_char,
                           orth.symbol_text, lemma.symbol_text,
                           pos.symbol_text, tag.symbol_text,
                           dependency.symbol_text,
                           t.head_start_char, t.head_end_char
                    FROM execution.semantic_parser_token AS t
                    JOIN execution.semantic_parser_symbol AS orth
                      ON orth.symbol_ref = t.orth_ref
                    LEFT JOIN execution.semantic_parser_symbol AS lemma
                      ON lemma.symbol_ref = t.lemma_ref
                    LEFT JOIN execution.semantic_parser_symbol AS pos
                      ON pos.symbol_ref = t.pos_ref
                    LEFT JOIN execution.semantic_parser_symbol AS tag
                      ON tag.symbol_ref = t.tag_ref
                    LEFT JOIN execution.semantic_parser_symbol AS dependency
                      ON dependency.symbol_ref = t.dependency_ref
                    WHERE t.sentence_ref = %s
                    ORDER BY t.local_token_ordinal
                    """,
                    (sentence_ref,),
                )
                return list(cursor.fetchall())
        finally:
            connection.close()

    def _morphology(self, token_refs: Sequence[str]) -> dict[str, dict[str, list[str]]]:
        if not token_refs:
            return {}
        connection = _connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT m.token_ref, feature.symbol_text, value.symbol_text
                    FROM execution.semantic_parser_token_morphology AS m
                    JOIN execution.semantic_parser_symbol AS feature
                      ON feature.symbol_ref = m.feature_ref
                    JOIN execution.semantic_parser_symbol AS value
                      ON value.symbol_ref = m.value_ref
                    WHERE m.token_ref = ANY(%s)
                    ORDER BY m.token_ref, m.ordinal
                    """,
                    (list(token_refs),),
                )
                result: dict[str, dict[str, list[str]]] = {}
                for token_ref, feature, value in cursor.fetchall():
                    result.setdefault(str(token_ref), {}).setdefault(str(feature), []).append(str(value))
                return result
        finally:
            connection.close()

    def _materialize_sentence(self, row: tuple[Any, ...]) -> Mapping[str, Any]:
        sentence_ref, start_char, end_char, partition_ref = row
        token_rows = self._token_rows(str(sentence_ref))
        morph = self._morphology([str(value[0]) for value in token_rows])
        tokens: list[dict[str, Any]] = []
        for token_row in token_rows:
            (
                token_ref,
                _local_ordinal,
                token_start,
                token_end,
                orth,
                lemma,
                pos,
                tag,
                dependency,
                head_start,
                _head_end,
            ) = token_row
            start = int(token_start)
            end = int(token_end)
            tokens.append(
                {
                    "token_ref": str(token_ref),
                    "index": start,
                    "text": self._text[start:end],
                    "lemma": str(lemma or orth or self._text[start:end]),
                    "pos": str(pos or ""),
                    "tag": str(tag or ""),
                    "morph": morph.get(str(token_ref), {}),
                    "dep": str(dependency or ""),
                    "head_index": int(head_start if head_start is not None else start),
                    "start": start,
                    "end": end,
                }
            )
        start = int(start_char)
        end = int(end_char)
        return {
            "sentence_ref": str(sentence_ref),
            "text": self._text[start:end],
            "start": start,
            "end": end,
            "tokens": tokens,
            "partition_ref": str(partition_ref),
        }

    def _iter_sentences(self) -> Iterator[Mapping[str, Any]]:
        for row in self._sentence_rows():
            yield self._materialize_sentence(row)

    def _sentence_at(self, index: int) -> Mapping[str, Any]:
        row = next(self._sentence_rows(offset=index), None)
        if row is None:
            raise IndexError(index)
        return self._materialize_sentence(row)


def _safe_boundary(text: str, *, start: int, desired: int, target: int) -> int:
    if desired >= len(text):
        return len(text)
    radius = max(1_024, target // 5)
    floor = max(start + 1, desired - radius)
    ceiling = min(len(text), desired + radius)
    window = text[floor:ceiling]
    before = desired - floor
    for pattern in (r"\n\s*\n", r"\n", r"(?<=[.!?])\s+", r"\s+"):
        matches = tuple(re.finditer(pattern, window))
        prior = [match for match in matches if match.end() <= before + 1]
        if prior:
            return floor + prior[-1].end()
        if matches:
            return floor + matches[0].end()
    return desired


def build_structural_partitions(
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    source_locator: str,
    parser_contract_ref: str,
    canonical_text: str,
    policy: ParserStreamingPolicy,
) -> tuple[ParserPartition, ...]:
    """Build disjoint owner intervals at structural text boundaries."""

    if not canonical_text:
        raise ValueError("parser source text must be non-empty")
    intervals: list[tuple[int, int]] = []
    owner_start = 0
    while owner_start < len(canonical_text):
        desired = min(len(canonical_text), owner_start + policy.target_chars)
        owner_end = _safe_boundary(
            canonical_text,
            start=owner_start,
            desired=desired,
            target=policy.target_chars,
        )
        if owner_end <= owner_start:
            owner_end = desired
        intervals.append((owner_start, owner_end))
        owner_start = owner_end
    partitions: list[ParserPartition] = []
    for sequence_no, (start, end) in enumerate(intervals):
        context_start = max(0, start - policy.context_chars)
        context_end = min(len(canonical_text), end + policy.context_chars)
        partition_ref = _ref(
            "parser-partition:",
            STREAMING_SPACY_CONTRACT,
            run_ref,
            document_ref,
            source_ref,
            parser_contract_ref,
            "structural",
            start,
            end,
            context_start,
            context_end,
        )
        partitions.append(
            ParserPartition(
                partition_ref=partition_ref,
                run_ref=run_ref,
                document_ref=document_ref,
                source_ref=source_ref,
                source_locator=source_locator,
                parser_contract_ref=parser_contract_ref,
                partition_kind="structural",
                sequence_no=sequence_no,
                owner_start_char=start,
                owner_end_char=end,
                context_start_char=context_start,
                context_end_char=context_end,
                repair_depth=0,
                resolves_obligation_ref=None,
                lease_token="",
                lease_epoch=0,
                attempt_ref="",
            )
        )
    return tuple(partitions)


def _write_source(canonical_text: str, artifact_root: Path) -> tuple[str, Path, bytes, int]:
    encoded = canonical_text.encode("utf-8")
    digest = sha256(encoded).digest()
    source_ref = "parser-source:" + digest.hex()
    path = artifact_root / "source" / digest.hex()[:2] / f"{digest.hex()}.utf8"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(f".tmp.{os.getpid()}")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    if path.stat().st_size != len(encoded):
        raise RuntimeError("canonical parser source size changed")
    return source_ref, path, digest, len(encoded)


def _register_execution(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    source_path: Path,
    source_digest: bytes,
    source_bytes: int,
    parser_contract_ref: str,
    partitions: Sequence[ParserPartition],
) -> None:
    connection = _connect(database_url)
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
                         byte_count, encoding_ref, locator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_ref) DO NOTHING
                    """,
                    (
                        source_ref,
                        run_ref,
                        document_ref,
                        source_digest,
                        source_bytes,
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
                             context_start_char, context_end_char, repair_depth)
                        VALUES (%s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s)
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


def _lease_partitions(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    batch_size: int,
    lease_seconds: int,
) -> tuple[ParserPartition, ...]:
    connection = _connect(database_url)
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
                    prior_epoch = int(row[13])
                    epoch = prior_epoch + 1
                    token = uuid4().hex
                    attempt_ref = f"parser-attempt:{row[0]}:{epoch}:{token}"
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
                            repair_depth=int(row[11]),
                            resolves_obligation_ref=(str(row[12]) if row[12] else None),
                            lease_token=token,
                            lease_epoch=epoch,
                            attempt_ref=attempt_ref,
                        )
                    )
    finally:
        connection.close()
    return tuple(leased)


def _source_slice(partition: ParserPartition) -> str:
    path = Path(partition.source_locator)
    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as source:
            # Character offsets index Unicode text, not UTF-8 bytes.  Decode one
            # bounded source view; the complete source is never copied per Doc.
            text = source[:].decode("utf-8")
            return text[partition.context_start_char : partition.context_end_char]


def _symbol(kind: str, text: str) -> tuple[str, str, str]:
    value = str(text or "")
    return (_ref("parser-symbol:", kind, value), kind, value)


def _sentence_ref(partition: ParserPartition, start: int, end: int) -> str:
    return _ref(
        "parser-sentence:",
        partition.run_ref,
        partition.document_ref,
        SEGMENTATION_CONTRACT,
        start,
        end,
    )


def _token_ref(sentence_ref: str, start: int, end: int) -> str:
    return _ref("parser-token:", TOKEN_IDENTITY_CONTRACT, sentence_ref, start, end)


def _seal_docbin(doc: Any, partition: ParserPartition, artifact_root: Path) -> tuple[str, Path, bytes, int]:
    from spacy.tokens import DocBin

    docbin = DocBin(store_user_data=False)
    docbin.add(doc)
    payload = docbin.to_bytes()
    digest = sha256(payload).digest()
    artifact_ref = _ref("parser-artifact:", partition.partition_ref, digest)
    path = artifact_root / "docbin" / digest.hex()[:2] / f"{digest.hex()}.spacy"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(f".tmp.{os.getpid()}")
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    return artifact_ref, path, digest, len(payload)


def _refresh_coverage(cursor: Any, *, run_ref: str, document_ref: str) -> str:
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
    total, completed, failed = (int(value) for value in cursor.fetchone())
    cursor.execute(
        """
        SELECT count(*)
        FROM execution.semantic_parser_boundary_obligation
        WHERE run_ref = %s AND document_ref = %s AND state = 'open'
        """,
        (run_ref, document_ref),
    )
    open_obligations = int(cursor.fetchone()[0])
    state = "failed" if failed else (
        "complete" if completed == total and open_obligations == 0 else "open"
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
        event_ref = _ref("parser-event:", run_ref, document_ref, "coverage-closed")
        cursor.execute(
            """
            INSERT INTO execution.semantic_parser_outbox
                (event_ref, event_type_ref, run_ref, document_ref)
            VALUES (%s, 'parser.document-coverage.closed.v1', %s, %s)
            ON CONFLICT (event_ref) DO NOTHING
            """,
            (event_ref, run_ref, document_ref),
        )
    return state


def _create_boundary_repair(
    cursor: Any,
    *,
    partition: ParserPartition,
    start: int,
    end: int,
    policy: ParserStreamingPolicy,
) -> tuple[str, str | None]:
    obligation_ref = _ref(
        "parser-boundary-obligation:",
        partition.run_ref,
        partition.document_ref,
        "sentence_crosses_owner",
        start,
        end,
    )
    if partition.repair_depth >= policy.max_repair_depth:
        cursor.execute(
            """
            INSERT INTO execution.semantic_parser_boundary_obligation
                (obligation_ref, run_ref, document_ref, source_partition_ref,
                 obligation_kind, suspected_start_char, suspected_end_char, state)
            VALUES (%s, %s, %s, %s, 'sentence_crosses_owner', %s, %s, 'failed')
            ON CONFLICT (obligation_ref) DO UPDATE SET state = 'failed'
            """,
            (
                obligation_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                start,
                end,
            ),
        )
        return obligation_ref, None
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (partition.run_ref,))
    cursor.execute(
        "SELECT coalesce(max(sequence_no), -1) + 1 FROM execution.semantic_parser_partition WHERE run_ref = %s",
        (partition.run_ref,),
    )
    sequence_no = int(cursor.fetchone()[0])
    source_length = Path(partition.source_locator).read_bytes().decode("utf-8").__len__()
    context_start = max(0, start - policy.context_chars)
    context_end = min(source_length, end + policy.context_chars)
    repair_ref = _ref(
        "parser-partition:",
        STREAMING_SPACY_CONTRACT,
        partition.run_ref,
        partition.document_ref,
        partition.source_ref,
        partition.parser_contract_ref,
        "boundary_repair",
        obligation_ref,
        start,
        end,
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_boundary_obligation
            (obligation_ref, run_ref, document_ref, source_partition_ref,
             repair_partition_ref, obligation_kind,
             suspected_start_char, suspected_end_char, state)
        VALUES (%s, %s, %s, %s, %s, 'sentence_crosses_owner', %s, %s, 'open')
        ON CONFLICT (obligation_ref) DO NOTHING
        """,
        (
            obligation_ref,
            partition.run_ref,
            partition.document_ref,
            partition.partition_ref,
            repair_ref,
            start,
            end,
        ),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_partition
            (partition_ref, run_ref, document_ref, source_ref,
             parser_contract_ref, partition_kind, sequence_no,
             owner_start_char, owner_end_char, context_start_char,
             context_end_char, repair_depth, resolves_obligation_ref)
        VALUES (%s, %s, %s, %s, %s, 'boundary_repair', %s,
                %s, %s, %s, %s, %s, %s)
        ON CONFLICT (partition_ref) DO NOTHING
        """,
        (
            repair_ref,
            partition.run_ref,
            partition.document_ref,
            partition.source_ref,
            partition.parser_contract_ref,
            sequence_no,
            start,
            end,
            context_start,
            context_end,
            partition.repair_depth + 1,
            obligation_ref,
        ),
    )
    event_ref = _ref("parser-event:", obligation_ref, "opened")
    cursor.execute(
        """
        INSERT INTO execution.semantic_parser_outbox
            (event_ref, event_type_ref, run_ref, document_ref,
             partition_ref, obligation_ref)
        VALUES (%s, 'parser.boundary-obligation.opened.v1', %s, %s, %s, %s)
        ON CONFLICT (event_ref) DO NOTHING
        """,
        (
            event_ref,
            partition.run_ref,
            partition.document_ref,
            partition.partition_ref,
            obligation_ref,
        ),
    )
    return obligation_ref, repair_ref


def _copy_rows(cursor: Any, table: str, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        return
    temporary = "tmp_" + table.removeprefix("semantic_")
    column_sql = ", ".join(columns)
    cursor.execute(
        f"CREATE TEMP TABLE {temporary} (LIKE execution.{table} INCLUDING DEFAULTS) ON COMMIT DROP"
    )
    with cursor.copy(f"COPY {temporary} ({column_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    cursor.execute(
        f"INSERT INTO execution.{table} ({column_sql}) SELECT {column_sql} FROM {temporary} ON CONFLICT DO NOTHING"
    )


def _commit_doc(
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
        "sentence_segmentation": any(name in pipe_names for name in ("parser", "senter", "sentencizer")),
        "part_of_speech": any(name in pipe_names for name in ("tagger", "morphologizer")),
        "morphology": any(name in pipe_names for name in ("tagger", "morphologizer")),
        "dependencies": "parser" in pipe_names,
        "named_entities": "ner" in pipe_names,
    }
    artifact = (
        _seal_docbin(doc, partition, artifact_root) if policy.cache_docbin else None
    )
    sentence_rows: list[tuple[Any, ...]] = []
    token_rows: list[tuple[Any, ...]] = []
    morph_rows: list[tuple[Any, ...]] = []
    entity_rows: list[tuple[Any, ...]] = []
    symbols: dict[str, tuple[str, str, str]] = {}
    crossing_sentences: list[tuple[int, int]] = []
    sentence_for_span: list[tuple[int, int, str]] = []
    sentence_spans = tuple(doc.sents) if doc.has_annotation("SENT_START") else (doc[:],)
    owned_sentence_ordinal = 0
    for span in sentence_spans:
        start = partition.context_start_char + int(span.start_char)
        end = partition.context_start_char + int(span.end_char)
        overlaps_owner = start < partition.owner_end_char and end > partition.owner_start_char
        if not overlaps_owner:
            continue
        if not (start >= partition.owner_start_char and end <= partition.owner_end_char):
            crossing_sentences.append((start, end))
            continue
        sentence_ref = _sentence_ref(partition, start, end)
        sentence_rows.append(
            (
                sentence_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                owned_sentence_ordinal,
                start,
                end,
                SEGMENTATION_CONTRACT,
                "owned",
            )
        )
        sentence_for_span.append((start, end, sentence_ref))
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
            head_end = partition.context_start_char + int(token.head.idx + len(token.head.text))
            orth = _symbol("orth", token.text)
            lemma = _symbol("lemma", token.lemma_ or token.text)
            pos = _symbol("pos", token.pos_)
            tag = _symbol("tag", token.tag_)
            dependency = _symbol("dependency", token.dep_)
            for symbol in (orth, lemma, pos, tag, dependency):
                symbols[symbol[0]] = symbol
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
            for feature, values in sorted(token.morph.to_dict().items()):
                feature_symbol = _symbol("morph_feature", feature)
                symbols[feature_symbol[0]] = feature_symbol
                for value in values if isinstance(values, (list, tuple)) else (values,):
                    value_symbol = _symbol("morph_value", str(value))
                    symbols[value_symbol[0]] = value_symbol
                    morph_rows.append((token_ref, feature_symbol[0], value_symbol[0], morph_ordinal))
                    morph_ordinal += 1
        owned_sentence_ordinal += 1
    for entity in getattr(doc, "ents", ()):
        start = partition.context_start_char + int(entity.start_char)
        end = partition.context_start_char + int(entity.end_char)
        if not (start >= partition.owner_start_char and end <= partition.owner_end_char):
            continue
        entity_type = _symbol("entity_type", entity.label_)
        symbols[entity_type[0]] = entity_type
        sentence_ref = next(
            (ref for sent_start, sent_end, ref in sentence_for_span if start >= sent_start and end <= sent_end),
            None,
        )
        entity_ref = _ref(
            "parser-entity:",
            partition.run_ref,
            partition.document_ref,
            start,
            end,
            entity_type[0],
        )
        entity_rows.append(
            (
                entity_ref,
                partition.run_ref,
                partition.document_ref,
                partition.partition_ref,
                sentence_ref,
                start,
                end,
                entity_type[0],
            )
        )

    connection = _connect(database_url)
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
                state, token, epoch = cursor.fetchone()
                if str(state) == "completed":
                    return
                if str(state) != "leased" or token != partition.lease_token or int(epoch) != partition.lease_epoch:
                    cursor.execute(
                        "UPDATE execution.semantic_parser_attempt SET state = 'stale', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s",
                        (partition.attempt_ref,),
                    )
                    return
                for symbol_ref, kind, text in symbols.values():
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_symbol
                            (symbol_ref, symbol_kind, symbol_text)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (symbol_ref) DO NOTHING
                        """,
                        (symbol_ref, kind, text),
                    )
                _copy_rows(
                    cursor,
                    "semantic_parser_sentence",
                    (
                        "sentence_ref", "run_ref", "document_ref", "partition_ref",
                        "local_sentence_ordinal", "start_char", "end_char",
                        "segmentation_contract_ref", "ownership_state",
                    ),
                    sentence_rows,
                )
                _copy_rows(
                    cursor,
                    "semantic_parser_token",
                    (
                        "token_ref", "run_ref", "document_ref", "partition_ref",
                        "sentence_ref", "local_token_ordinal", "start_char", "end_char",
                        "orth_ref", "lemma_ref", "pos_ref", "tag_ref",
                        "dependency_ref", "head_token_ref", "head_start_char", "head_end_char",
                    ),
                    token_rows,
                )
                _copy_rows(
                    cursor,
                    "semantic_parser_token_morphology",
                    ("token_ref", "feature_ref", "value_ref", "ordinal"),
                    morph_rows,
                )
                _copy_rows(
                    cursor,
                    "semantic_parser_entity_span",
                    (
                        "entity_ref", "run_ref", "document_ref", "partition_ref",
                        "sentence_ref", "start_char", "end_char", "entity_type_ref",
                    ),
                    entity_rows,
                )
                repair_refs: list[str] = []
                for start, end in crossing_sentences:
                    _obligation_ref, repair_ref = _create_boundary_repair(
                        cursor,
                        partition=partition,
                        start=start,
                        end=end,
                        policy=policy,
                    )
                    if repair_ref is not None:
                        repair_refs.append(repair_ref)
                if partition.resolves_obligation_ref:
                    cursor.execute(
                        """
                        UPDATE execution.semantic_parser_boundary_obligation
                        SET state = 'resolved', resolved_at = CURRENT_TIMESTAMP
                        WHERE obligation_ref = %s
                          AND EXISTS (
                              SELECT 1 FROM execution.semantic_parser_sentence
                              WHERE partition_ref = %s
                          )
                        """,
                        (partition.resolves_obligation_ref, partition.partition_ref),
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
                    raise RuntimeError("parser partition fence changed during commit")
                cursor.execute(
                    "UPDATE execution.semantic_parser_attempt SET state = 'completed', completed_at = CURRENT_TIMESTAMP WHERE attempt_ref = %s",
                    (partition.attempt_ref,),
                )
                for sentence_row in sentence_rows:
                    sentence_ref = str(sentence_row[0])
                    event_ref = _ref("parser-event:", sentence_ref, "committed")
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_parser_outbox
                            (event_ref, event_type_ref, run_ref, document_ref,
                             partition_ref, sentence_ref)
                        VALUES (%s, 'parser.sentence.committed.v1', %s, %s, %s, %s)
                        ON CONFLICT (event_ref) DO NOTHING
                        """,
                        (
                            event_ref,
                            partition.run_ref,
                            partition.document_ref,
                            partition.partition_ref,
                            sentence_ref,
                        ),
                    )
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_parser_outbox
                        (event_ref, event_type_ref, run_ref, document_ref, partition_ref)
                    VALUES (%s, 'parser.partition.completed.v1', %s, %s, %s)
                    ON CONFLICT (event_ref) DO NOTHING
                    """,
                    (
                        _ref("parser-event:", partition.partition_ref, "completed"),
                        partition.run_ref,
                        partition.document_ref,
                        partition.partition_ref,
                    ),
                )
                _refresh_coverage(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                )
    finally:
        connection.close()


def _fail_partition(database_url: str, partition: ParserPartition, error: BaseException) -> None:
    connection = _connect(database_url)
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
                _refresh_coverage(
                    cursor,
                    run_ref=partition.run_ref,
                    document_ref=partition.document_ref,
                )
    finally:
        connection.close()


def _worker_drain(
    database_url: str,
    run_ref: str,
    worker_ref: str,
    policy: ParserStreamingPolicy,
    artifact_root: str,
) -> int:
    from src.nlp.spacy_adapter import get_default_nlp

    pipeline = get_default_nlp()
    completed = 0
    while True:
        partitions = _lease_partitions(
            database_url,
            run_ref=run_ref,
            worker_ref=worker_ref,
            batch_size=policy.batch_size,
            lease_seconds=policy.lease_seconds,
        )
        if not partitions:
            return completed
        stream = ((_source_slice(partition), partition) for partition in partitions)
        try:
            for doc, partition in pipeline.pipe(
                stream,
                as_tuples=True,
                batch_size=policy.batch_size,
                n_process=1,
            ):
                started = monotonic_ns()
                try:
                    _commit_doc(
                        database_url,
                        partition=partition,
                        doc=doc,
                        policy=policy,
                        artifact_root=Path(artifact_root),
                        pipeline=pipeline,
                        elapsed_ns=max(0, monotonic_ns() - started),
                    )
                    completed += 1
                except BaseException as error:
                    _fail_partition(database_url, partition, error)
                    raise
        except BaseException:
            raise


def _recover_expired(database_url: str, *, run_ref: str) -> int:
    connection = _connect(database_url)
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


def _execution_state(database_url: str, *, run_ref: str, document_ref: str) -> tuple[str, int, int, int]:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       count(partition.partition_ref) FILTER (WHERE partition.state = 'ready'),
                       count(partition.partition_ref) FILTER (WHERE partition.state = 'leased'),
                       count(partition.partition_ref) FILTER (WHERE partition.state = 'failed')
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


def _summary(database_url: str, *, run_ref: str, document_ref: str, source_ref: str, parser_contract_ref: str) -> ParserExecutionSummary:
    connection = _connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       count(DISTINCT sentence.sentence_ref),
                       count(DISTINCT token.token_ref),
                       count(DISTINCT partition.partition_ref),
                       count(DISTINCT entity.entity_ref),
                       count(DISTINCT obligation.obligation_ref)
                FROM execution.semantic_parser_document_coverage AS coverage
                LEFT JOIN execution.semantic_parser_partition AS partition
                  ON partition.run_ref = coverage.run_ref
                 AND partition.document_ref = coverage.document_ref
                LEFT JOIN execution.semantic_parser_sentence AS sentence
                  ON sentence.run_ref = coverage.run_ref
                 AND sentence.document_ref = coverage.document_ref
                LEFT JOIN execution.semantic_parser_token AS token
                  ON token.run_ref = coverage.run_ref
                 AND token.document_ref = coverage.document_ref
                LEFT JOIN execution.semantic_parser_entity_span AS entity
                  ON entity.run_ref = coverage.run_ref
                 AND entity.document_ref = coverage.document_ref
                LEFT JOIN execution.semantic_parser_boundary_obligation AS obligation
                  ON obligation.run_ref = coverage.run_ref
                 AND obligation.document_ref = coverage.document_ref
                WHERE coverage.run_ref = %s AND coverage.document_ref = %s
                GROUP BY coverage.state
                """,
                (run_ref, document_ref),
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


def run_streaming_spacy_execution(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text: str,
    parser_contract_ref: str,
    artifact_root: str | Path,
    worker_count: int = 2,
    policy: ParserStreamingPolicy | None = None,
) -> PostgresSentenceCarrier:
    """Parse and commit one document without a document-sized parser result."""

    if not 1 <= worker_count <= 32:
        raise ValueError("parser worker_count must be between 1 and 32")
    policy = policy or ParserStreamingPolicy()
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    source_ref, source_path, source_digest, source_bytes = _write_source(canonical_text, root)
    partitions = build_structural_partitions(
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref=parser_contract_ref,
        canonical_text=canonical_text,
        policy=policy,
    )
    _register_execution(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_path=source_path,
        source_digest=source_digest,
        source_bytes=source_bytes,
        parser_contract_ref=parser_contract_ref,
        partitions=partitions,
    )
    for round_ordinal in range(128):
        context = __import__("multiprocessing").get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
            initializer=linux_parent_death_initializer,
        ) as pool:
            futures = [
                pool.submit(
                    _worker_drain,
                    database_url,
                    run_ref,
                    f"parser-worker:{run_ref}:{round_ordinal}:{index}",
                    policy,
                    str(root),
                )
                for index in range(worker_count)
            ]
            for future in futures:
                future.result()
        _recover_expired(database_url, run_ref=run_ref)
        state, ready, leased, failed = _execution_state(
            database_url,
            run_ref=run_ref,
            document_ref=document_ref,
        )
        if failed:
            raise RuntimeError("typed parser partition failed")
        if state == "complete":
            break
        if ready:
            continue
        if leased:
            time.sleep(min(1.0, policy.lease_seconds / 4))
            continue
        raise RuntimeError("parser coverage remained open without runnable work")
    else:
        raise RuntimeError("parser execution exceeded bounded scheduling rounds")
    summary = _summary(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        parser_contract_ref=parser_contract_ref,
    )
    if summary.coverage_state != "complete":
        raise RuntimeError("parser document coverage did not close")
    parser_receipt = {
        "backend_ref": "parser:spacy:typed-postgresql",
        "parser_contract_ref": parser_contract_ref,
        "execution_contract_ref": STREAMING_SPACY_CONTRACT,
        "source_ref": source_ref,
        "sentence_count": summary.sentence_count,
        "token_count": summary.token_count,
        "partition_count": summary.partition_count,
        "entity_count": summary.entity_count,
        "boundary_obligation_count": summary.boundary_obligation_count,
        "coverage_state": summary.coverage_state,
        "authority": "postgresql_typed_parser_observations",
    }
    return PostgresSentenceCarrier(
        database_url=database_url,
        canonical_text=canonical_text,
        summary=summary,
        parser_receipt=parser_receipt,
    )


__all__ = [
    "DOCBIN_ENCODING",
    "ParserExecutionSummary",
    "ParserPartition",
    "ParserStreamingPolicy",
    "PostgresSentenceCarrier",
    "SEGMENTATION_CONTRACT",
    "STREAMING_SPACY_CONTRACT",
    "build_structural_partitions",
    "run_streaming_spacy_execution",
]
