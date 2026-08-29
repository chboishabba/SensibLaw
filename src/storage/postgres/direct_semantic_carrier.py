"""Evidence-backed return surface for direct semantic execution.

This carrier deliberately does not reconstruct lemma/POS/dependency fields that
were not persisted in direct mode.  It exposes source text, sentence spans, and
stable token evidence only.  Legacy parser compatibility reconstruction remains
available exclusively through ``PostgresSentenceCarrier`` in reference/parity
mode.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from src.storage.postgres.spacy_parser_model import ParserExecutionSummary, connect


class _DirectSentenceSequence(Sequence[Mapping[str, Any]]):
    def __init__(self, carrier: "DirectSentenceCarrier", count: int) -> None:
        self._carrier = carrier
        self._count = count

    def __len__(self) -> int:
        return self._count

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        yield from self._carrier.iter_sentences()

    def __getitem__(self, index: int | slice) -> Any:
        if isinstance(index, slice):
            return tuple(self)[index]
        if index < 0:
            index += self._count
        if not 0 <= index < self._count:
            raise IndexError(index)
        return self._carrier.sentence_at(index)


def direct_execution_summary(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    parser_contract_ref: str,
) -> ParserExecutionSummary:
    """Summarise consumed observations from receipts, not parser row counts."""

    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       COALESCE(sum(receipt.sentence_count), 0),
                       COALESCE(sum(receipt.token_count), 0),
                       count(partition.partition_ref),
                       COALESCE(sum(receipt.entity_count), 0),
                       (SELECT count(*)
                          FROM execution.semantic_parser_boundary_obligation
                         WHERE run_ref = %s AND document_ref = %s)
                  FROM execution.semantic_parser_document_coverage AS coverage
                  LEFT JOIN execution.semantic_parser_partition AS partition
                    ON partition.run_ref = coverage.run_ref
                   AND partition.document_ref = coverage.document_ref
                  LEFT JOIN execution.semantic_parser_partition_receipt AS receipt
                    ON receipt.partition_ref = partition.partition_ref
                 WHERE coverage.run_ref = %s
                   AND coverage.document_ref = %s
                 GROUP BY coverage.state
                """,
                (run_ref, document_ref, run_ref, document_ref),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("direct semantic execution summary is missing")
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


class DirectSentenceCarrier(Mapping[str, Any]):
    """Stable source-evidence view with no parser-token reconstruction."""

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
        self._sentences = _DirectSentenceSequence(self, summary.sentence_count)

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

    def iter_sentences(self) -> Iterator[Mapping[str, Any]]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT evidence.sentence_digest,
                           min(evidence.start_char),
                           max(evidence.end_char)
                      FROM execution.semantic_pnf_source_evidence AS evidence
                     GROUP BY evidence.sentence_digest
                     ORDER BY min(evidence.start_char), max(evidence.end_char),
                              evidence.sentence_digest
                    """
                )
                sentence_rows = tuple(cursor.fetchall())
                for sentence_digest, start_char, end_char in sentence_rows:
                    start = int(start_char)
                    end = int(end_char)
                    cursor.execute(
                        """
                        SELECT evidence_digest, token_digest, start_char, end_char
                          FROM execution.semantic_pnf_source_evidence
                         WHERE sentence_digest = %s
                         ORDER BY start_char, end_char, evidence_id
                        """,
                        (sentence_digest,),
                    )
                    tokens = tuple(
                        {
                            "evidence_digest": bytes(evidence_digest),
                            "token_digest": bytes(token_digest),
                            "start": int(token_start),
                            "end": int(token_end),
                            "text": self._text[int(token_start):int(token_end)],
                        }
                        for evidence_digest, token_digest, token_start, token_end
                        in cursor.fetchall()
                    )
                    yield {
                        "sentence_digest": bytes(sentence_digest),
                        "text": self._text[start:end],
                        "start": start,
                        "end": end,
                        "tokens": tokens,
                        "authority": "stable_source_evidence",
                    }
        finally:
            connection.close()

    def sentence_at(self, index: int) -> Mapping[str, Any]:
        for ordinal, sentence in enumerate(self.iter_sentences()):
            if ordinal == index:
                return sentence
        raise IndexError(index)


__all__ = ["DirectSentenceCarrier", "direct_execution_summary"]
