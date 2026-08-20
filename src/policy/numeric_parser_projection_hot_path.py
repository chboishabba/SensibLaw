"""Execution-only hot-path projection for strict numeric parser persistence.

The strict parser producer owns one complete bounded partition fibre before its
first authority write.  The hot path therefore keeps producer-known structure
intact across the PostgreSQL boundary instead of throwing it away and asking row
triggers to reconstruct or re-prove it.

Migration 175 assigns/reuses final token ids and resolves dependency heads before
COPY.  Migration 176 generalises the same principle to the five numeric semantic
symbol references and four annotation-origin references: the producer proves the
finite reference sets against their authority tables once, then advertises a
transaction-local capability so the generic set-wise fallback need not repeat the
same membership proof after INSERT.

Generic writers remain fail-closed.  Legacy textual parser-symbol references,
sentence/run/partition references, morph sets and self-head integrity are not
covered by the migration-176 capability.
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


def _allocate_missing_token_ids(
    cursor: Any,
    *,
    token_refs: tuple[str, ...],
) -> dict[str, int]:
    """Reuse existing ids and allocate final ids only for missing token refs."""

    cursor.execute(
        """
        SELECT token_ref, token_id
          FROM execution.semantic_parser_token
         WHERE token_ref = ANY(%s)
           AND representation_version = 2
        """,
        (list(token_refs),),
    )
    token_id_by_ref = {
        str(token_ref): int(token_id) for token_ref, token_id in cursor.fetchall()
    }
    missing = tuple(ref for ref in token_refs if ref not in token_id_by_ref)
    if missing:
        cursor.execute(
            """
            SELECT nextval(
                       pg_get_serial_sequence(
                           'execution.semantic_parser_token', 'token_id'
                       )::regclass
                   )
              FROM generate_series(1, %s)
            """,
            (len(missing),),
        )
        allocated = tuple(int(row[0]) for row in cursor.fetchall())
        if len(allocated) != len(missing):
            raise RuntimeError(
                "numeric token id allocator returned the wrong cardinality"
            )
        token_id_by_ref.update(zip(missing, allocated, strict=True))
    return token_id_by_ref


def _producer_certify_numeric_references(
    cursor: Any,
    *,
    columns: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
) -> None:
    """Prove the bounded v2 symbol/origin reference fibre against authority."""

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
            """,
            (list(requested_origins),),
        )
        observed_origins = tuple(int(row[0]) for row in cursor.fetchall())
        if observed_origins != requested_origins:
            raise RuntimeError(
                "producer numeric token fibre contains a non-authoritative annotation origin"
            )

    cursor.execute(
        "SELECT set_config("
        "'sensiblaw.producer_certified_numeric_references', 'on', TRUE)"
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

        # Detect physical capabilities before COPY because trigger branch
        # conditions are evaluated while the INSERT statement executes.
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
            token_id_by_ref = _allocate_missing_token_ids(
                cursor,
                token_refs=token_refs,
            )
            token_id_by_sentence_span: dict[tuple[int, int, int], int] = {}
            staged_rows: list[tuple[Any, ...]] = []
            staged_base: list[tuple[tuple[Any, ...], int, int]] = []

            for row in materialized:
                sentence_id = sentence_id_by_ref[str(row[sentence_ref_index])]
                token_ref = str(row[token_ref_index])
                token_id = token_id_by_ref[token_ref]
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

            cursor.execute(
                "SELECT set_config("
                "'sensiblaw.producer_complete_numeric_heads', 'on', TRUE)"
            )
            result = original_copy_rows(
                cursor,
                table=table,
                columns=(
                    *column_tuple,
                    "sentence_id",
                    "token_id",
                    "head_token_id",
                ),
                rows=tuple(staged_rows),
                **kwargs,
            )

            # ON CONFLICT remains the generic replay boundary. Before suppressing
            # the old UPDATE payload, prove that every authority row exposes the
            # producer-assigned token/head edge exactly.
            cursor.execute(
                """
                SELECT token_ref, token_id, head_token_id
                  FROM execution.semantic_parser_token
                 WHERE token_ref = ANY(%s)
                   AND representation_version = 2
                """,
                (list(token_refs),),
            )
            persisted = {
                str(token_ref): (int(token_id), int(head_token_id))
                for token_ref, token_id, head_token_id in cursor.fetchall()
                if head_token_id is not None
            }
            expected = {
                str(row[token_ref_index]): (
                    int(token_id),
                    int(head_token_id),
                )
                for row, token_id, head_token_id in (
                    (staged[: len(column_tuple)], staged[-2], staged[-1])
                    for staged in staged_rows
                )
            }
            if persisted != expected:
                raise RuntimeError(
                    "producer-complete numeric token authority failed exact head parity"
                )
            _SETWISE_HEADS_READY.set(True)
            return result

        enriched_rows = tuple(
            (*row, sentence_id_by_ref[str(row[sentence_ref_index])])
            for row in materialized
        )
        result = original_copy_rows(
            cursor,
            table=table,
            columns=(*column_tuple, "sentence_id"),
            rows=enriched_rows,
            **kwargs,
        )

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
