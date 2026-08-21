"""Execution-only hot-path projection for strict numeric parser persistence.

The strict parser producer owns one complete bounded partition fibre before its
first authority write. The hot path therefore keeps producer-known structure
intact across the PostgreSQL boundary instead of throwing it away and asking row
triggers to reconstruct or re-prove it.

Migration 175 writes final token/head identity on first admission. Migration 176
certifies the bounded numeric symbol/origin reference fibre once. This layer now
also separates *fresh authority admission* from *replay/conflict verification*:
PostgreSQL ``RETURNING`` is the exact witness that a row was newly admitted by
the current INSERT, while only token refs absent from RETURNING are reread and
proved equal to the producer row. Fresh-only partitions therefore perform no
persistent token-id allocation readback and no post-insert head-parity reread.

A rare mixed fresh/replay partition is handled without weakening correctness:
preallocated ids are replaced by the existing replay ids in the final dependency
map, and only fresh rows whose heads cross into that replay fibre are repaired.
Generic writers, legacy textual parser-symbol references, sentence/run/partition
references, morph sets and self-head integrity remain fail-closed.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from typing import Any, Iterable, Sequence


_INSTALL_MARKER = "_numeric_parser_projection_hot_path_installed"
_SETWISE_HEADS_READY: ContextVar[bool] = ContextVar(
    "sensiblaw_setwise_numeric_heads_ready", default=False
)
_SYMBOL_REFERENCE_COLUMNS = (
    "orth_symbol_id",
    "lemma_symbol_id",
    "pos_symbol_id",
    "tag_symbol_id",
    "dependency_symbol_id",
)
_ORIGIN_REFERENCE_COLUMNS = (
    "lemma_origin_id",
    "pos_origin_id",
    "tag_origin_id",
    "dependency_origin_id",
)
_RETURNING_COLUMNS = (
    "token_ref",
    "token_id",
    "sentence_id",
    "start_char",
    "end_char",
    "head_token_id",
)


def _allocate_provisional_token_ids(cursor: Any, *, count: int) -> tuple[int, ...]:
    """Allocate producer ids without rereading the persistent token authority."""

    if count < 1:
        return ()
    cursor.execute(
        """
        SELECT nextval(
                   pg_get_serial_sequence(
                       'execution.semantic_parser_token', 'token_id'
                   )::regclass
               )
          FROM generate_series(1, %s)
        """,
        (count,),
    )
    allocated = tuple(int(row[0]) for row in cursor.fetchall())
    if len(allocated) != count:
        raise RuntimeError("numeric token id allocator returned the wrong cardinality")
    return allocated


def _producer_certify_numeric_references(
    cursor: Any,
    *,
    columns: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
) -> None:
    """Prove and lock the bounded v2 symbol/origin reference fibre."""

    symbol_indexes = tuple(columns.index(name) for name in _SYMBOL_REFERENCE_COLUMNS)
    origin_indexes = tuple(columns.index(name) for name in _ORIGIN_REFERENCE_COLUMNS)

    requested_symbols = tuple(
        sorted(
            {
                int(row[index])
                for row in rows
                for index in symbol_indexes
                if row[index] is not None
            }
        )
    )
    requested_origins = tuple(
        sorted(
            {
                int(row[index])
                for row in rows
                for index in origin_indexes
                if row[index] is not None
            }
        )
    )

    if requested_symbols:
        cursor.execute(
            """
            SELECT symbol_id
              FROM execution.semantic_symbol
             WHERE symbol_id = ANY(%s)
             ORDER BY symbol_id
             FOR KEY SHARE
            """,
            (list(requested_symbols),),
        )
        observed_symbols = tuple(int(row[0]) for row in cursor.fetchall())
        if observed_symbols != requested_symbols:
            raise RuntimeError(
                "producer numeric token fibre contains a non-authoritative symbol id"
            )

    if requested_origins:
        cursor.execute(
            """
            SELECT origin_id
              FROM execution.semantic_parser_annotation_origin
             WHERE origin_id = ANY(%s)
             ORDER BY origin_id
             FOR KEY SHARE
            """,
            (list(requested_origins),),
        )
        observed_origins = tuple(int(row[0]) for row in cursor.fetchall())
        if observed_origins != requested_origins:
            raise RuntimeError(
                "producer numeric token fibre contains a non-authoritative annotation origin"
            )


def _set_producer_reference_capability(cursor: Any, enabled: bool) -> None:
    cursor.execute(
        "SELECT set_config("
        "'sensiblaw.producer_certified_numeric_references', %s, TRUE)",
        ("on" if enabled else "off",),
    )


def _set_producer_head_capability(cursor: Any, enabled: bool) -> None:
    cursor.execute(
        "SELECT set_config('sensiblaw.producer_complete_numeric_heads', %s, TRUE)",
        ("on" if enabled else "off",),
    )


def install_numeric_parser_projection_hot_path() -> bool:
    """Install exact producer-complete parser projections."""

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

        column_tuple = tuple(columns)
        sentence_ref_index = column_tuple.index("sentence_ref")
        token_ref_index = column_tuple.index("token_ref")
        start_char_index = column_tuple.index("start_char")
        end_char_index = column_tuple.index("end_char")
        head_start_index = column_tuple.index("head_start_char")
        head_end_index = column_tuple.index("head_end_char")

        sentence_refs = tuple(
            sorted({str(row[sentence_ref_index]) for row in materialized})
        )
        token_refs = tuple(str(row[token_ref_index]) for row in materialized)
        if len(set(token_refs)) != len(token_refs):
            raise RuntimeError("producer token fibre contains duplicate token refs")

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

        cursor.execute(
            """
            SELECT
                to_regprocedure(
                    'execution.resolve_numeric_parser_dependency_heads()'
                ) IS NOT NULL,
                to_regprocedure(
                    'execution.numeric_parser_setwise_head_integrity_ready()'
                ) IS NOT NULL,
                to_regprocedure(
                    'execution.numeric_parser_setwise_annotation_origin_ready()'
                ) IS NOT NULL,
                to_regprocedure(
                    'execution.numeric_parser_producer_complete_heads_ready()'
                ) IS NOT NULL,
                to_regprocedure(
                    'execution.numeric_parser_producer_certified_references_ready()'
                ) IS NOT NULL
            """
        )
        (
            has_setwise_head_projection,
            has_setwise_integrity_fence,
            has_setwise_annotation_origin,
            has_producer_complete_heads,
            has_producer_certified_references,
        ) = (bool(value) for value in cursor.fetchone())

        if has_setwise_integrity_fence and (
            has_setwise_head_projection or has_producer_complete_heads
        ):
            cursor.execute(
                "SELECT set_config("
                "'sensiblaw.setwise_numeric_head_integrity', 'on', TRUE)"
            )
        if has_setwise_annotation_origin:
            cursor.execute(
                "SELECT set_config("
                "'sensiblaw.setwise_numeric_annotation_origins', 'on', TRUE)"
            )
        if has_producer_certified_references:
            _producer_certify_numeric_references(
                cursor,
                columns=column_tuple,
                rows=materialized,
            )

        if has_producer_complete_heads:
            provisional_ids = _allocate_provisional_token_ids(
                cursor,
                count=len(token_refs),
            )
            provisional_id_by_ref = dict(
                zip(token_refs, provisional_ids, strict=True)
            )
            token_id_by_sentence_span: dict[tuple[int, int, int], int] = {}
            staged_rows: list[tuple[Any, ...]] = []
            staged_base: list[tuple[tuple[Any, ...], int, int]] = []

            for row in materialized:
                sentence_id = sentence_id_by_ref[str(row[sentence_ref_index])]
                token_ref = str(row[token_ref_index])
                token_id = provisional_id_by_ref[token_ref]
                span_key = (
                    sentence_id,
                    int(row[start_char_index]),
                    int(row[end_char_index]),
                )
                previous = token_id_by_sentence_span.setdefault(span_key, token_id)
                if previous != token_id:
                    raise RuntimeError(
                        "producer token fibre contains an ambiguous sentence-local span"
                    )
                staged_base.append((row, sentence_id, token_id))

            for row, sentence_id, token_id in staged_base:
                head_key = (
                    sentence_id,
                    int(row[head_start_index]),
                    int(row[head_end_index]),
                )
                head_token_id = token_id_by_sentence_span.get(head_key)
                if head_token_id is None:
                    raise projection.NumericHeadProjectionError(
                        "producer-complete dependency head is absent from its sentence"
                    )
                staged_rows.append((*row, sentence_id, token_id, head_token_id))

            insert_columns = (
                *column_tuple,
                "sentence_id",
                "token_id",
                "head_token_id",
            )
            _set_producer_head_capability(cursor, True)
            if has_producer_certified_references:
                _set_producer_reference_capability(cursor, True)
            try:
                returned = original_copy_rows(
                    cursor,
                    table=table,
                    columns=insert_columns,
                    rows=tuple(staged_rows),
                    returning=_RETURNING_COLUMNS,
                    **kwargs,
                )
            finally:
                if has_producer_certified_references:
                    _set_producer_reference_capability(cursor, False)
                _set_producer_head_capability(cursor, False)

            fresh_rows = tuple(returned or ())
            fresh_by_ref = {
                str(token_ref): (
                    int(token_id),
                    int(sentence_id),
                    int(start_char),
                    int(end_char),
                    int(head_token_id),
                )
                for (
                    token_ref,
                    token_id,
                    sentence_id,
                    start_char,
                    end_char,
                    head_token_id,
                ) in fresh_rows
            }
            if len(fresh_by_ref) != len(fresh_rows):
                raise RuntimeError("token INSERT RETURNING produced duplicate token refs")

            replay_refs = tuple(
                token_ref for token_ref in token_refs if token_ref not in fresh_by_ref
            )
            replay_by_ref: dict[str, tuple[Any, ...]] = {}
            if replay_refs:
                # Only conflict/replay rows require persistent equality evidence.
                replay_column_sql = ", ".join(insert_columns)
                cursor.execute(
                    f"SELECT {replay_column_sql} "
                    "FROM execution.semantic_parser_token "
                    "WHERE token_ref = ANY(%s) AND representation_version = 2 "
                    "ORDER BY token_ref FOR KEY SHARE",
                    (list(replay_refs),),
                )
                replay_by_ref = {
                    str(row[0]): tuple(row) for row in cursor.fetchall()
                }
                if tuple(sorted(replay_by_ref)) != tuple(sorted(replay_refs)):
                    raise RuntimeError(
                        "token replay fibre is missing an authoritative conflict row"
                    )

            final_id_by_ref = dict(provisional_id_by_ref)
            for token_ref, row in replay_by_ref.items():
                final_id_by_ref[token_ref] = int(row[-2])

            final_id_by_span: dict[tuple[int, int, int], int] = {}
            for row in materialized:
                token_ref = str(row[token_ref_index])
                sentence_id = sentence_id_by_ref[str(row[sentence_ref_index])]
                final_id_by_span[
                    (
                        sentence_id,
                        int(row[start_char_index]),
                        int(row[end_char_index]),
                    )
                ] = final_id_by_ref[token_ref]

            expected_by_ref: dict[str, tuple[Any, ...]] = {}
            head_repairs: list[tuple[int, int]] = []
            for row in materialized:
                token_ref = str(row[token_ref_index])
                sentence_id = sentence_id_by_ref[str(row[sentence_ref_index])]
                token_id = final_id_by_ref[token_ref]
                head_key = (
                    sentence_id,
                    int(row[head_start_index]),
                    int(row[head_end_index]),
                )
                final_head_id = final_id_by_span.get(head_key)
                if final_head_id is None:
                    raise projection.NumericHeadProjectionError(
                        "final replay-aware dependency head is absent from its sentence"
                    )
                expected_by_ref[token_ref] = (
                    *row,
                    sentence_id,
                    token_id,
                    final_head_id,
                )
                fresh = fresh_by_ref.get(token_ref)
                if fresh is not None and fresh[-1] != final_head_id:
                    head_repairs.append((final_head_id, token_id))

            for token_ref, persisted in replay_by_ref.items():
                expected = expected_by_ref[token_ref]
                if persisted != expected:
                    raise RuntimeError(
                        "numeric token replay conflicts with producer-complete authority"
                    )

            if head_repairs:
                # This path is proportional only to fresh->replay dependency edges.
                cursor.executemany(
                    """
                    UPDATE execution.semantic_parser_token
                       SET head_token_id = %s
                     WHERE token_id = %s
                    """,
                    tuple(head_repairs),
                )

            _SETWISE_HEADS_READY.set(True)
            return fresh_rows

        enriched_rows = tuple(
            (*row, sentence_id_by_ref[str(row[sentence_ref_index])])
            for row in materialized
        )
        if has_producer_certified_references:
            _set_producer_reference_capability(cursor, True)
        try:
            result = original_copy_rows(
                cursor,
                table=table,
                columns=(*column_tuple, "sentence_id"),
                rows=enriched_rows,
                **kwargs,
            )
        finally:
            if has_producer_certified_references:
                _set_producer_reference_capability(cursor, False)

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
        # Canonical parser validation still executes using the authority rows
        # loaded by the base writer. Only its physical UPDATE payload is skipped.
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
