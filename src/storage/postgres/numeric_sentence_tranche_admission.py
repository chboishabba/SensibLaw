"""Fixed-family PostgreSQL authority admission for a sentence tranche.

E0 removed per-sentence lease/transaction/token-load orchestration, but still
invoked the one-sentence set-wise writer once for every closure.  This E0b owner
keeps sentence semantics independent while making persistence fixed-per-family:

    composed sentence closures
        -> five tranche-keyed COPY streams
        -> set-wise object/factor/demand admission
        -> grouped exact interface identity materialization
        -> set-wise export/lookup/region/work publication

The semantic producer remains ``compose_numeric_sentence``.  Existing digests,
promotion rules, demand triggers, authority tables, and work fences remain the
semantic authority.  This module only changes physical grouping.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence

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


_OBJECT_STAGE = "tmp_numeric_sentence_tranche_object"
_FACTOR_STAGE = "tmp_numeric_sentence_tranche_factor"
_FACTOR_SUPPORT_STAGE = "tmp_numeric_sentence_tranche_factor_support"
_FACTOR_SLOT_STAGE = "tmp_numeric_sentence_tranche_factor_slot"
_DEMAND_STAGE = "tmp_numeric_sentence_tranche_demand"
_INTERFACE_STAGE = "tmp_numeric_sentence_tranche_interface"


@dataclass(frozen=True, slots=True)
class SentenceTrancheAdmissionReceipt:
    sentence_count: int
    copy_stream_count: int
    family_statement_count: int
    interface_identity_query_count: int
    per_sentence_stage_create_count: int
    per_sentence_family_statement_count: int


def _create_tranche_stages(cursor: Any) -> None:
    cursor.execute(
        f"""
        CREATE TEMP TABLE {_OBJECT_STAGE} (
            region_id BIGINT NOT NULL,
            ordinal INTEGER NOT NULL,
            object_digest BYTEA NOT NULL,
            object_kind_symbol_id BIGINT NOT NULL,
            head_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            information_gain DOUBLE PRECISION NOT NULL,
            representation_cost DOUBLE PRECISION NOT NULL,
            ambiguity_cost DOUBLE PRECISION NOT NULL,
            promotion_score DOUBLE PRECISION NOT NULL,
            promoted BOOLEAN NOT NULL,
            PRIMARY KEY (region_id, ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_STAGE} (
            region_id BIGINT NOT NULL,
            ordinal INTEGER NOT NULL,
            factor_digest BYTEA NOT NULL,
            factor_type_symbol_id BIGINT NOT NULL,
            predicate_symbol_id BIGINT NOT NULL,
            temporal_state SMALLINT NOT NULL,
            modal_state SMALLINT NOT NULL,
            support_score DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (region_id, ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_SUPPORT_STAGE} (
            region_id BIGINT NOT NULL,
            factor_ordinal INTEGER NOT NULL,
            support_ordinal INTEGER NOT NULL,
            token_id BIGINT NOT NULL,
            PRIMARY KEY (region_id, factor_ordinal, support_ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_FACTOR_SLOT_STAGE} (
            region_id BIGINT NOT NULL,
            factor_ordinal INTEGER NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            role_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            resolution_state SMALLINT NOT NULL,
            required BOOLEAN NOT NULL,
            PRIMARY KEY (region_id, factor_ordinal, slot_ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_DEMAND_STAGE} (
            region_id BIGINT NOT NULL,
            ordinal INTEGER NOT NULL,
            demand_digest BYTEA NOT NULL,
            expected_target_kind SMALLINT NOT NULL,
            expected_factor_type_symbol_id BIGINT,
            expected_object_kind_symbol_id BIGINT,
            lexical_symbol_id BIGINT,
            role_symbol_id BIGINT,
            residual_type_symbol_id BIGINT NOT NULL,
            recency_class SMALLINT NOT NULL,
            max_candidates INTEGER NOT NULL,
            PRIMARY KEY (region_id, ordinal)
        ) ON COMMIT DROP;
        CREATE TEMP TABLE {_INTERFACE_STAGE} (
            region_id BIGINT PRIMARY KEY,
            work_id BIGINT NOT NULL,
            lease_token TEXT NOT NULL,
            lease_epoch BIGINT NOT NULL,
            parent_region_id BIGINT,
            graph_revision BIGINT NOT NULL,
            interface_digest BYTEA NOT NULL,
            node_count BIGINT NOT NULL,
            edge_count BIGINT NOT NULL,
            alternative_count BIGINT NOT NULL,
            unresolved_count BIGINT NOT NULL,
            boundary_demand_weight DOUBLE PRECISION NOT NULL,
            encoded_byte_count BIGINT NOT NULL,
            rule_count BIGINT NOT NULL,
            closure_rounds BIGINT NOT NULL,
            query_cost_ns BIGINT NOT NULL,
            promoted_object_count BIGINT NOT NULL,
            interface_cardinality BIGINT NOT NULL,
            hierarchy_cost DOUBLE PRECISION NOT NULL,
            mdl_cost DOUBLE PRECISION NOT NULL
        ) ON COMMIT DROP
        """
    )


def _copy_tranche_specs(
    cursor: Any,
    *,
    admissions: Sequence[tuple[WorkLease, NumericSentenceClosure]],
    profile: MdlProfile,
) -> None:
    with cursor.copy(
        f"""COPY {_OBJECT_STAGE}
        (region_id, ordinal, object_digest, object_kind_symbol_id,
         head_symbol_id, source_token_id, information_gain,
         representation_cost, ambiguity_cost, promotion_score, promoted)
        FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            for ordinal, spec in enumerate(closure.objects):
                score = promotion_score(spec.promotion_evidence, profile)
                copy.write_row(
                    (
                        lease.region_id,
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

    with cursor.copy(
        f"""COPY {_FACTOR_STAGE}
        (region_id, ordinal, factor_digest, factor_type_symbol_id,
         predicate_symbol_id, temporal_state, modal_state, support_score)
        FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            for ordinal, spec in enumerate(closure.factors):
                copy.write_row(
                    (
                        lease.region_id,
                        ordinal,
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
        (region_id, factor_ordinal, support_ordinal, token_id) FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            for factor_ordinal, spec in enumerate(closure.factors):
                for support_ordinal, token_id in enumerate(spec.support_token_ids):
                    copy.write_row(
                        (lease.region_id, factor_ordinal, support_ordinal, token_id)
                    )

    with cursor.copy(
        f"""COPY {_FACTOR_SLOT_STAGE}
        (region_id, factor_ordinal, slot_ordinal, role_symbol_id,
         source_token_id, resolution_state, required) FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            for factor_ordinal, spec in enumerate(closure.factors):
                for slot_ordinal, slot in enumerate(spec.slots):
                    copy.write_row(
                        (
                            lease.region_id,
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
        (region_id, ordinal, demand_digest, expected_target_kind,
         expected_factor_type_symbol_id, expected_object_kind_symbol_id,
         lexical_symbol_id, role_symbol_id, residual_type_symbol_id,
         recency_class, max_candidates) FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            for ordinal, demand in enumerate(closure.demands):
                copy.write_row(
                    (
                        lease.region_id,
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


def _verify_fences(
    cursor: Any,
    admissions: Sequence[tuple[WorkLease, NumericSentenceClosure]],
) -> dict[int, tuple[int | None, int]]:
    leases = [lease for lease, _closure in admissions]
    work_ids = [lease.work_id for lease in leases]
    cursor.execute(
        """
        SELECT work.work_id, work.state_id, work.lease_token, work.lease_epoch,
               work.region_id, region.parent_region_id, region.graph_revision
          FROM execution.semantic_pnf_work_item AS work
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = work.region_id
         WHERE work.work_id = ANY(%s)
         ORDER BY work.work_id
         FOR UPDATE OF work, region
        """,
        (work_ids,),
    )
    rows = cursor.fetchall()
    if len(rows) != len(leases):
        raise RuntimeError("sentence tranche work fence set changed")
    expected = {lease.work_id: lease for lease in leases}
    region_state: dict[int, tuple[int | None, int]] = {}
    for row in rows:
        work_id = int(row[0])
        lease = expected.get(work_id)
        if lease is None:
            raise RuntimeError("sentence tranche returned an unexpected work fence")
        if (
            int(row[1]) != int(WorkState.LEASED)
            or str(row[2]) != lease.lease_token
            or int(row[3]) != lease.lease_epoch
            or int(row[4]) != lease.region_id
        ):
            raise RuntimeError("numeric PNF sentence tranche fence changed")
        region_state[lease.region_id] = (
            int(row[5]) if row[5] is not None else None,
            int(row[6]) + 1,
        )
    return region_state


def _materialize_ids(cursor: Any) -> tuple[
    dict[int, list[tuple[int, int, float]]],
    dict[int, list[tuple[int, int, int]]],
    dict[int, list[tuple[int, int, int | None, int | None]]],
]:
    promoted: dict[int, list[tuple[int, int, float]]] = defaultdict(list)
    cursor.execute(
        f"""
        SELECT stage.region_id, object.object_id,
               stage.head_symbol_id, stage.promotion_score
          FROM {_OBJECT_STAGE} AS stage
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = stage.object_digest
         WHERE stage.promoted
         ORDER BY stage.region_id, stage.ordinal
        """
    )
    for region_id, object_id, head_symbol_id, score in cursor.fetchall():
        promoted[int(region_id)].append(
            (int(object_id), int(head_symbol_id), float(score))
        )

    factors: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    cursor.execute(
        f"""
        SELECT stage.region_id, factor.factor_id,
               stage.factor_type_symbol_id, stage.predicate_symbol_id
          FROM {_FACTOR_STAGE} AS stage
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
         ORDER BY stage.region_id, stage.ordinal
        """
    )
    for region_id, factor_id, factor_type_id, predicate_id in cursor.fetchall():
        factors[int(region_id)].append(
            (int(factor_id), int(factor_type_id), int(predicate_id))
        )

    demands: dict[int, list[tuple[int, int, int | None, int | None]]] = defaultdict(list)
    cursor.execute(
        f"""
        SELECT stage.region_id, demand.demand_id,
               stage.residual_type_symbol_id,
               stage.expected_factor_type_symbol_id,
               stage.lexical_symbol_id
          FROM {_DEMAND_STAGE} AS stage
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_digest = stage.demand_digest
         ORDER BY stage.region_id, stage.ordinal
        """
    )
    for region_id, demand_id, residual_id, factor_type_id, lexical_id in cursor.fetchall():
        demands[int(region_id)].append(
            (
                int(demand_id),
                int(residual_id),
                int(factor_type_id) if factor_type_id is not None else None,
                int(lexical_id) if lexical_id is not None else None,
            )
        )
    return promoted, factors, demands


def _copy_interface_stage(
    cursor: Any,
    *,
    admissions: Sequence[tuple[WorkLease, NumericSentenceClosure]],
    profile: MdlProfile,
    region_state: dict[int, tuple[int | None, int]],
    promoted: dict[int, list[tuple[int, int, float]]],
    factors: dict[int, list[tuple[int, int, int]]],
    demands: dict[int, list[tuple[int, int, int | None, int | None]]],
) -> None:
    with cursor.copy(
        f"""COPY {_INTERFACE_STAGE}
        (region_id, work_id, lease_token, lease_epoch, parent_region_id,
         graph_revision, interface_digest, node_count, edge_count,
         alternative_count, unresolved_count, boundary_demand_weight,
         encoded_byte_count, rule_count, closure_rounds, query_cost_ns,
         promoted_object_count, interface_cardinality, hierarchy_cost, mdl_cost)
        FROM STDIN"""
    ) as copy:
        for lease, closure in admissions:
            parent_region_id, graph_revision = region_state[lease.region_id]
            object_ids = promoted.get(lease.region_id, [])
            factor_ids = factors.get(lease.region_id, [])
            demand_ids = demands.get(lease.region_id, [])
            measure = closure.measure
            interface_digest = numeric_digest(
                lease.region_id,
                graph_revision,
                tuple(object_id for object_id, _head, _score in object_ids),
                tuple(factor_id for factor_id, _type, _predicate in factor_ids),
                tuple(demand_id for demand_id, *_rest in demand_ids),
            )
            copy.write_row(
                (
                    lease.region_id,
                    lease.work_id,
                    lease.lease_token,
                    lease.lease_epoch,
                    parent_region_id,
                    graph_revision,
                    interface_digest,
                    measure.node_count,
                    measure.edge_count,
                    measure.alternative_count,
                    measure.unresolved_count,
                    measure.boundary_demand_weight,
                    measure.encoded_byte_count,
                    measure.rule_count,
                    measure.closure_rounds,
                    measure.query_cost_ns,
                    len(object_ids),
                    len(object_ids) + len(factor_ids) + len(demand_ids),
                    measure.hierarchy_cost,
                    description_length(measure, profile),
                )
            )


def persist_sentence_tranche_setwise(
    cursor: Any,
    *,
    admissions: Sequence[tuple[WorkLease, NumericSentenceClosure]],
    profile: MdlProfile,
) -> SentenceTrancheAdmissionReceipt:
    """Persist an independent sentence tranche with fixed-per-family SQL work."""

    if not admissions:
        return SentenceTrancheAdmissionReceipt(0, 0, 0, 0, 0, 0)
    region_ids = [lease.region_id for lease, _closure in admissions]
    if len(set(region_ids)) != len(region_ids):
        raise ValueError("sentence tranche contains duplicate region ids")

    region_state = _verify_fences(cursor, admissions)
    _create_tranche_stages(cursor)
    _copy_tranche_specs(cursor, admissions=admissions, profile=profile)

    # Object family.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_object
            (object_digest, region_id, object_kind_symbol_id,
             head_symbol_id, scope_region_id, promotion_level,
             information_gain, representation_cost, ambiguity_cost,
             promotion_score, active)
        SELECT stage.object_digest, stage.region_id, stage.object_kind_symbol_id,
               stage.head_symbol_id, stage.region_id, 0,
               stage.information_gain, stage.representation_cost,
               stage.ambiguity_cost, stage.promotion_score, TRUE
          FROM {_OBJECT_STAGE} AS stage
         ORDER BY stage.region_id, stage.ordinal
        ON CONFLICT (object_digest) DO UPDATE SET
            promotion_score = EXCLUDED.promotion_score,
            active = TRUE
        """
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

    # Factor family.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_factor
            (factor_digest, region_id, factor_type_symbol_id,
             predicate_symbol_id, scope_region_id, temporal_state,
             modal_state, promotion_level, support_score, active)
        SELECT stage.factor_digest, stage.region_id, stage.factor_type_symbol_id,
               stage.predicate_symbol_id, stage.region_id,
               stage.temporal_state, stage.modal_state, 0,
               stage.support_score, TRUE
          FROM {_FACTOR_STAGE} AS stage
         ORDER BY stage.region_id, stage.ordinal
        ON CONFLICT (factor_digest) DO UPDATE SET active = TRUE
        """
    )
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_factor_token_support
            (factor_id, token_id, ordinal)
        SELECT factor.factor_id, support.token_id, support.support_ordinal
          FROM {_FACTOR_SUPPORT_STAGE} AS support
          JOIN {_FACTOR_STAGE} AS stage
            ON stage.region_id = support.region_id
           AND stage.ordinal = support.factor_ordinal
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
        ON CONFLICT DO NOTHING
        """
    )
    cursor.execute(
        f"""
        WITH object_choice AS (
            SELECT DISTINCT ON (region_id, source_token_id)
                   region_id, source_token_id, object_digest
              FROM {_OBJECT_STAGE}
             ORDER BY region_id, source_token_id, ordinal DESC
        )
        INSERT INTO execution.semantic_pnf_hyperedge
            (factor_id, slot_ordinal, role_symbol_id,
             object_id, resolution_state, required)
        SELECT factor.factor_id, slot.slot_ordinal, slot.role_symbol_id,
               object.object_id, slot.resolution_state, slot.required
          FROM {_FACTOR_SLOT_STAGE} AS slot
          JOIN {_FACTOR_STAGE} AS stage
            ON stage.region_id = slot.region_id
           AND stage.ordinal = slot.factor_ordinal
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
          JOIN object_choice AS choice
            ON choice.region_id = slot.region_id
           AND choice.source_token_id = slot.source_token_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = choice.object_digest
        ON CONFLICT DO NOTHING
        """
    )

    # Demand family. Existing row/statement triggers remain authoritative.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_demand
            (demand_digest, source_region_id, expected_target_kind,
             expected_factor_type_symbol_id, expected_object_kind_symbol_id,
             lexical_symbol_id, role_symbol_id, residual_type_symbol_id,
             recency_class, state, max_candidates)
        SELECT stage.demand_digest, stage.region_id, stage.expected_target_kind,
               stage.expected_factor_type_symbol_id,
               stage.expected_object_kind_symbol_id,
               stage.lexical_symbol_id, stage.role_symbol_id,
               stage.residual_type_symbol_id, stage.recency_class,
               1, stage.max_candidates
          FROM {_DEMAND_STAGE} AS stage
         ORDER BY stage.region_id, stage.ordinal
        ON CONFLICT (demand_digest) DO UPDATE SET
            state = LEAST(execution.semantic_pnf_demand.state, 1)
        """
    )

    promoted, factors, demands = _materialize_ids(cursor)
    _copy_interface_stage(
        cursor,
        admissions=admissions,
        profile=profile,
        region_state=region_state,
        promoted=promoted,
        factors=factors,
        demands=demands,
    )

    # Interface identities are exact Python numeric_digest results staged once;
    # parent interface ids are resolved set-wise at publication time.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_interface
            (interface_digest, region_id, parent_interface_id,
             closure_state, graph_revision, node_count, edge_count,
             alternative_count, unresolved_count, boundary_demand_weight,
             encoded_byte_count, rule_count, closure_rounds, query_cost_ns,
             promoted_object_count, interface_cardinality, hierarchy_cost, mdl_cost)
        SELECT stage.interface_digest,
               stage.region_id,
               parent.interface_id,
               {int(ClosureState.LOCALLY_CLOSED)},
               stage.graph_revision,
               stage.node_count, stage.edge_count, stage.alternative_count,
               stage.unresolved_count, stage.boundary_demand_weight,
               stage.encoded_byte_count, stage.rule_count, stage.closure_rounds,
               stage.query_cost_ns, stage.promoted_object_count,
               stage.interface_cardinality, stage.hierarchy_cost, stage.mdl_cost
          FROM {_INTERFACE_STAGE} AS stage
          LEFT JOIN execution.semantic_pnf_interface AS parent
            ON parent.region_id = stage.parent_region_id
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
        """
    )

    # All three export families in one statement, partitioning ranks by region.
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, role_symbol_id, residual_type_symbol_id,
             rank, promotion_score)
        SELECT interface.interface_id,
               {int(ExportKind.OBJECT)}, {int(TargetKind.OBJECT)},
               object.object_id, stage.head_symbol_id,
               NULL::BIGINT, NULL::BIGINT,
               row_number() OVER (
                   PARTITION BY stage.region_id ORDER BY stage.ordinal
               ) - 1,
               stage.promotion_score
          FROM {_OBJECT_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = stage.object_digest
         WHERE stage.promoted
        UNION ALL
        SELECT interface.interface_id,
               {int(ExportKind.FACTOR)}, {int(TargetKind.FACTOR)},
               factor.factor_id, stage.factor_type_symbol_id,
               NULL::BIGINT, NULL::BIGINT, stage.ordinal, 0
          FROM {_FACTOR_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
        UNION ALL
        SELECT interface.interface_id,
               {int(ExportKind.DEMAND)}, {int(TargetKind.DEMAND)},
               demand.demand_id, stage.lexical_symbol_id,
               NULL::BIGINT, stage.residual_type_symbol_id, stage.ordinal, 0
          FROM {_DEMAND_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_digest = stage.demand_digest
        ON CONFLICT DO NOTHING
        """
    )

    cursor.execute(
        f"""
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        SELECT interface.interface_id,
               {int(KeyKind.NORMALIZED_SYMBOL)}, stage.head_symbol_id, 0,
               {int(TargetKind.OBJECT)}, object.object_id,
               row_number() OVER (
                   PARTITION BY stage.region_id ORDER BY stage.ordinal
               ) - 1
          FROM {_OBJECT_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_digest = stage.object_digest
         WHERE stage.promoted
        UNION ALL
        SELECT interface.interface_id,
               {int(KeyKind.FACTOR_TYPE)}, stage.factor_type_symbol_id, 0,
               {int(TargetKind.FACTOR)}, factor.factor_id, stage.ordinal
          FROM {_FACTOR_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
        UNION ALL
        SELECT interface.interface_id,
               {int(KeyKind.NORMALIZED_SYMBOL)}, stage.predicate_symbol_id, 0,
               {int(TargetKind.FACTOR)}, factor.factor_id, stage.ordinal
          FROM {_FACTOR_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_digest = stage.factor_digest
        UNION ALL
        SELECT interface.interface_id,
               {int(KeyKind.RESIDUAL_TYPE)}, stage.residual_type_symbol_id,
               COALESCE(stage.expected_factor_type_symbol_id, 0),
               {int(TargetKind.DEMAND)}, demand.demand_id, stage.ordinal
          FROM {_DEMAND_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_digest = stage.demand_digest
        UNION ALL
        SELECT interface.interface_id,
               {int(KeyKind.NORMALIZED_SYMBOL)}, stage.lexical_symbol_id,
               stage.residual_type_symbol_id,
               {int(TargetKind.DEMAND)}, demand.demand_id, stage.ordinal
          FROM {_DEMAND_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_digest = stage.demand_digest
         WHERE stage.lexical_symbol_id IS NOT NULL
           AND stage.lexical_symbol_id <> 0
        ON CONFLICT DO NOTHING
        """
    )

    # Ancestor materialization remains the same authoritative function, invoked
    # server-side for each newly published sentence interface in one statement.
    cursor.execute(
        f"""
        SELECT execution.rebuild_pnf_interface_ancestors(interface.interface_id)
          FROM {_INTERFACE_STAGE} AS stage
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = stage.region_id
         ORDER BY stage.region_id
        """
    )
    cursor.fetchall()

    cursor.execute(
        f"""
        UPDATE execution.semantic_pnf_region AS region
           SET closure_state = {int(ClosureState.LOCALLY_CLOSED)},
               graph_revision = stage.graph_revision,
               closed_at = CURRENT_TIMESTAMP
          FROM {_INTERFACE_STAGE} AS stage
         WHERE region.region_id = stage.region_id
        """
    )
    cursor.execute(
        f"""
        UPDATE execution.semantic_pnf_work_item AS work
           SET state_id = {int(WorkState.COMPLETED)},
               lease_owner = NULL,
               lease_token = NULL,
               lease_expires_at = NULL,
               completed_at = CURRENT_TIMESTAMP
          FROM {_INTERFACE_STAGE} AS stage
         WHERE work.work_id = stage.work_id
           AND work.state_id = {int(WorkState.LEASED)}
           AND work.lease_token = stage.lease_token
           AND work.lease_epoch = stage.lease_epoch
        """
    )
    if cursor.rowcount != len(admissions):
        raise RuntimeError("numeric PNF sentence tranche fence changed during completion")

    return SentenceTrancheAdmissionReceipt(
        sentence_count=len(admissions),
        copy_stream_count=6,
        family_statement_count=12,
        interface_identity_query_count=3,
        per_sentence_stage_create_count=0,
        per_sentence_family_statement_count=0,
    )


__all__ = ["SentenceTrancheAdmissionReceipt", "persist_sentence_tranche_setwise"]
