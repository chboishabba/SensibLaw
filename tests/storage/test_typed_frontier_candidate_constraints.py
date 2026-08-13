from __future__ import annotations

from hashlib import sha256
import os
from uuid import uuid4

import pytest

from src.storage.postgres.spacy_parser_model import connect


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for typed frontier constraints",
)


def _digest(*parts: object) -> bytes:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return sha256(payload).digest()


def _symbol(cursor: object, *, kind: int, text: str) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_symbol
            (kind_id, symbol_text, symbol_digest)
        VALUES (%s, %s, %s)
        ON CONFLICT (kind_id, symbol_text) DO UPDATE SET
            symbol_text = EXCLUDED.symbol_text
        RETURNING symbol_id
        """,
        (kind, text, _digest("symbol", kind, text)),
    )
    return int(cursor.fetchone()[0])  # type: ignore[attr-defined]


def _region(
    cursor: object,
    *,
    run_ref: str,
    document_ref: str,
    kind: int,
    start: int,
    end: int,
    parent_region_id: int | None,
) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_region
            (region_digest, run_ref, document_ref, region_kind,
             start_char, end_char, sequence_no, parent_region_id,
             closure_state, authored_boundary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 3, TRUE)
        RETURNING region_id
        """,
        (
            _digest("region", run_ref, kind, start, end),
            run_ref,
            document_ref,
            kind,
            start,
            end,
            start,
            parent_region_id,
        ),
    )
    return int(cursor.fetchone()[0])  # type: ignore[attr-defined]


def _interface(
    cursor: object,
    *,
    region_id: int,
    parent_interface_id: int | None,
) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_interface
            (interface_digest, region_id, parent_interface_id,
             closure_state, graph_revision)
        VALUES (%s, %s, %s, 3, 1)
        RETURNING interface_id
        """,
        (
            _digest("interface", region_id, parent_interface_id),
            region_id,
            parent_interface_id,
        ),
    )
    return int(cursor.fetchone()[0])  # type: ignore[attr-defined]


def _object(
    cursor: object,
    *,
    region_id: int,
    object_kind: int,
    head_symbol: int,
    marker: str,
) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_object
            (object_digest, region_id, object_kind_symbol_id,
             head_symbol_id, scope_region_id, promotion_score)
        VALUES (%s, %s, %s, %s, %s, 10)
        RETURNING object_id
        """,
        (
            _digest("object", marker),
            region_id,
            object_kind,
            head_symbol,
            region_id,
        ),
    )
    return int(cursor.fetchone()[0])  # type: ignore[attr-defined]


def _profile(
    cursor: object,
    *,
    interface_id: int,
    object_id: int,
    object_kind: int,
    role: int,
    factor_type: int,
    predicate: int,
    start: int,
    end: int,
) -> None:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_actor_profile
            (interface_id, object_id, object_kind_symbol_id,
             role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
             occurrence_count, first_start_char, last_end_char,
             promotion_score)
        VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, 10)
        """,
        (
            interface_id,
            object_id,
            object_kind,
            role,
            factor_type,
            predicate,
            start,
            end,
        ),
    )


def test_typed_constraints_filter_bounded_actor_candidates() -> None:
    assert DATABASE_URL is not None
    marker = uuid4().hex
    run_ref = f"typed-frontier-run:{marker}"
    document_ref = f"typed-frontier-document:{marker}"
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO execution.semantic_run
                    (run_ref, document_ref, authority_backend, lifecycle)
                VALUES (%s, %s, 'pytest', 'running')
                """,
                (run_ref, document_ref),
            )
            person = _symbol(cursor, kind=14, text=f"person:{marker}")
            applicant = _symbol(cursor, kind=2, text=f"applicant:{marker}")
            addressee = _symbol(cursor, kind=12, text=f"addressee:{marker}")
            observer = _symbol(cursor, kind=12, text=f"observer:{marker}")
            notice = _symbol(cursor, kind=10, text=f"notice:{marker}")
            respond = _symbol(cursor, kind=11, text=f"respond:{marker}")
            anaphor = _symbol(
                cursor,
                kind=13,
                text="anaphor_unresolved",
            )

            root_region = _region(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                kind=10,
                start=0,
                end=300,
                parent_region_id=None,
            )
            root_interface = _interface(
                cursor,
                region_id=root_region,
                parent_interface_id=None,
            )
            actor_region = _region(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                kind=3,
                start=0,
                end=90,
                parent_region_id=root_region,
            )
            first_object = _object(
                cursor,
                region_id=actor_region,
                object_kind=person,
                head_symbol=applicant,
                marker=f"first:{marker}",
            )
            second_object = _object(
                cursor,
                region_id=actor_region,
                object_kind=person,
                head_symbol=applicant,
                marker=f"second:{marker}",
            )
            _profile(
                cursor,
                interface_id=root_interface,
                object_id=first_object,
                object_kind=person,
                role=addressee,
                factor_type=notice,
                predicate=respond,
                start=0,
                end=40,
            )
            _profile(
                cursor,
                interface_id=root_interface,
                object_id=second_object,
                object_kind=person,
                role=observer,
                factor_type=notice,
                predicate=respond,
                start=0,
                end=40,
            )

            demand_region = _region(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                kind=3,
                start=100,
                end=190,
                parent_region_id=root_region,
            )
            demand_interface = _interface(
                cursor,
                region_id=demand_region,
                parent_interface_id=root_interface,
            )
            cursor.execute(
                """
                INSERT INTO execution.semantic_pnf_demand
                    (demand_digest, source_interface_id, source_region_id,
                     expected_target_kind,
                     expected_object_kind_symbol_id,
                     residual_type_symbol_id, recency_class,
                     state, max_candidates)
                VALUES (%s, %s, %s, 1, %s, %s, 4, 1, 16)
                RETURNING demand_id
                """,
                (
                    _digest("demand", marker),
                    demand_interface,
                    demand_region,
                    person,
                    anaphor,
                ),
            )
            demand_id = int(cursor.fetchone()[0])
            cursor.executemany(
                """
                INSERT INTO execution.semantic_pnf_demand_constraint
                    (demand_id, ordinal, key_kind, key_a, key_b,
                     required, polarity)
                VALUES (%s, %s, %s, %s, 0, TRUE, 1)
                ON CONFLICT DO NOTHING
                """,
                (
                    (demand_id, 10, 4, addressee),
                    (demand_id, 11, 1, notice),
                    (demand_id, 12, 3, respond),
                ),
            )

            cursor.executemany(
                """
                INSERT INTO execution.semantic_pnf_demand_candidate
                    (demand_id, ordinal, target_kind, target_id,
                     source_interface_id, ancestor_distance,
                     index_rank, candidate_score,
                     common_scope_interface_id, validation_state)
                VALUES (%s, %s, 1, %s, %s, 1, 0, 10, %s, 2)
                """,
                (
                    (
                        demand_id,
                        0,
                        first_object,
                        root_interface,
                        root_interface,
                    ),
                    (
                        demand_id,
                        1,
                        second_object,
                        root_interface,
                        root_interface,
                    ),
                ),
            )
            cursor.execute(
                """
                SELECT target_id
                  FROM execution.semantic_pnf_demand_candidate
                 WHERE demand_id = %s
                 ORDER BY target_id
                """,
                (demand_id,),
            )
            assert [int(row[0]) for row in cursor.fetchall()] == [first_object]

            cursor.execute(
                "DELETE FROM execution.semantic_pnf_demand_candidate "
                "WHERE demand_id = %s",
                (demand_id,),
            )
            cursor.execute(
                """
                INSERT INTO execution.semantic_pnf_demand_constraint
                    (demand_id, ordinal, key_kind, key_a, key_b,
                     required, polarity)
                VALUES (%s, 13, 3, %s, 0, TRUE, -1)
                """,
                (demand_id, respond),
            )
            cursor.execute(
                """
                INSERT INTO execution.semantic_pnf_demand_candidate
                    (demand_id, ordinal, target_kind, target_id,
                     source_interface_id, ancestor_distance,
                     index_rank, candidate_score,
                     common_scope_interface_id, validation_state)
                VALUES (%s, 0, 1, %s, %s, 1, 0, 10, %s, 2)
                """,
                (
                    demand_id,
                    first_object,
                    root_interface,
                    root_interface,
                ),
            )
            cursor.execute(
                """
                SELECT count(*)
                  FROM execution.semantic_pnf_demand_candidate
                 WHERE demand_id = %s
                """,
                (demand_id,),
            )
            assert int(cursor.fetchone()[0]) == 0
    finally:
        connection.rollback()
        connection.close()
