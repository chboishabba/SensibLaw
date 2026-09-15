"""PostgreSQL-backed source payment projection for Semantic Reader actions.

This module is intentionally read-only. PostgreSQL owns persisted source,
revision, canonical-text, and span coordinates; this projection does not turn
persistence into applicability, proposition support, or legal truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ReaderIntent(str, Enum):
    OPEN_SOURCE = "open_source"
    WHY = "why"


@dataclass(frozen=True)
class ReaderSourcePayment:
    source_revision_ref: str
    requested_span_ref: str
    document_ref: str | None = None
    media_type: str | None = None
    canonical_text_sha256: str | None = None
    authority_level: str | None = None
    span_ref: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    literal_span: str | None = None
    persisted_source_ready: bool = False
    exact_authority_span_paid: bool = False
    proposition_chain_paid: bool = False
    claim_truth_paid: bool = False


@dataclass(frozen=True)
class ReaderActionDecision:
    state: str
    residual_ref: str | None = None
    source_locator: tuple[str, str] | None = None


def load_reader_source_payment(
    cursor: Any,
    *,
    source_revision_ref: str,
    span_ref: str,
) -> ReaderSourcePayment:
    """Project one reader source payment from the PostgreSQL semantic spine.

    A compatible legal-source revision pays only retrieval readiness. The source
    action becomes executable only when the requested span is persisted on the
    same document and its character coordinates are valid for canonical text.
    """

    cursor.execute(
        """
        SELECT l.source_revision_ref,
               l.document_ref,
               l.media_type,
               l.canonical_text_sha256,
               convert_from(c.payload, 'UTF8') AS canonical_text,
               s.span_ref,
               s.start_char,
               s.end_char,
               s.span_type_ref,
               l.authority_level
        FROM legal_source_revision AS l
        JOIN corpus.document AS d
          ON d.document_ref = l.document_ref
        JOIN corpus.canonical_content AS c
          ON c.canonical_ref = d.canonical_ref
        LEFT JOIN corpus.span AS s
          ON s.document_ref = l.document_ref
         AND s.span_ref = %s
        WHERE l.source_revision_ref = %s
          AND l.compile_eligible = TRUE
        """,
        (span_ref, source_revision_ref),
    )
    row = cursor.fetchone()
    if row is None:
        return ReaderSourcePayment(
            source_revision_ref=source_revision_ref,
            requested_span_ref=span_ref,
        )

    canonical_text = str(row[4])
    persisted_span_ref = str(row[5]) if row[5] is not None else None
    start_char = int(row[6]) if row[6] is not None else None
    end_char = int(row[7]) if row[7] is not None else None
    valid_bounds = (
        persisted_span_ref == span_ref
        and start_char is not None
        and end_char is not None
        and 0 <= start_char < end_char <= len(canonical_text)
    )
    literal_span = canonical_text[start_char:end_char] if valid_bounds else None

    return ReaderSourcePayment(
        source_revision_ref=str(row[0]),
        requested_span_ref=span_ref,
        document_ref=str(row[1]),
        media_type=str(row[2]),
        canonical_text_sha256=str(row[3]),
        authority_level=str(row[9]) if len(row) > 9 and row[9] is not None else None,
        span_ref=persisted_span_ref,
        start_char=start_char,
        end_char=end_char,
        literal_span=literal_span,
        persisted_source_ready=True,
        exact_authority_span_paid=valid_bounds,
        proposition_chain_paid=False,
        claim_truth_paid=False,
    )


def compile_reader_intent(
    payment: ReaderSourcePayment,
    intent: ReaderIntent,
) -> ReaderActionDecision:
    """Lower a semantic reader intent without upgrading evidence authority."""

    if intent is ReaderIntent.OPEN_SOURCE:
        if payment.exact_authority_span_paid and payment.span_ref is not None:
            return ReaderActionDecision(
                state="execute",
                source_locator=(payment.source_revision_ref, payment.span_ref),
            )
        return ReaderActionDecision(
            state="defer",
            residual_ref="reader-residual:exact-authority-span",
        )

    if intent is ReaderIntent.WHY:
        if payment.proposition_chain_paid:
            return ReaderActionDecision(state="execute")
        return ReaderActionDecision(
            state="defer",
            residual_ref="reader-residual:detailed-proposition-chain",
        )

    raise ValueError(f"unsupported reader intent: {intent!r}")


__all__ = [
    "ReaderActionDecision",
    "ReaderIntent",
    "ReaderSourcePayment",
    "compile_reader_intent",
    "load_reader_source_payment",
]
