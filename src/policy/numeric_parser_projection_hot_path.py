"""Execution-only hot-path projection for strict numeric parser persistence.

The canonical numeric parser writer already COPYs one partition at a time. Its
legacy compatibility shape had two row-amplifying tails:

* token COPY omitted ``sentence_id`` and relied on migration 042's BEFORE ROW
  trigger to look the id up from ``sentence_ref`` for every token;
* after COPY, Python validated dependency-head spans and then sent one UPDATE per
  token through ``executemany``.

This strategy preserves those semantic checks while changing only their physical
projection. It resolves the finite sentence-ref -> sentence-id map once and
includes the exact id in token COPY rows. When migration 150 is installed, the
same COPY also resolves all ``head_token_id`` values set-wise from the declared
sentence-local head spans. Python still runs the canonical
``_project_numeric_heads`` validation; only the redundant row-wise UPDATE payload
is suppressed after the database projection has been verified present.

Migration 042 remains installed for other writers, and absence of migration 150
fails safe to the original per-token head updates.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from typing import Any, Iterable, Sequence


_INSTALL_MARKER = "_numeric_parser_projection_hot_path_installed"
_SETWISE_HEADS_READY: ContextVar[bool] = ContextVar(
    "sensiblaw_setwise_numeric_heads_ready", default=False
)


def install_numeric_parser_projection_hot_path() -> bool:
    """Install exact sentence-id and dependency-head batch projection."""

    from src.storage.postgres import spacy_numeric_projection as projection

    if getattr(projection, _INSTALL_MARKER, False):
        return False

    original_copy_rows = projection._copy_rows
    original_project_heads = projection._project_numeric_heads

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
        token_ref_index = tuple(columns).index("token_ref")
        sentence_refs = tuple(
            sorted({str(row[sentence_ref_index]) for row in materialized})
        )
        token_refs = tuple(str(row[token_ref_index]) for row in materialized)
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
        missing = tuple(ref for ref in sentence_refs if ref not in sentence_id_by_ref)
        if missing:
            raise RuntimeError(
                "numeric token COPY cannot resolve sentence ids for "
                f"{len(missing)} sentence refs"
            )

        enriched_rows = tuple(
            (*row, sentence_id_by_ref[str(row[sentence_ref_index])])
            for row in materialized
        )
        result = original_copy_rows(
            cursor,
            table=table,
            columns=(*tuple(columns), "sentence_id"),
            rows=enriched_rows,
            **kwargs,
        )

        # Migration 150 is an optional physical optimization. Detect it on the
        # active database rather than assuming branch migration state. If it is
        # present, verify that the statement trigger actually filled every head
        # before suppressing Python's redundant UPDATE payload.
        cursor.execute(
            "SELECT to_regprocedure("
            "'execution.resolve_numeric_parser_dependency_heads()') IS NOT NULL"
        )
        has_setwise_head_projection = bool(cursor.fetchone()[0])
        if has_setwise_head_projection:
            cursor.execute(
                """
                SELECT count(*)
                  FROM execution.semantic_parser_token
                 WHERE token_ref = ANY(%s)
                   AND representation_version = 2
                   AND head_token_id IS NULL
                """,
                (list(token_refs),),
            )
            missing_heads = int(cursor.fetchone()[0])
            if missing_heads:
                raise RuntimeError(
                    "set-wise numeric dependency-head projection left "
                    f"{missing_heads} token heads unresolved"
                )
        _SETWISE_HEADS_READY.set(has_setwise_head_projection)
        return result

    @wraps(original_project_heads)
    def project_heads(*args: Any, **kwargs: Any):
        # Always execute the canonical parser-specific validation. It checks
        # explicit root self-heads, non-root self-resolution and missing heads.
        # Only the physical UPDATE tuples become unnecessary under migration 150.
        updates = original_project_heads(*args, **kwargs)
        if _SETWISE_HEADS_READY.get():
            _SETWISE_HEADS_READY.set(False)
            return ()
        return updates

    projection._copy_rows = copy_rows
    projection._project_numeric_heads = project_heads
    setattr(projection, _INSTALL_MARKER, True)
    return True


__all__ = ["install_numeric_parser_projection_hot_path"]
