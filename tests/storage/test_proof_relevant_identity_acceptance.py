from __future__ import annotations

from hashlib import sha256
import os
from uuid import uuid4

import pytest

from src.storage.postgres.spacy_parser_model import connect


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for proof-relevant identity acceptance",
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


def _object(
    cursor: object,
    *,
    region_id: int,
    object_kind_symbol_id: int,
    head_symbol_id: int,
    marker: str,
) -> int:
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
            _digest("object", marker, region_id, head_symbol_id),
            region_id,
            object_kind_symbol_id,
            head_symbol_id,
            region_id,
        ),
    )
    return int(cursor.fetchone()[0])  # type: ignore[attr-defined]


def _factor(
    cursor: object,
    *,
    region_id: int,
    factor_type_symbol_id: int,
    predicate_symbol_id: int,
    role_symbol_id: int,
    object_id: int,
    marker: str,
) -> int:
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_factor
            (factor_digest, region_id, factor_type_symbol_id,
             predicate_symbol_id, scope_region_id, support_score)
        VALUES (%s, %s, %s, %s, %s, 10)
        RETURNING factor_id
        """,
        (
            _digest("factor", marker, region_id, predicate_symbol_id, object_id),
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
    return factor_id


def _actor_child(
    cursor: object,
    *,
    run_ref: str,
    document_ref: str,
    root_region_id: int,
    root_interface_id: int,
    sequence: int,
    start: int,
    person_symbol_id: int,
    head_symbol_id: int,
    role_symbol_id: int,
    factor_type_symbol_id: int,
    predicate_symbol_id: int,
    marker: str,
) -> tuple[int, int, int]:
    region_id = _region(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        kind=3,
        start=start,
        end=start + 80,
        sequence=sequence,
        parent_region_id=root_region_id,
    )
    interface_id = _interface(
        cursor,
        region_id=region_id,
        parent_interface_id=root_interface_id,
    )
    object_id = _object(
        cursor,
        region_id=region_id,
        object_kind_symbol_id=person_symbol_id,
        head_symbol_id=head_symbol_id,
        marker=f"{marker}:actor:{sequence}",
    )
    factor_id = _factor(
        cursor,
        region_id=region_id,
        factor_type_symbol_id=factor_type_symbol_id,
        predicate_symbol_id=predicate_symbol_id,
        role_symbol_id=role_symbol_id,
        object_id=object_id,
        marker=f"{marker}:actor-factor:{sequence}",
    )
    cursor.executemany(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, 0, 10)
        ON CONFLICT DO NOTHING
        """,
        (
            (interface_id, 1, 1, object_id, head_symbol_id),
            (interface_id, 2, 2, factor_id, factor_type_symbol_id),
        ),
    )
    return interface_id, object_id, factor_id


def _base_fixture(cursor: object, marker: str) -> dict[str, int | str]:
    run_ref = f"identity-acceptance-run:{marker}"
    document_ref = f"identity-acceptance-document:{marker}"
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_run
            (run_ref, document_ref, authority_backend, lifecycle)
        VALUES (%s, %s, 'pytest', 'running')
        """,
        (run_ref, document_ref),
    )
    person = _symbol(cursor, kind=14, text=f"person:{marker}")
    pronoun = _symbol(cursor, kind=14, text=f"pronoun:{marker}")
    reagan = _symbol(cursor, kind=2, text=f"ronald_reagan:{marker}")
    bush = _symbol(cursor, kind=2, text=f"george_bush:{marker}")
    he = _symbol(cursor, kind=2, text=f"he:{marker}")
    they = _symbol(cursor, kind=2, text=f"they:{marker}")
    addressee = _symbol(cursor, kind=12, text=f"addressee:{marker}")
    bearer = _symbol(cursor, kind=12, text=f"bearer:{marker}")
    notice = _symbol(cursor, kind=10, text=f"notice:{marker}")
    respond = _symbol(cursor, kind=11, text=f"must_respond:{marker}")
    observed_response = _symbol(cursor, kind=11, text=f"responded:{marker}")
    anaphor = _symbol(cursor, kind=13, text=f"anaphor_unresolved:{marker}")
    root_region_id = _region(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        kind=10,
        start=0,
        end=500,
        sequence=0,
        parent_region_id=None,
    )
    root_interface_id = _interface(
        cursor,
        region_id=root_region_id,
        parent_interface_id=None,
    )
    return {
        "run_ref": run_ref,
        "document_ref": document_ref,
        "person": person,
        "pronoun": pronoun,
        "reagan": reagan,
        "bush": bush,
        "he": he,
        "they": they,
        "addressee": addressee,
        "bearer": bearer,
        "notice": notice,
        "respond": respond,
        "observed_response": observed_response,
        "anaphor": anaphor,
        "root_region_id": root_region_id,
        "root_interface_id": root_interface_id,
    }


def _source_demand(
    cursor: object,
    *,
    fixture: dict[str, int | str],
    marker: str,
    surface_symbol_id: int,
    reference_mode: int,
    sequence: int,
    start: int,
) -> tuple[int, int, int, int]:
    region_id = _region(
        cursor,
        run_ref=str(fixture["run_ref"]),
        document_ref=str(fixture["document_ref"]),
        kind=3,
        start=start,
        end=start + 80,
        sequence=sequence,
        parent_region_id=int(fixture["root_region_id"]),
    )
    interface_id = _interface(
        cursor,
        region_id=region_id,
        parent_interface_id=int(fixture["root_interface_id"]),
    )
    source_object_id = _object(
        cursor,
        region_id=region_id,
        object_kind_symbol_id=int(fixture["pronoun"]),
        head_symbol_id=surface_symbol_id,
        marker=f"{marker}:source",
    )
    premise_factor_id = _factor(
        cursor,
        region_id=region_id,
        factor_type_symbol_id=int(fixture["notice"]),
        predicate_symbol_id=int(fixture["observed_response"]),
        role_symbol_id=int(fixture["bearer"]),
        object_id=source_object_id,
        marker=f"{marker}:source-factor",
    )
    cursor.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO execution.semantic_pnf_demand
            (demand_digest, source_interface_id, source_region_id,
             source_object_id, expected_target_kind,
             expected_factor_type_symbol_id,
             expected_object_kind_symbol_id,
             lexical_symbol_id, role_symbol_id,
             residual_type_symbol_id, recency_class,
             state, max_candidates, reference_mode)
        VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s, 4, 1, 16, %s)
        RETURNING demand_id
        """,
        (
            _digest("demand", marker),
            interface_id,
            region_id,
            source_object_id,
            int(fixture["notice"]),
            int(fixture["person"]),
            None,
            int(fixture["addressee"]),
            int(fixture["anaphor"]),
            reference_mode,
        ),
    )
    demand_id = int(cursor.fetchone()[0])  # type: ignore[attr-defined]
    return interface_id, source_object_id, premise_factor_id, demand_id


def _reduce(cursor: object, root_interface_id: int) -> None:
    cursor.execute(  # type: ignore[attr-defined]
        "SELECT * FROM execution.rebuild_numeric_pnf_parent_frontier(%s)",
        (root_interface_id,),
    )
    cursor.fetchone()  # type: ignore[attr-defined]


def _run_document_ids(cursor: object, run_ref: str, document_ref: str) -> tuple[int, int]:
    cursor.execute(  # type: ignore[attr-defined]
        "SELECT run_id FROM execution.semantic_pnf_run_identity WHERE run_ref = %s",
        (run_ref,),
    )
    run_id = int(cursor.fetchone()[0])  # type: ignore[attr-defined]
    cursor.execute(  # type: ignore[attr-defined]
        "SELECT document_id FROM execution.semantic_pnf_document_identity WHERE document_ref = %s",
        (document_ref,),
    )
    document_id = int(cursor.fetchone()[0])  # type: ignore[attr-defined]
    return run_id, document_id


def test_unique_identity_round_trip_is_proof_relevant_and_retractable() -> None:
    assert DATABASE_URL is not None
    marker = uuid4().hex
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            fixture = _base_fixture(cursor, marker)
            _, target_object_id, _ = _actor_child(
                cursor,
                run_ref=str(fixture["run_ref"]),
                document_ref=str(fixture["document_ref"]),
                root_region_id=int(fixture["root_region_id"]),
                root_interface_id=int(fixture["root_interface_id"]),
                sequence=0,
                start=0,
                person_symbol_id=int(fixture["person"]),
                head_symbol_id=int(fixture["reagan"]),
                role_symbol_id=int(fixture["addressee"]),
                factor_type_symbol_id=int(fixture["notice"]),
                predicate_symbol_id=int(fixture["respond"]),
                marker=marker,
            )
            _, source_object_id, premise_factor_id, demand_id = _source_demand(
                cursor,
                fixture=fixture,
                marker=marker,
                surface_symbol_id=int(fixture["he"]),
                reference_mode=1,
                sequence=1,
                start=120,
            )

            # G_E^(0): the local factor exists, but no entity fibre or Level-3
            # substitution exists before a resolved demand proof.
            cursor.execute(
                "SELECT count(*) FROM execution.semantic_pnf_factor WHERE factor_id = %s",
                (premise_factor_id,),
            )
            assert int(cursor.fetchone()[0]) == 1
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_projection
                 WHERE source_object_id = %s
                """,
                (source_object_id,),
            )
            assert int(cursor.fetchone()[0]) == 0

            _reduce(cursor, int(fixture["root_interface_id"]))
            cursor.execute(
                """
                SELECT outcome_state, candidate_count, selected_target_kind,
                       selected_target_id
                  FROM execution.semantic_pnf_frontier_resolution
                 WHERE demand_id = %s AND interface_id = %s
                """,
                (demand_id, int(fixture["root_interface_id"])),
            )
            outcome, candidate_count, target_kind, target_id = cursor.fetchone()
            assert (int(outcome), int(candidate_count), int(target_kind), int(target_id)) == (
                2,
                1,
                1,
                target_object_id,
            )

            run_id, document_id = _run_document_ids(
                cursor,
                str(fixture["run_ref"]),
                str(fixture["document_ref"]),
            )
            cursor.execute(
                "SELECT * FROM execution.refresh_numeric_pnf_semantic_derivations(%s, %s)",
                (run_id, document_id),
            )
            cursor.fetchone()

            # G_E^(1): pi : he => E exists and the premise factor is projected
            # into a separate Level-3 proposition retaining pi.
            cursor.execute(
                """
                SELECT projection.target_entity_id, projection.witness_ids,
                       entity.anchor_object_id, entity.authority_class
                  FROM execution.semantic_pnf_identity_projection AS projection
                  JOIN execution.semantic_pnf_canonical_entity AS entity
                    ON entity.entity_id = projection.target_entity_id
                 WHERE projection.source_object_id = %s
                   AND projection.authority_class = 2
                """,
                (source_object_id,),
            )
            entity_id, witness_ids, anchor_object_id, authority_class = cursor.fetchone()
            assert int(anchor_object_id) == target_object_id
            assert int(authority_class) == 2
            assert len(witness_ids) >= 1

            cursor.execute(
                """
                SELECT witness.witness_id, witness.candidate_count,
                       witness.authority_class, kind.witness_name,
                       admission.admission_state
                  FROM execution.semantic_pnf_identity_witness AS witness
                  JOIN execution.semantic_pnf_identity_witness_kind AS kind
                    ON kind.witness_kind = witness.witness_kind
                  JOIN execution.semantic_pnf_identity_witness_admission AS admission
                    ON admission.witness_id = witness.witness_id
                 WHERE witness.source_object_id = %s
                   AND witness.target_entity_id = %s
                   AND witness.demand_id = %s
                """,
                (source_object_id, int(entity_id), demand_id),
            )
            witness_id, witness_candidate_count, witness_authority, witness_kind, admission = (
                cursor.fetchone()
            )
            assert int(witness_candidate_count) == 1
            assert int(witness_authority) == int(authority_class)
            assert witness_kind == "anaphor_demand_resolution"
            assert int(admission) == 2

            cursor.execute(
                """
                SELECT derivation.derivation_id,
                       argument.identity_entity_id,
                       argument.identity_witness_ids
                  FROM execution.semantic_pnf_factor_derivation AS derivation
                  JOIN execution.semantic_pnf_factor_derivation_premise AS premise
                    ON premise.derivation_id = derivation.derivation_id
                   AND premise.premise_ordinal = 0
                  JOIN execution.semantic_pnf_factor_derivation_argument AS argument
                    ON argument.derivation_id = derivation.derivation_id
                 WHERE derivation.rule_ref = 'identity-substitution:v1'
                   AND premise.factor_id = %s
                   AND argument.source_object_id = %s
                """,
                (premise_factor_id, source_object_id),
            )
            derivation_id, derived_entity_id, derivation_witness_ids = cursor.fetchone()
            assert int(derived_entity_id) == int(entity_id)
            assert int(witness_id) in {int(value) for value in derivation_witness_ids}

            # The Level-1 premise is immutable and still present after projection.
            cursor.execute(
                "SELECT count(*) FROM execution.semantic_pnf_factor WHERE factor_id = %s",
                (premise_factor_id,),
            )
            assert int(cursor.fetchone()[0]) == 1

            # G_E^(1) -> G_E^(0): retract pi.  The immutable witness remains for
            # audit, but current projection and Level-3 derivation disappear.
            cursor.execute(
                "SELECT execution.retract_numeric_pnf_identity_witness(%s)",
                (int(witness_id),),
            )
            assert bool(cursor.fetchone()[0]) is True
            cursor.execute(
                """
                SELECT admission_state
                  FROM execution.semantic_pnf_identity_witness_admission
                 WHERE witness_id = %s
                """,
                (int(witness_id),),
            )
            assert int(cursor.fetchone()[0]) == 3
            cursor.execute(
                "SELECT count(*) FROM execution.semantic_pnf_identity_witness WHERE witness_id = %s",
                (int(witness_id),),
            )
            assert int(cursor.fetchone()[0]) == 1
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_projection
                 WHERE source_object_id = %s AND authority_class = 2
                """,
                (source_object_id,),
            )
            assert int(cursor.fetchone()[0]) == 0
            cursor.execute(
                """
                SELECT count(*)
                  FROM execution.semantic_pnf_factor_derivation AS derivation
                  JOIN execution.semantic_pnf_factor_derivation_premise AS premise
                    ON premise.derivation_id = derivation.derivation_id
                 WHERE derivation.rule_ref = 'identity-substitution:v1'
                   AND premise.factor_id = %s
                """,
                (premise_factor_id,),
            )
            assert int(cursor.fetchone()[0]) == 0
            cursor.execute(
                "SELECT count(*) FROM execution.semantic_pnf_factor WHERE factor_id = %s",
                (premise_factor_id,),
            )
            assert int(cursor.fetchone()[0]) == 1
            assert int(derivation_id) > 0
    finally:
        connection.rollback()
        connection.close()


def test_singular_two_candidate_reference_is_ambiguous_and_projects_nothing() -> None:
    assert DATABASE_URL is not None
    marker = uuid4().hex
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            fixture = _base_fixture(cursor, marker)
            for sequence, head_symbol_id in enumerate(
                (int(fixture["reagan"]), int(fixture["bush"]))
            ):
                _actor_child(
                    cursor,
                    run_ref=str(fixture["run_ref"]),
                    document_ref=str(fixture["document_ref"]),
                    root_region_id=int(fixture["root_region_id"]),
                    root_interface_id=int(fixture["root_interface_id"]),
                    sequence=sequence,
                    start=sequence * 90,
                    person_symbol_id=int(fixture["person"]),
                    head_symbol_id=head_symbol_id,
                    role_symbol_id=int(fixture["addressee"]),
                    factor_type_symbol_id=int(fixture["notice"]),
                    predicate_symbol_id=int(fixture["respond"]),
                    marker=marker,
                )
            _, source_object_id, _, demand_id = _source_demand(
                cursor,
                fixture=fixture,
                marker=marker,
                surface_symbol_id=int(fixture["he"]),
                reference_mode=1,
                sequence=2,
                start=220,
            )
            _reduce(cursor, int(fixture["root_interface_id"]))
            cursor.execute(
                """
                SELECT outcome_state, candidate_count, selected_target_id
                  FROM execution.semantic_pnf_frontier_resolution
                 WHERE demand_id = %s AND interface_id = %s
                """,
                (demand_id, int(fixture["root_interface_id"])),
            )
            outcome, candidate_count, selected_target = cursor.fetchone()
            assert int(outcome) == 3
            assert int(candidate_count) == 2
            assert selected_target is None

            run_id, document_id = _run_document_ids(
                cursor,
                str(fixture["run_ref"]),
                str(fixture["document_ref"]),
            )
            cursor.execute(
                "SELECT * FROM execution.refresh_numeric_pnf_semantic_derivations(%s, %s)",
                (run_id, document_id),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_projection
                 WHERE source_object_id = %s
                """,
                (source_object_id,),
            )
            assert int(cursor.fetchone()[0]) == 0
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_witness
                 WHERE source_object_id = %s AND demand_id = %s
                """,
                (source_object_id, demand_id),
            )
            assert int(cursor.fetchone()[0]) == 0
    finally:
        connection.rollback()
        connection.close()


def test_plural_and_generic_reference_modes_do_not_collapse_to_ambiguity_or_unique() -> None:
    assert DATABASE_URL is not None
    marker = uuid4().hex
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            fixture = _base_fixture(cursor, marker)
            for sequence, head_symbol_id in enumerate(
                (int(fixture["reagan"]), int(fixture["bush"]))
            ):
                _actor_child(
                    cursor,
                    run_ref=str(fixture["run_ref"]),
                    document_ref=str(fixture["document_ref"]),
                    root_region_id=int(fixture["root_region_id"]),
                    root_interface_id=int(fixture["root_interface_id"]),
                    sequence=sequence,
                    start=sequence * 90,
                    person_symbol_id=int(fixture["person"]),
                    head_symbol_id=head_symbol_id,
                    role_symbol_id=int(fixture["addressee"]),
                    factor_type_symbol_id=int(fixture["notice"]),
                    predicate_symbol_id=int(fixture["respond"]),
                    marker=marker,
                )

            _, plural_source, _, plural_demand = _source_demand(
                cursor,
                fixture=fixture,
                marker=f"{marker}:plural",
                surface_symbol_id=int(fixture["they"]),
                reference_mode=2,
                sequence=2,
                start=220,
            )
            _, generic_source, _, generic_demand = _source_demand(
                cursor,
                fixture=fixture,
                marker=f"{marker}:generic",
                surface_symbol_id=int(fixture["they"]),
                reference_mode=3,
                sequence=3,
                start=320,
            )
            _reduce(cursor, int(fixture["root_interface_id"]))

            cursor.execute(
                """
                SELECT demand_id, outcome_state, candidate_count,
                       selected_target_kind, selected_target_id
                  FROM execution.semantic_pnf_frontier_resolution
                 WHERE demand_id = ANY(%s) AND interface_id = %s
                 ORDER BY demand_id
                """,
                ([plural_demand, generic_demand], int(fixture["root_interface_id"])),
            )
            rows = {int(row[0]): row[1:] for row in cursor.fetchall()}
            plural = rows[plural_demand]
            generic = rows[generic_demand]
            assert int(plural[0]) == 5
            assert int(plural[1]) == 2
            assert plural[2] is None and plural[3] is None
            assert int(generic[0]) == 4
            assert generic[2] is None and generic[3] is None

            run_id, document_id = _run_document_ids(
                cursor,
                str(fixture["run_ref"]),
                str(fixture["document_ref"]),
            )
            cursor.execute(
                "SELECT * FROM execution.refresh_numeric_pnf_semantic_derivations(%s, %s)",
                (run_id, document_id),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_projection
                 WHERE source_object_id = ANY(%s)
                """,
                ([plural_source, generic_source],),
            )
            assert int(cursor.fetchone()[0]) == 0
            cursor.execute(
                """
                SELECT count(*) FROM execution.semantic_pnf_identity_witness
                 WHERE source_object_id = ANY(%s)
                   AND demand_id = ANY(%s)
                """,
                ([plural_source, generic_source], [plural_demand, generic_demand]),
            )
            assert int(cursor.fetchone()[0]) == 0
    finally:
        connection.rollback()
        connection.close()
