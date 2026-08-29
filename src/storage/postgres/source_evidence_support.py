"""Durable source-evidence support independent of parser-token surrogates.

This schema is additive: the historical ``semantic_parser_token`` relations remain
available to explicit reference/parity/audit execution, while direct publication owns
support through full source-evidence digests and coordinates.  ``evidence_id`` is only
a storage locator; ``evidence_digest`` is the stable semantic identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from src.pnf.packed_sentence_fibre import PackedSentenceFibre


@dataclass(frozen=True, slots=True)
class EvidenceSupportSchemaReceipt:
    parser_token_foreign_keys: int = 0
    authoritative_identity: str = "evidence_digest"


@dataclass(frozen=True, slots=True)
class SourceEvidenceRow:
    evidence_digest: bytes
    sentence_digest: bytes
    token_ordinal: int
    start_char: int
    end_char: int
    start_byte: int
    end_byte: int


def source_evidence_rows(fibre: PackedSentenceFibre) -> tuple[SourceEvidenceRow, ...]:
    rows = tuple(
        SourceEvidenceRow(
            evidence_digest=bytes(token.evidence_digest),
            sentence_digest=bytes(fibre.sentence_digest),
            token_ordinal=token.ordinal,
            start_char=token.start_char,
            end_char=token.end_char,
            start_byte=token.start_byte,
            end_byte=token.end_byte,
        )
        for token in fibre.tokens
    )
    if len({row.evidence_digest for row in rows}) != len(rows):
        raise RuntimeError("packed sentence contains duplicate source-evidence digests")
    return rows


def ensure_source_evidence_support_schema(cursor: Any) -> EvidenceSupportSchemaReceipt:
    """Install the G4 evidence carrier without any parser-token foreign key."""

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS execution.semantic_source_token_evidence (
            evidence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            evidence_digest BYTEA NOT NULL UNIQUE,
            run_ref TEXT NOT NULL,
            document_ref TEXT NOT NULL,
            sentence_digest BYTEA NOT NULL,
            token_ordinal INTEGER NOT NULL,
            start_char BIGINT NOT NULL,
            end_char BIGINT NOT NULL,
            start_byte BIGINT NOT NULL,
            end_byte BIGINT NOT NULL,
            CHECK (start_char >= 0 AND end_char >= start_char),
            CHECK (start_byte >= 0 AND end_byte >= start_byte),
            UNIQUE (run_ref, document_ref, sentence_digest, token_ordinal)
        );

        CREATE TABLE IF NOT EXISTS execution.semantic_pnf_object_evidence_support (
            object_id BIGINT NOT NULL
                REFERENCES execution.semantic_pnf_object(object_id) ON DELETE CASCADE,
            evidence_id BIGINT NOT NULL
                REFERENCES execution.semantic_source_token_evidence(evidence_id) ON DELETE RESTRICT,
            ordinal INTEGER NOT NULL,
            PRIMARY KEY (object_id, ordinal),
            UNIQUE (object_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS execution.semantic_pnf_factor_evidence_support (
            factor_id BIGINT NOT NULL
                REFERENCES execution.semantic_pnf_factor(factor_id) ON DELETE CASCADE,
            evidence_id BIGINT NOT NULL
                REFERENCES execution.semantic_source_token_evidence(evidence_id) ON DELETE RESTRICT,
            ordinal INTEGER NOT NULL,
            PRIMARY KEY (factor_id, ordinal),
            UNIQUE (factor_id, evidence_id)
        );
        """
    )
    return EvidenceSupportSchemaReceipt()


def upsert_source_evidence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibres: Sequence[PackedSentenceFibre],
) -> dict[bytes, int]:
    """Persist full evidence identities and fail closed on coordinate disagreement."""

    rows = tuple(row for fibre in fibres for row in source_evidence_rows(fibre))
    for row in rows:
        cursor.execute(
            """
            INSERT INTO execution.semantic_source_token_evidence
                (evidence_digest, run_ref, document_ref, sentence_digest,
                 token_ordinal, start_char, end_char, start_byte, end_byte)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (evidence_digest) DO NOTHING
            """,
            (
                row.evidence_digest,
                run_ref,
                document_ref,
                row.sentence_digest,
                row.token_ordinal,
                row.start_char,
                row.end_char,
                row.start_byte,
                row.end_byte,
            ),
        )
    if not rows:
        return {}
    digests = [row.evidence_digest for row in rows]
    cursor.execute(
        """
        SELECT evidence_id, evidence_digest, run_ref, document_ref, sentence_digest,
               token_ordinal, start_char, end_char, start_byte, end_byte
          FROM execution.semantic_source_token_evidence
         WHERE evidence_digest = ANY(%s)
        """,
        (digests,),
    )
    expected = {row.evidence_digest: row for row in rows}
    result: dict[bytes, int] = {}
    for db_row in cursor.fetchall():
        digest = bytes(db_row[1])
        row = expected.get(digest)
        if row is None:
            raise RuntimeError("source-evidence lookup returned an unexpected digest")
        observed = (
            str(db_row[2]),
            str(db_row[3]),
            bytes(db_row[4]),
            int(db_row[5]),
            int(db_row[6]),
            int(db_row[7]),
            int(db_row[8]),
            int(db_row[9]),
        )
        wanted = (
            run_ref,
            document_ref,
            row.sentence_digest,
            row.token_ordinal,
            row.start_char,
            row.end_char,
            row.start_byte,
            row.end_byte,
        )
        if observed != wanted:
            raise RuntimeError(
                "stable source-evidence digest collided with different source coordinates"
            )
        result[digest] = int(db_row[0])
    if set(result) != set(expected):
        raise RuntimeError("source-evidence persistence did not return the complete digest set")
    return result


__all__ = [
    "EvidenceSupportSchemaReceipt",
    "SourceEvidenceRow",
    "ensure_source_evidence_support_schema",
    "source_evidence_rows",
    "upsert_source_evidence",
]
