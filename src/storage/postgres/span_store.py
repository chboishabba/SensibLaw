"""Relational persistence for source-anchored generic spans."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def persist_licensed_spans(
    cursor: Any,
    *,
    document_ref: str,
    mentions: Sequence[Mapping[str, Any]],
) -> None:
    for row in mentions:
        cursor.execute(
            """
            INSERT INTO corpus.span
                (span_ref, document_ref, start_char, end_char, start_token,
                 end_token, span_type_ref)
            VALUES (%s, %s, %s, %s, %s, %s, 'licensed_mention')
            ON CONFLICT (span_ref) DO NOTHING
            """,
            (
                str(row["mention_ref"]),
                document_ref,
                int(row["start_char"]),
                int(row["end_char"]),
                int(row["start_token"]),
                int(row["end_token"]),
            ),
        )


__all__ = ["persist_licensed_spans"]
