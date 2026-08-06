"""Typed identities and lazy views for streamed spaCy execution."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
from typing import Any

from src.policy.carriers.canonical import canonical_fields_sha256


STREAMING_SPACY_CONTRACT = "postgres-streaming-spacy:v1"
SEGMENTATION_CONTRACT = "spacy-sentence-boundaries:v1"
TOKEN_IDENTITY_CONTRACT = "source-coordinate-parser-token:v1"
DOCBIN_ENCODING = "spacy-docbin:v1"
SOURCE_ENCODING = "utf8-canonical-source:v1"


def typed_ref(prefix: str, *fields: object) -> str:
    return prefix + canonical_fields_sha256(*fields)


def connect(database_url: str) -> Any:
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise RuntimeError("psycopg is required for typed parser execution") from error
    return psycopg.connect(database_url, autocommit=False)


@dataclass(frozen=True)
class ParserStreamingPolicy:
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
    owner_start_byte: int
    owner_end_byte: int
    context_start_byte: int
    context_end_byte: int
    repair_depth: int = 0
    resolves_obligation_ref: str | None = None
    lease_token: str = ""
    lease_epoch: int = 0
    attempt_ref: str = ""

    @property
    def context_text_byte_count(self) -> int:
        return self.context_end_byte - self.context_start_byte


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


def safe_boundary(text: str, *, start: int, desired: int, target: int) -> int:
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


def byte_offsets(text: str, char_offsets: Sequence[int]) -> dict[int, int]:
    """Resolve only requested character boundaries in one forward UTF-8 pass."""

    requested = sorted(set(int(value) for value in char_offsets))
    if not requested or requested[0] < 0 or requested[-1] > len(text):
        raise ValueError("character boundary lies outside canonical source")
    result: dict[int, int] = {}
    prior_char = 0
    prior_byte = 0
    for char_offset in requested:
        prior_byte += len(text[prior_char:char_offset].encode("utf-8"))
        result[char_offset] = prior_byte
        prior_char = char_offset
    return result


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
    """Build disjoint owner intervals at paragraph/newline/sentence boundaries."""

    if not canonical_text:
        raise ValueError("parser source text must be non-empty")
    intervals: list[tuple[int, int]] = []
    owner_start = 0
    while owner_start < len(canonical_text):
        desired = min(len(canonical_text), owner_start + policy.target_chars)
        owner_end = safe_boundary(
            canonical_text,
            start=owner_start,
            desired=desired,
            target=policy.target_chars,
        )
        if owner_end <= owner_start:
            owner_end = desired
        intervals.append((owner_start, owner_end))
        owner_start = owner_end
    char_boundaries: list[int] = []
    expanded: list[tuple[int, int, int, int]] = []
    for start, end in intervals:
        context_start = max(0, start - policy.context_chars)
        context_end = min(len(canonical_text), end + policy.context_chars)
        expanded.append((start, end, context_start, context_end))
        char_boundaries.extend((start, end, context_start, context_end))
    bytes_by_char = byte_offsets(canonical_text, char_boundaries)
    partitions: list[ParserPartition] = []
    for sequence_no, (start, end, context_start, context_end) in enumerate(expanded):
        partition_ref = typed_ref(
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
                owner_start_byte=bytes_by_char[start],
                owner_end_byte=bytes_by_char[end],
                context_start_byte=bytes_by_char[context_start],
                context_end_byte=bytes_by_char[context_end],
            )
        )
    return tuple(partitions)


def write_source(canonical_text: str, artifact_root: Path) -> tuple[str, Path, bytes, int]:
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


def read_partition_text(partition: ParserPartition) -> str:
    """Read and decode only the partition context bytes."""

    with Path(partition.source_locator).open("rb") as handle:
        handle.seek(partition.context_start_byte)
        encoded = handle.read(partition.context_text_byte_count)
    text = encoded.decode("utf-8")
    if len(text) != partition.context_end_char - partition.context_start_char:
        raise RuntimeError("parser partition character/byte coordinates diverged")
    return text


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
    """One-sentence-at-a-time compatibility view over typed parser rows."""

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
        connection = connect(self.database_url)
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
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT t.token_ref, t.start_char, t.end_char,
                           orth.symbol_text, lemma.symbol_text,
                           pos.symbol_text, tag.symbol_text,
                           dependency.symbol_text, t.head_start_char
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
        connection = connect(self.database_url)
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
        for token_ref, token_start, token_end, orth, lemma, pos, tag, dependency, head_start in token_rows:
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


__all__ = [
    "DOCBIN_ENCODING",
    "ParserExecutionSummary",
    "ParserPartition",
    "ParserStreamingPolicy",
    "PostgresSentenceCarrier",
    "SEGMENTATION_CONTRACT",
    "SOURCE_ENCODING",
    "STREAMING_SPACY_CONTRACT",
    "TOKEN_IDENTITY_CONTRACT",
    "build_structural_partitions",
    "byte_offsets",
    "connect",
    "read_partition_text",
    "typed_ref",
    "write_source",
]
