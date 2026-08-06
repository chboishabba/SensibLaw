"""Bounded compatibility views over typed parser authority.

The historical parser mapping remains available without reconstructing a full
parsed document. A named PostgreSQL cursor streams joined sentence, token, and
morphology rows in source order; at most one sentence is materialised at once.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any
from uuid import uuid4

from src.storage.postgres.spacy_parser_model import (
    ParserExecutionSummary,
    connect,
)


_SENTENCE_STREAM_SQL = """
    SELECT sentence.sentence_ref,
           sentence.start_char,
           sentence.end_char,
           sentence.partition_ref,
           token.token_ref,
           token.local_token_ordinal,
           token.start_char,
           token.end_char,
           orth.symbol_text,
           lemma.symbol_text,
           pos.symbol_text,
           tag.symbol_text,
           dependency.symbol_text,
           token.head_start_char,
           morphology.ordinal,
           feature.symbol_text,
           value.symbol_text
    FROM execution.semantic_parser_sentence AS sentence
    LEFT JOIN execution.semantic_parser_token AS token
      ON token.sentence_ref = sentence.sentence_ref
    LEFT JOIN execution.semantic_parser_symbol AS orth
      ON orth.symbol_ref = token.orth_ref
    LEFT JOIN execution.semantic_parser_symbol AS lemma
      ON lemma.symbol_ref = token.lemma_ref
    LEFT JOIN execution.semantic_parser_symbol AS pos
      ON pos.symbol_ref = token.pos_ref
    LEFT JOIN execution.semantic_parser_symbol AS tag
      ON tag.symbol_ref = token.tag_ref
    LEFT JOIN execution.semantic_parser_symbol AS dependency
      ON dependency.symbol_ref = token.dependency_ref
    LEFT JOIN execution.semantic_parser_token_morphology AS morphology
      ON morphology.token_ref = token.token_ref
    LEFT JOIN execution.semantic_parser_symbol AS feature
      ON feature.symbol_ref = morphology.feature_ref
    LEFT JOIN execution.semantic_parser_symbol AS value
      ON value.symbol_ref = morphology.value_ref
    WHERE sentence.run_ref = %s
      AND sentence.document_ref = %s
    ORDER BY sentence.start_char,
             sentence.end_char,
             sentence.sentence_ref,
             token.local_token_ordinal,
             morphology.ordinal
"""


class _SentenceSequence(Sequence[Mapping[str, Any]]):
    def __init__(self, carrier: "PostgresSentenceCarrier", sentence_count: int):
        self._carrier = carrier
        self._sentence_count = sentence_count

    def __len__(self) -> int:
        return self._sentence_count

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        yield from self._carrier.iter_sentences()

    def __getitem__(self, index: int | slice) -> Any:
        if isinstance(index, slice):
            return tuple(self)[index]
        if index < 0:
            index += self._sentence_count
        if not 0 <= index < self._sentence_count:
            raise IndexError(index)
        return self._carrier.sentence_at(index)


class PostgresSentenceCarrier(Mapping[str, Any]):
    """Historical mapping shape backed by one bounded relational stream."""

    def __init__(
        self,
        *,
        database_url: str,
        canonical_text: str,
        summary: ParserExecutionSummary,
        parser_receipt: Mapping[str, Any],
        fetch_size: int = 512,
    ) -> None:
        if fetch_size < 1:
            raise ValueError("parser sentence fetch size must be positive")
        self.database_url = database_url
        self._text = canonical_text
        self.summary = summary
        self._parser_receipt = dict(parser_receipt)
        self._fetch_size = fetch_size
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

    def iter_sentence_refs(self) -> Iterator[str]:
        """Yield stable sentence identities without loading token rows."""

        connection = connect(self.database_url)
        try:
            name = f"parser_sentence_refs_{uuid4().hex}"
            with connection.cursor(name=name) as cursor:
                cursor.itersize = self._fetch_size
                cursor.execute(
                    """
                    SELECT sentence_ref
                    FROM execution.semantic_parser_sentence
                    WHERE run_ref = %s AND document_ref = %s
                    ORDER BY start_char, end_char, sentence_ref
                    """,
                    (self.summary.run_ref, self.summary.document_ref),
                )
                for (sentence_ref,) in cursor:
                    yield str(sentence_ref)
        finally:
            connection.close()

    def iter_sentences(self) -> Iterator[Mapping[str, Any]]:
        """Yield one reconstructed compatibility sentence at a time."""

        connection = connect(self.database_url)
        try:
            name = f"parser_sentence_stream_{uuid4().hex}"
            with connection.cursor(name=name) as cursor:
                cursor.itersize = self._fetch_size
                cursor.execute(
                    _SENTENCE_STREAM_SQL,
                    (self.summary.run_ref, self.summary.document_ref),
                )
                yield from self._group_rows(cursor)
        finally:
            connection.close()

    def sentence_at(self, index: int) -> Mapping[str, Any]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sentence_ref
                    FROM execution.semantic_parser_sentence
                    WHERE run_ref = %s AND document_ref = %s
                    ORDER BY start_char, end_char, sentence_ref
                    LIMIT 1 OFFSET %s
                    """,
                    (self.summary.run_ref, self.summary.document_ref, index),
                )
                row = cursor.fetchone()
                if row is None:
                    raise IndexError(index)
                sentence_ref = str(row[0])
                cursor.execute(
                    _SENTENCE_STREAM_SQL.replace(
                        "WHERE sentence.run_ref = %s\n      AND sentence.document_ref = %s",
                        "WHERE sentence.run_ref = %s\n"
                        "      AND sentence.document_ref = %s\n"
                        "      AND sentence.sentence_ref = %s",
                    ),
                    (
                        self.summary.run_ref,
                        self.summary.document_ref,
                        sentence_ref,
                    ),
                )
                result = next(self._group_rows(cursor), None)
                if result is None:
                    raise IndexError(index)
                return result
        finally:
            connection.close()

    def _group_rows(self, rows: Any) -> Iterator[Mapping[str, Any]]:
        current_sentence_ref: str | None = None
        current_sentence_start = 0
        current_sentence_end = 0
        current_partition_ref = ""
        sentence_tokens: list[dict[str, Any]] = []
        current_token_ref: str | None = None
        current_token: dict[str, Any] | None = None

        def finish_token() -> None:
            nonlocal current_token, current_token_ref
            if current_token is not None:
                sentence_tokens.append(current_token)
            current_token = None
            current_token_ref = None

        def finish_sentence() -> Mapping[str, Any] | None:
            if current_sentence_ref is None:
                return None
            finish_token()
            return {
                "sentence_ref": current_sentence_ref,
                "text": self._text[current_sentence_start:current_sentence_end],
                "start": current_sentence_start,
                "end": current_sentence_end,
                "tokens": list(sentence_tokens),
                "partition_ref": current_partition_ref,
            }

        for row in rows:
            (
                sentence_ref_raw,
                sentence_start_raw,
                sentence_end_raw,
                partition_ref_raw,
                token_ref_raw,
                _local_token_ordinal,
                token_start_raw,
                token_end_raw,
                orth,
                lemma,
                pos,
                tag,
                dependency,
                head_start_raw,
                _morph_ordinal,
                feature,
                value,
            ) = row
            sentence_ref = str(sentence_ref_raw)
            if current_sentence_ref is not None and sentence_ref != current_sentence_ref:
                completed = finish_sentence()
                if completed is not None:
                    yield completed
                sentence_tokens.clear()
            if sentence_ref != current_sentence_ref:
                current_sentence_ref = sentence_ref
                current_sentence_start = int(sentence_start_raw)
                current_sentence_end = int(sentence_end_raw)
                current_partition_ref = str(partition_ref_raw)
                current_token_ref = None
                current_token = None

            if token_ref_raw is None:
                continue
            token_ref = str(token_ref_raw)
            if current_token_ref is not None and token_ref != current_token_ref:
                finish_token()
            if token_ref != current_token_ref:
                start = int(token_start_raw)
                end = int(token_end_raw)
                current_token_ref = token_ref
                current_token = {
                    "token_ref": token_ref,
                    "index": start,
                    "text": self._text[start:end],
                    "lemma": str(lemma or orth or self._text[start:end]),
                    "pos": str(pos or ""),
                    "tag": str(tag or ""),
                    "morph": {},
                    "dep": str(dependency or ""),
                    "head_index": int(
                        head_start_raw if head_start_raw is not None else start
                    ),
                    "start": start,
                    "end": end,
                }
            if current_token is not None and feature is not None and value is not None:
                morphology = current_token["morph"]
                morphology.setdefault(str(feature), []).append(str(value))

        completed = finish_sentence()
        if completed is not None:
            yield completed


__all__ = ["PostgresSentenceCarrier"]
