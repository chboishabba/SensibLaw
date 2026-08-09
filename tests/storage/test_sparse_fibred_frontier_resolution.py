from __future__ import annotations

from hashlib import sha256
import os
from uuid import uuid4

import pytest

from src.storage.postgres.spacy_parser_model import connect


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL frontier resolution",
)


def _digest(*parts: object) -> bytes:
    return sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()


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
    sequence: int,
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
            _digest("region", run_ref, document_ref, kind, start, end),
            run_ref,
            document_ref,
            kind,
            start,
            end,
            sequence,
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


def _actor_child(
    cursor: object,
    *,
    run_ref: str,
    document_ref: str,
    root_region_id: int,
    root_interface_id: int,
    sequence: int,
    start: int,
    object_kind_symbol_id: int,
    head_symbol_id: int,
    role_symbol_id: int,
    factor_type_symbol_id: int,
    predicate_symbol_id: int,
) -> tuple[int, int, int]:
    region_id = _region(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        kind=3,
        start=start,
        end=start + 90,
        sequence=sequence,
        parent_region_id=root_region_id,
    )
    interface_id = _interface(
        cursor,
        region_id=region_id,
        parent_interface_id=root_interface_id,
    )
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_object
            (object_digest, region_id, object_kind_symbol_id,
             head_symbol_id, scope_region_id,
             information_gain, representation_cost,
             ambiguity_cost, promotion_score)
        VALUES (%s, %s, %s, %s, %s, 10, 1, 0, 10)
        RETURNING object_id
        """,
        (
            _digest("object", region_id, sequence),
            region_id,
            object_kind_symbol_id,
            head_symbol_id,
            region_id,
        ),
    )
    object_id = int(cursor.fetchone()[0])  # type: ignore[attr-defined]
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_factor
            (factor_digest, region_id, factor_type_symbol_id,
             predicate_symbol_id, scope_region_id, support_score)
        VALUES (%s, %s, %s, %s, %s, 10)
        RETURNING factor_id
        """,
        (
            _digest("factor", region_id, sequence),
            region_id,
            factor_type_symbol_id,
            predicate_symbol_id,
            region_id,
        ),
    )
    factor_id = int(cursor.fetchone()[0])  # type: ignore[attr-defined]
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_hyperedge
            (factor_id, slot_ordinal, role_symbol_id,
             object_id, resolution_state, required)
        VALUES (%s, 0, %s, %s, 2, TRUE)
        """,
        (factor_id, role_symbol_id, object_id),
    )
    cursor.executemany(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, 0, 10)
        """,
        (
            (interface_id, 1, 1, object_id, head_symbol_id),
            (interface_id, 2, 2, factor_id, factor_type_symbol_id),
        ),
    )
    cursor.executemany(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        VALUES (%s, %s, %s, 0, %s, %s, 0)
        """,
        (
            (interface_id, 2, object_kind_symbol_id, 1, object_id),
            (interface_id, 3, head_symbol_id, 1, object_id),
            (interface_id, 1, factor_type_symbol_id, 2, factor_id),
            (interface_id, 3, predicate_symbol_id, 2, factor_id),
        ),
    )
    return interface_id, object_id, factor_id


def _outcome(cursor: object, *, demand_id: int, interface_id: int) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        SELECT outcome_state
          FROM execution.semantic_pnf_frontier_resolution
         WHERE demand_id = %s AND interface_id = %s
        """,
        (demand_id, interface_id),
    )
    row = cursor.fetchone()  # type: ignore[attr-defined]
    assert row is not None
    return int(row[0])


def test_actor_hole_resolves_uniquely_then_preserves_ambiguity() -> None:
    assert DATABASE_URL is not None
    marker = uuid4().hex
    run_ref = f"sparse-frontier-run:{marker}"
    document_ref = f"sparse-frontier-document:{marker}"
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
            notice = _symbol(cursor, kind=10, text=f"notice:{marker}")
            must_respond = _symbol(
                cursor,
                kind=11,
                text=f"must_respond:{marker}",
            )
            anaphor = _symbol(
                cursor,
                kind=13,
                text="anaphor_unresolved",
            )
            you_surface = _symbol(cursor, kind=2, text=f"you:{marker}")
            unrelated_role = _symbol(
                cursor,
                kind=12,
                text=f"unrelated_role:{marker}",
            )

            root_region_id = _region(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                kind=10,
                start=0,
                end=400,
                sequence=0,
                parent_region_id=None,
            )
            root_interface_id = _interface(
                cursor,
                region_id=root_region_id,
                parent_interface_id=None,
            )
            _, first_actor_id, _ = _actor_child(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                root_region_id=root_region_id,
                root_interface_id=root_interface_id,
                sequence=0,
                start=0,
                object_kind_symbol_id=person,
                head_symbol_id=applicant,
                role_symbol_id=addressee,
                factor_type_symbol_id=notice,
                predicate_symbol_id=must_respond,
            )
            demand_region_id = _region(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                kind=3,
                start=100,
                end=190,
                sequence=1,
                parent_region_id=root_region_id,
            )
            demand_interface_id = _interface(
                cursor,
                region_id=demand_region_id,
                parent_interface_id=root_interface_id,
            )
            cursor.execute(
                """
                INSERT INTO execution.semantic_pnf_demand
                    (demand_digest, source_interface_id, source_region_id,
                     expected_target_kind,
                     expected_factor_type_symbol_id,
                     expected_object_kind_symbol_id,
                     lexical_symbol_id, role_symbol_id,
                     residual_type_symbol_id, recency_class,
                     state, max_candidates)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, 4, 1, 16)
                RETURNING demand_id,
                          lexical_symbol_id,
                          surface_lexical_symbol_id
                """,
                (
                    _digest("demand", marker),
                    demand_interface_id,
                    demand_region_id,
                    notice,
                    person,
                    you_surface,
                    addressee,
                    anaphor,
                ),
            )
            demand_id, identity_lexical, surface_lexical = cursor.fetchone()
            demand_id = int(demand_id)
            assert identity_lexical is None
            assert int(surface_lexical) == you_surface

            cursor.execute(
                """
                SELECT *
                  FROM execution.rebuild_numeric_pnf_parent_frontier(%s)
                """,
                (root_interface_id,),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT state, resolved_target_kind, resolved_target_id,
                       candidate_count
                  FROM execution.semantic_pnf_demand
                 WHERE demand_id = %s
                """,
                (demand_id,),
            )
            state, target_kind, target_id, candidate_count = cursor.fetchone()
            assert (int(state), int(target_kind), int(target_id)) == (
                2,
                1,
                first_actor_id,
            )
            assert int(candidate_count) == 1
            assert _outcome(
                cursor,
                demand_id=demand_id,
                interface_id=root_interface_id,
            ) == 2
            cursor.execute(
                """
                SELECT count(*)
                  FROM execution.semantic_pnf_interface_export
                 WHERE interface_id = %s
                   AND target_kind = 3
                   AND target_id = %s
                """,
                (root_interface_id, demand_id),
            )
            assert int(cursor.fetchone()[0]) == 0

            _actor_child(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                root_region_id=root_region_id,
                root_interface_id=root_interface_id,
                sequence=2,
                start=200,
                object_kind_symbol_id=person,
                head_symbol_id=applicant,
                role_symbol_id=addressee,
                factor_type_symbol_id=notice,
                predicate_symbol_id=must_respond,
            )
            cursor.execute(
                """
                UPDATE execution.semantic_pnf_demand
                   SET state = 1,
                       resolved_target_kind = NULL,
                       resolved_target_id = NULL,
                       candidate_count = 0
                 WHERE demand_id = %s
                """,
                (demand_id,),
            )
            cursor.execute(
                """
                SELECT *
                  FROM execution.rebuild_numeric_pnf_parent_frontier(%s)
                """,
                (root_interface_id,),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT state, resolved_target_id, candidate_count
                  FROM execution.semantic_pnf_demand
                 WHERE demand_id = %s
                """,
                (demand_id,),
            )
            state, target_id, candidate_count = cursor.fetchone()
            assert int(state) == 1
            assert target_id is None
            assert int(candidate_count) == 2
            assert _outcome(
                cursor,
                demand_id=demand_id,
                interface_id=root_interface_id,
            ) == 3

            cursor.execute(
                """
                UPDATE execution.semantic_pnf_demand
                   SET role_symbol_id = %s,
                       state = 1,
                       resolved_target_kind = NULL,
                       resolved_target_id = NULL,
                       candidate_count = 0
                 WHERE demand_id = %s
                """,
                (unrelated_role, demand_id),
            )
            cursor.execute(
                """
                SELECT *
                  FROM execution.rebuild_numeric_pnf_parent_frontier(%s)
                """,
                (root_interface_id,),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT state, resolved_target_id, candidate_count
                  FROM execution.semantic_pnf_demand
                 WHERE demand_id = %s
                """,
                (demand_id,),
            )
            state, target_id, candidate_count = cursor.fetchone()
            assert int(state) == 3
            assert target_id is None
            assert int(candidate_count) == 0
            assert _outcome(
                cursor,
                demand_id=demand_id,
                interface_id=root_interface_id,
            ) == 7

            cursor.execute(
                "SELECT execution.refresh_pnf_global_lookup(%s, %s)",
                (run_ref, document_ref),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*),
                       count(*) FILTER (
                           WHERE interface_id <> %s
                       )
                  FROM execution.semantic_pnf_global_lookup
                 WHERE run_ref = %s AND document_ref = %s
                """,
                (root_interface_id, run_ref, document_ref),
            )
            row_count, non_root_count = cursor.fetchone()
            assert int(row_count) > 0
            assert int(non_root_count) == 0
    finally:
        connection.rollback()
        connection.close()
