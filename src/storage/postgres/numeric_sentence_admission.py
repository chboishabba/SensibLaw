"""Set-wise PostgreSQL admission for one numeric sentence closure.

The semantic producer remains ``compose_numeric_sentence`` and every existing
object/factor/demand digest, trigger, fence, interface and proof producer remains
authoritative.  This module changes only the physical admission shape:

    bounded closure specs -> COPY temp rows -> set-wise upsert -> digest/id join

so sentence cost is not proportional to one client/server round trip per object,
factor, and demand.
"""

from __future__ import annotations

from typing import Any

from src.pnf.numeric_hyperfabric import (
    ClosureState,
    ExportKind,
    KeyKind,
    MdlProfile,
    TargetKind,
    WorkState,
    description_length,
    numeric_digest,
    promotion_score,
    should_promote,
)
from src.pnf.numeric_operator_composition import NumericSentenceClosure
from src.storage.postgres.numeric_hyperfabric_store import WorkLease


_OBJECT_STAGE = "tmp_numeric_sentence_object"
_FACTOR_STAGE = "tmp_numeric_sentence_factor"
_FACTOR_SUPPORT_STAGE = "tmp_numeric_sentence_factor_support"
_FACTOR_SLOT_STAGE = "tmp_numeric_sentence_factor_slot"
_DEMAND_STAGE = "tmp_numeric_sentence_demand"


def _create_stages(cursor: Any) -> None:
    cursor.execute(
        f"""
        CREATE TEMP TABLE {_OBJECT_STAGE} (
            ordinal INTEGER PRIMARY KEY,
            object_digest BYTEA NOT NULL,
            object_kind_symbol_id BIGINT NOT NULL,
            head_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            information_gain DOUBLE PRECISION NOT NULL,
            representation_cost DOUBLE PRECISION NOT NULL,
            ambiguity_cost DOUBLE PRECISION NOT NULL,
            promotion_score DOUBLE PRECISION NOT NULL,
            promoted BOOLEAN NOT NULL
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_STAGE} (
            ordinal INTEGER PRIMARY KEY,
            factor_digest BYTEA NOT NULL,
            factor_type_symbol_id BIGINT NOT NULL,
            predicate_symbol_id BIGINT NOT NULL,
            temporal_state SMALLINT NOT NULL,
            modal_state SMALLINT NOT NULL,
            support_score DOUBLE PRECISION NOT NULL
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_SUPPORT_STAGE} (
            factor_ordinal INTEGER NOT NULL,
            support_ordinal INTEGER NOT NULL,
            token_id BIGINT NOT NULL,
            PRIMARY KEY (factor_ordinal, support_ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_SLOT_STAGE} (
            factor_ordinal INTEGER NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            role_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            resolution_state SMALLINT NOT NULL,
            required BOOLEAN NOT NULL,
            PRIMARY KEY (factor_ordinal, slot_ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_DEMAND_STAGE} (
            ordinal INTEGER PRIMARY KEY,
            demand_digest BYTEA NOT NULL,
            expected_target_kind SMALLINT NOT NULL,
            expected_factor_type_symbol_id BIGINT,
            expected_object_kind_symbol_id BIGINT,
            lexical_symbol_id BIGINT,
            role_symbol_id BIGINT,
            residual_type_symbol_id BIGINT NOT NULL,
            recency_class SMALLINT NOT NULL,
            max_candidates INTEGER NOT NULL
        ) ON COMMIT DROP
        """
    )


def _copy_specs(
    cursor: Any,
    *,
    closure: NumericSentenceClosure,
    profile: MdlProfile,
) -> None:
    with cursor.copy(
        f"""COPY {_OBJECT_STAGE}
        (ordinal, object_digest, object_kind_symbol_id, head_symbol_id,
         source_token_id, information_gain, representation_cost,
         ambiguity_cost, promotion_score, promoted) FROM STDIN"""
    ) as copy:
        for ordinal, spec in enumerate(closure.objects):
            score = promotion_score(spec.promotion_evidence, profile)
            copy.write_row(
                (
                    ordinal,
                    spec.object_digest,
                    spec.object_kind_symbol_id,
                    spec.head_symbol_id,
                    spec.source_token_id,
                    spec.information_gain,
                    spec.representation_cost,
                    spec.ambiguity_cost,
                    score,
                    should_promote(spec.promotion_evidence, profile),
                )
            )

    # PostgreSQL accepts one COPY FROM STDIN stream per connection.  These
    # three bounded temp tables share a cursor, so stage them sequentially.
    with cursor.copy(
        f"""COPY {_FACTOR_STAGE}
        (ordinal, factor_digest, factor_type_symbol_id, predicate_symbol_id,
         temporal_state, modal_state, support_score) FROM STDIN"""
    ) as factor_copy:
        for factor_ordinal, spec in enumerate(closure.factors):
            factor_copy.write_row(
                (
                    factor_ordinal,
                    spec.factor_digest,
                    spec.factor_type_symbol_id,
                    spec.predicate_symbol_id,
                    spec.temporal_state,
                    spec.modal_state,
                    spec.support_score,
                )
            )

    with cursor.copy(
        f"""COPY {_FACTOR_SUPPORT_STAGE}
        (factor_ordinal, support_ordinal, token_id) FROM STDIN"""
    ) as support_copy:
        for factor_ordinal, spec in enumerate(closure.factors):
            for support_ordinal, token_id in enumerate(spec.support_token_ids):
                support_copy.write_row((factor_ordinal, support_ordinal, token_id))

    with cursor.copy(
        f"""COPY {_FACTOR_SLOT_STAGE}
        (factor_ordinal, slot_ordinal, role_symbol_id, source_token_id,
         resolution_state, required) FROM STDIN"""
    ) as slot_copy:
        for factor_ordinal, spec in enumerate(closure.factors):
            for slot_ordinal, slot in enumerate(spec.slots):
                slot_copy.write_row(
                    (
                        factor_ordinal,
                        slot_ordinal,
                        slot.role_symbol_id,
                        slot.source_token_id,
                        int(slot.resolution_state),
                        slot.required,
                    )
                )

    with cursor.copy(
        f"""COPY {_DEMAND_STAGE}
        (ordinal, demand_digest, expected_target_kind,
         expected_factor_type_symbol_id, expected_object_kind_symbol_id,
         lexical_symbol_id, role_symbol_id, residual_type_symbol_id,
         recency_class, max_candidates) FROM STDIN"""
    ) as copy:
        for ordinal, demand in enumerate(closure.demands):
            copy.write_row(
                (
                    ordinal,
                    demand.demand_digest,
                    int(demand.expected_target_kind),
                    demand.expected_factor_type_symbol_id,
                    demand.expected_object_kind_symbol_id,
                    demand.lexical_symbol_id,
                    demand.role_symbol_id,
                    demand.residual_type_symbol_id,
                    int(demand.recency_class),
                    demand.max_candidates,
                )
            )


def persist_sentence_closure_setwise(
    cursor: Any,
    *,
    lease: WorkLease,
    closure: NumericSentenceClosure,
    profile: MdlProfile,
) -> int:
    """Persist one already-composed closure with bounded set-wise admissions."""

    cursor.execute(
        """
        SELECT work.state_id, work.lease_token, work.lease_epoch,
               region.run_ref, region.document_ref,
               region.parent_region_id, region.graph_revision
          FROM execution.semantic_pnf_work_item AS work
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = work.region_id
         WHERE work.work_id = %s
         FOR UPDATE OF work, region
        """,
        (lease.work_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("leased numeric PNF work disappeared")
    if (
        int(row[0]) != int(WorkState.LEASED)
        or str(row[1]) != lease.lease_token
        or int(row[2]) != lease.lease_epoch
    ):
        raise RuntimeError("numeric PNF work fence changed")
    parent_region_id = int(row[5]) if row[5] is not None else None
    graph_revision = int(row[6]) + 1

    _create_stages(cursor)
    _copy_specs(cursor, closure=closure, profile=profile)

    # Objects: one upsert plus one digest->id join, regardless of object count.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_object
            (object_digest, region_id, object_kind_symbol_id,
             head_symbol_id, scope_region_id, promotion_level,
             information_gain, representation_cost, ambiguity_cost,
             promotion_score, active)
        SELECT stage.object_digest, %s, stage.object_kind_symbol_id,
               stage.head_symbol_id, %s, 0,
               stage.information_gain, stage.representation_cost,
               stage.ambiguity_cost, stage.promotion_score, TRUE
          FROM {_OBJECT_STAGE} AS stage
         ORDER BY stage.ordinal
        ON CONFLICT (object_digest) DO UPDATE SET
            promotion_score = EXCLUDED.promotion_score,
            active = TRUE
        """,
        (lease.region_id, lease.region_id),
    )
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_object_token_support
            (object_id, token_id, ordinal)
        SELECT object.object_id, stage.source_token_id, 0
          FROM {_OBJECT_STAGE} AS stage
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = stage.object_digest
        ON CONFLICT DO NOTHING
        """
    )
    cursor.execute(
        f"""
        SELECT stage.ordinal, object.object_id, stage.source_token_id,
               stage.head_symbol_id, stage.promotion_score, stage.promoted
          FROM {_OBJECT_STAGE} AS stage
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = stage.object_digest
         ORDER BY stage.ordinal
        """
    )
    object_rows = tuple(cursor.fetchall())
    object_id_by_token: dict[int, int] = {}
    promoted_object_ids: list[tuple[int, int, float]] = []
    for (
        _ordinal,
        object_id,
        source_token_id,
        head_symbol_id,
        score,
        promoted,
    ) in object_rows:
        # Preserve the previous Python dict semantics exactly: the final object
        # spec for a source token wins when factor slots map token -> object.
        object_id_by_token[int(source_token_id)] = int(object_id)
        if bool(promoted):
            promoted_object_ids.append(
                (int(object_id), int(head_symbol_id), float(score))
            )

    # Factors and their token support/slots are admitted in three set-wise SQL
    # statements after one COPY of the closure specification.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_factor
            (factor_digest, region_id, factor_type_symbol_id,
             predicate_symbol_id, scope_region_id,
             temporal_state, modal_state, promotion_level,
             support_score, active)
        SELECT stage.factor_digest, %s, stage.factor_type_symbol_id,
               stage.predicate_symbol_id, %s,
               stage.temporal_state, stage.modal_state, 0,
               stage.support_score, TRUE
          FROM {_FACTOR_STAGE} AS stage
         ORDER BY stage.ordinal
        ON CONFLICT (factor_digest) DO UPDATE SET active = TRUE
        """,
        (lease.region_id, lease.region_id),
    )
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_factor_token_support
            (factor_id, token_id, ordinal)
        SELECT factor.factor_id, support.token_id, support.support_ordinal
          FROM {_FACTOR_SUPPORT_STAGE} AS support
          JOIN {_FACTOR_STAGE} AS stage
            ON stage.ordinal = support.factor_ordinal
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
        ON CONFLICT DO NOTHING
        """
    )
    cursor.execute(
        f"""
        WITH object_choice AS (
            SELECT DISTINCT ON (source_token_id)
                   source_token_id, object_digest
              FROM {_OBJECT_STAGE}
             ORDER BY source_token_id, ordinal DESC
        )
        INSERT INTO execution.semantic_pnf_hyperedge
            (factor_id, slot_ordinal, role_symbol_id,
             object_id, resolution_state, required)
        SELECT factor.factor_id, slot.slot_ordinal, slot.role_symbol_id,
               object.object_id, slot.resolution_state, slot.required
          FROM {_FACTOR_SLOT_STAGE} AS slot
          JOIN {_FACTOR_STAGE} AS stage
            ON stage.ordinal = slot.factor_ordinal
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
          JOIN object_choice AS choice
            ON choice.source_token_id = slot.source_token_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = choice.object_digest
        ON CONFLICT DO NOTHING
        """
    )
    cursor.execute(
        f"""
        SELECT stage.ordinal, factor.factor_id,
               stage.factor_type_symbol_id, stage.predicate_symbol_id
          FROM {_FACTOR_STAGE} AS stage
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
         ORDER BY stage.ordinal
        """
    )
    factor_ids = [
        (int(factor_id), int(factor_type_id), int(predicate_id))
        for _ordinal, factor_id, factor_type_id, predicate_id in cursor.fetchall()
    ]

    # Demands are likewise admitted once. Existing INSERT triggers (including
    # occurrence provenance / incremental scheduling) still fire for each row.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_demand
            (demand_digest, source_region_id,
             expected_target_kind,
             expected_factor_type_symbol_id,
             expected_object_kind_symbol_id,
             lexical_symbol_id, role_symbol_id,
             residual_type_symbol_id, recency_class,
             state, max_candidates)
        SELECT stage.demand_digest, %s,
               stage.expected_target_kind,
               stage.expected_factor_type_symbol_id,
               stage.expected_object_kind_symbol_id,
               stage.lexical_symbol_id, stage.role_symbol_id,
               stage.residual_type_symbol_id, stage.recency_class,
               1, stage.max_candidates
          FROM {_DEMAND_STAGE} AS stage
         ORDER BY stage.ordinal
        ON CONFLICT (demand_digest) DO UPDATE SET
            state = LEAST(execution.semantic_pnf_demand.state, 1)
        """,
        (lease.region_id,),
    )
    cursor.execute(
        f"""
        SELECT stage.ordinal, demand.demand_id,
               stage.residual_type_symbol_id,
               stage.expected_factor_type_symbol_id,
               stage.lexical_symbol_id
          FROM {_DEMAND_STAGE} AS stage
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_digest = stage.demand_digest
         ORDER BY stage.ordinal
        """
    )
    demand_ids = [
        (
            int(demand_id),
            int(residual_id),
            int(factor_type_id) if factor_type_id is not None else None,
            int(lexical_id) if lexical_id is not None else None,
        )
        for _ordinal, demand_id, residual_id, factor_type_id, lexical_id in cursor.fetchall()
    ]

    measure = closure.measure
    interface_digest = numeric_digest(
        lease.region_id,
        graph_revision,
        tuple(object_id for object_id, _, _ in promoted_object_ids),
        tuple(factor_id for factor_id, _, _ in factor_ids),
        tuple(demand_id for demand_id, *_ in demand_ids),
    )
    parent_interface_id: int | None = None
    if parent_region_id is not None:
        cursor.execute(
            "SELECT interface_id FROM execution.semantic_pnf_interface WHERE region_id = %s",
            (parent_region_id,),
        )
        parent = cursor.fetchone()
        parent_interface_id = int(parent[0]) if parent else None
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_interface
            (interface_digest, region_id, parent_interface_id,
             closure_state, graph_revision,
             node_count, edge_count, alternative_count,
             unresolved_count, boundary_demand_weight,
             encoded_byte_count, rule_count, closure_rounds,
             query_cost_ns, promoted_object_count,
             interface_cardinality, hierarchy_cost, mdl_cost)
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (region_id) DO UPDATE SET
            interface_digest = EXCLUDED.interface_digest,
            closure_state = EXCLUDED.closure_state,
            graph_revision = EXCLUDED.graph_revision,
            node_count = EXCLUDED.node_count,
            edge_count = EXCLUDED.edge_count,
            unresolved_count = EXCLUDED.unresolved_count,
            boundary_demand_weight = EXCLUDED.boundary_demand_weight,
            encoded_byte_count = EXCLUDED.encoded_byte_count,
            rule_count = EXCLUDED.rule_count,
            closure_rounds = EXCLUDED.closure_rounds,
            promoted_object_count = EXCLUDED.promoted_object_count,
            interface_cardinality = EXCLUDED.interface_cardinality,
            mdl_cost = EXCLUDED.mdl_cost
        RETURNING interface_id
        """,
        (
            interface_digest,
            lease.region_id,
            parent_interface_id,
            int(ClosureState.LOCALLY_CLOSED),
            graph_revision,
            measure.node_count,
            measure.edge_count,
            measure.alternative_count,
            measure.unresolved_count,
            measure.boundary_demand_weight,
            measure.encoded_byte_count,
            measure.rule_count,
            measure.closure_rounds,
            measure.query_cost_ns,
            len(promoted_object_ids),
            len(promoted_object_ids) + len(factor_ids) + len(demand_ids),
            measure.hierarchy_cost,
            description_length(measure, profile),
        ),
    )
    interface_id = int(cursor.fetchone()[0])

    # These families are already batched by executemany and are bounded by one
    # sentence's promoted interface cardinality; they do not perform identity-
    # returning round trips and therefore remain as the existing cheap tail.
    cursor.executemany(
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        [
            (
                interface_id,
                int(ExportKind.OBJECT),
                int(TargetKind.OBJECT),
                object_id,
                head_symbol_id,
                rank,
                score,
            )
            for rank, (object_id, head_symbol_id, score) in enumerate(
                promoted_object_ids
            )
        ],
    )
    cursor.executemany(
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, %s, 0)
        ON CONFLICT DO NOTHING
        """,
        [
            (
                interface_id,
                int(ExportKind.FACTOR),
                int(TargetKind.FACTOR),
                factor_id,
                factor_type_id,
                rank,
            )
            for rank, (factor_id, factor_type_id, _predicate_id) in enumerate(
                factor_ids
            )
        ],
    )
    cursor.executemany(
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, residual_type_symbol_id,
             rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
        ON CONFLICT DO NOTHING
        """,
        [
            (
                interface_id,
                int(ExportKind.DEMAND),
                int(TargetKind.DEMAND),
                demand_id,
                lexical_id,
                residual_id,
                rank,
            )
            for rank, (
                demand_id,
                residual_id,
                _factor_type_id,
                lexical_id,
            ) in enumerate(demand_ids)
        ],
    )

    lookup_rows: list[tuple[int, int, int, int, int, int, int]] = []
    for rank, (object_id, head_symbol_id, _score) in enumerate(promoted_object_ids):
        lookup_rows.append(
            (
                interface_id,
                int(KeyKind.NORMALIZED_SYMBOL),
                head_symbol_id,
                0,
                int(TargetKind.OBJECT),
                object_id,
                rank,
            )
        )
    for rank, (factor_id, factor_type_id, predicate_id) in enumerate(factor_ids):
        lookup_rows.extend(
            (
                (
                    interface_id,
                    int(KeyKind.FACTOR_TYPE),
                    factor_type_id,
                    0,
                    int(TargetKind.FACTOR),
                    factor_id,
                    rank,
                ),
                (
                    interface_id,
                    int(KeyKind.NORMALIZED_SYMBOL),
                    predicate_id,
                    0,
                    int(TargetKind.FACTOR),
                    factor_id,
                    rank,
                ),
            )
        )
    for rank, (demand_id, residual_id, factor_type_id, lexical_id) in enumerate(
        demand_ids
    ):
        lookup_rows.append(
            (
                interface_id,
                int(KeyKind.RESIDUAL_TYPE),
                residual_id,
                factor_type_id or 0,
                int(TargetKind.DEMAND),
                demand_id,
                rank,
            )
        )
        if lexical_id:
            lookup_rows.append(
                (
                    interface_id,
                    int(KeyKind.NORMALIZED_SYMBOL),
                    lexical_id,
                    residual_id,
                    int(TargetKind.DEMAND),
                    demand_id,
                    rank,
                )
            )
    cursor.executemany(
        """
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        lookup_rows,
    )
    cursor.execute(
        "SELECT execution.rebuild_pnf_interface_ancestors(%s)", (interface_id,)
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s,
               graph_revision = %s,
               closed_at = CURRENT_TIMESTAMP
         WHERE region_id = %s
        """,
        (int(ClosureState.LOCALLY_CLOSED), graph_revision, lease.region_id),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = NULL,
               lease_token = NULL,
               lease_expires_at = NULL,
               completed_at = CURRENT_TIMESTAMP
         WHERE work_id = %s
           AND state_id = %s
           AND lease_token = %s
           AND lease_epoch = %s
        """,
        (
            int(WorkState.COMPLETED),
            lease.work_id,
            int(WorkState.LEASED),
            lease.lease_token,
            lease.lease_epoch,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("numeric PNF work fence changed during completion")
    return interface_id


__all__ = ["persist_sentence_closure_setwise"]
