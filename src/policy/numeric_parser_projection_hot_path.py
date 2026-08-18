"""Execution-only hot-path projection for strict numeric parser persistence.

The canonical numeric parser writer already COPYs one partition at a time. Its
legacy compatibility shape omitted ``sentence_id`` from token rows and relied on
migration-042's BEFORE ROW trigger to look the id up from ``sentence_ref`` for
every token. A large partition therefore turns one COPY into one indexed SELECT
per token.

This strategy enriches only the existing token COPY carrier. It resolves the
finite sentence-ref -> sentence-id map once on the same cursor, appends the exact
numeric id to every token row, and delegates to the unchanged COPY authority.
The migration-042 trigger remains installed for other writers and still validates
that a numeric token has a sentence identity; for this strict path it observes a
non-null id and performs no lookup.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Iterable, Sequence


_INSTALL_MARKER = "_numeric_parser_projection_hot_path_installed"


def install_numeric_parser_projection_hot_path() -> bool:
    """Install exact sentence-id enrichment on the existing parser COPY seam."""

    from src.storage.postgres import spacy_numeric_projection as projection

    if getattr(projection, _INSTALL_MARKER, False):
        return False

    original_copy_rows = projection._copy_rows

    @wraps(original_copy_rows)
    def copy_rows(
        cursor: Any,
        *,
        table: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[Any]],
        **kwargs: Any,
    ) -> Any:
        if table != "semantic_parser_token" or "sentence_id" in columns:
            return original_copy_rows(
                cursor,
                table=table,
                columns=columns,
                rows=rows,
                **kwargs,
            )

        materialized = tuple(tuple(row) for row in rows)
        if not materialized:
            return original_copy_rows(
                cursor,
                table=table,
                columns=columns,
                rows=materialized,
                **kwargs,
            )

        sentence_ref_index = tuple(columns).index("sentence_ref")
        sentence_refs = tuple(
            sorted({str(row[sentence_ref_index]) for row in materialized})
        )
        cursor.execute(
            """
            SELECT sentence_ref, sentence_id
              FROM execution.semantic_parser_sentence
             WHERE sentence_ref = ANY(%s)
               AND representation_version = 2
            """,
            (list(sentence_refs),),
        )
        sentence_id_by_ref = {
            str(sentence_ref): int(sentence_id)
            for sentence_ref, sentence_id in cursor.fetchall()
        }
        missing = tuple(
            ref for ref in sentence_refs if ref not in sentence_id_by_ref
        )
        if missing:
            raise RuntimeError(
                "numeric token COPY cannot resolve sentence ids for "
                f"{len(missing)} sentence refs"
            )

        enriched_rows = tuple(
            (*row, sentence_id_by_ref[str(row[sentence_ref_index])])
            for row in materialized
        )
        return original_copy_rows(
            cursor,
            table=table,
            columns=(*tuple(columns), "sentence_id"),
            rows=enriched_rows,
            **kwargs,
        )

    projection._copy_rows = copy_rows
    setattr(projection, _INSTALL_MARKER, True)
    return True


__all__ = ["install_numeric_parser_projection_hot_path"]
