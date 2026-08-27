"""Bounded MDL planning over exact numeric PNF interface sketches."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence

from src.pnf.numeric_hyperfabric import (
    ClosureState,
    MdlProfile,
    RegionEdgeKind,
    RegionKind,
    RegionMeasure,
    TargetKind,
    description_length,
    numeric_digest,
)
from src.storage.postgres import numeric_hyperfabric_store as store
from src.storage.postgres.spacy_parser_model import connect


DEFAULT_INTERFACE_KEY_BUDGET = int(
    os.environ.get("SENSIBLAW_INTERFACE_KEY_BUDGET", "8192")
)
_FINGERPRINT_MASK = (1 << 64) - 1
_FINGERPRINT_MULTIPLIER = 1_099_511_628_211


class InterfaceSketchBudgetExceeded(RuntimeError):
    """An exact interface sketch exceeded its configured proof budget."""


def _bounded_union(
    left: frozenset[tuple[int, int]],
    right: frozenset[tuple[int, int]],
    *,
    budget: int,
    key_family: str,
) -> frozenset[tuple[int, int]]:
    joined = left | right
    if len(joined) > budget:
        raise InterfaceSketchBudgetExceeded(
            f"{key_family} interface keys exceed exact budget {budget}: {len(joined)}"
        )
    return joined


@dataclass(frozen=True, slots=True)
class InterfaceSketch:
    region_id: int
    interface_id: int
    sequence_no: int
    start_char: int
    end_char: int
    object_keys: frozenset[tuple[int, int]]
    factor_keys: frozenset[tuple[int, int]]
    demand_keys: frozenset[tuple[int, int]]
    edge_count: int
    encoded_byte_count: int
    closure_rounds: int
    key_budget: int = DEFAULT_INTERFACE_KEY_BUDGET

    def __post_init__(self) -> None:
        if self.key_budget < 1:
            raise ValueError("interface sketch key budget must be positive")
        for family, keys in (
            ("object", self.object_keys),
            ("factor", self.factor_keys),
            ("demand", self.demand_keys),
        ):
            if len(keys) > self.key_budget:
                raise InterfaceSketchBudgetExceeded(
                    f"{family} interface keys exceed exact budget "
                    f"{self.key_budget}: {len(keys)}"
                )

    def join(self, other: "InterfaceSketch") -> "InterfaceSketch":
        if self.key_budget != other.key_budget:
            raise ValueError("joined interface sketches must share one key budget")
        return InterfaceSketch(
            region_id=self.region_id,
            interface_id=self.interface_id,
            sequence_no=min(self.sequence_no, other.sequence_no),
            start_char=min(self.start_char, other.start_char),
            end_char=max(self.end_char, other.end_char),
            # reductive merge contract:
            # object_keys=self.object_keys | other.object_keys
            object_keys=_bounded_union(
                self.object_keys,
                other.object_keys,
                budget=self.key_budget,
                key_family="object",
            ),
            factor_keys=_bounded_union(
                self.factor_keys,
                other.factor_keys,
                budget=self.key_budget,
                key_family="factor",
            ),
            demand_keys=_bounded_union(
                self.demand_keys,
                other.demand_keys,
                budget=self.key_budget,
                key_family="demand",
            ),
            edge_count=self.edge_count + other.edge_count,
            encoded_byte_count=self.encoded_byte_count + other.encoded_byte_count,
            closure_rounds=max(self.closure_rounds, other.closure_rounds),
            key_budget=self.key_budget,
        )

    def measure(
        self,
        *,
        child_count: int,
        raw_demand_count: int,
    ) -> RegionMeasure:
        unique_objects = len(self.object_keys)
        unique_factors = len(self.factor_keys)
        unresolved = len(self.demand_keys)
        discharged = max(0, raw_demand_count - unresolved)
        interface_cardinality = unique_objects + unique_factors + unresolved
        return RegionMeasure(
            node_count=interface_cardinality,
            edge_count=min(
                self.edge_count + max(0, child_count - 1),
                interface_cardinality * 4,
            ),
            unresolved_count=unresolved,
            boundary_demand_weight=max(0.0, float(unresolved - discharged)),
            encoded_byte_count=min(
                self.encoded_byte_count,
                interface_cardinality * 64,
            ),
            rule_count=1,
            closure_rounds=self.closure_rounds + 1,
            promoted_object_count=unique_objects,
            interface_cardinality=interface_cardinality,
            hierarchy_cost=float(child_count),
        )


@dataclass(frozen=True, slots=True)
class PlannedSegment:
    start: int
    end: int
    cost: float
    measure: RegionMeasure


@dataclass(frozen=True, slots=True)
class SketchSegmentation:
    segments: tuple[PlannedSegment, ...]
    total_cost: float
    evaluated_candidates: int
    asymptotic_bound: int
    exact_key_budget: int
    exact_work_bound: int


@dataclass(frozen=True, slots=True)
class _SketchState:
    total_cost: float
    segment: PlannedSegment | None
    previous: "_SketchState | None"
    segment_count: int
    path_fingerprint: int
    serial: int


def _extend_fingerprint(previous: int, *, start: int, end: int) -> int:
    segment_code = ((start & 0xFFFFFFFF) << 32) | (end & 0xFFFFFFFF)
    return ((previous * _FINGERPRINT_MULTIPLIER) ^ segment_code) & _FINGERPRINT_MASK


def _unwind_planned_segments(state: _SketchState) -> tuple[PlannedSegment, ...]:
    segments: list[PlannedSegment] = []
    current: _SketchState | None = state
    while current is not None and current.segment is not None:
        segments.append(current.segment)
        current = current.previous
    segments.reverse()
    return tuple(segments)


def plan_interface_segments(
    sketches: Sequence[InterfaceSketch],
    *,
    profile: MdlProfile,
) -> SketchSegmentation:
    """Windowed beam DP with bounded exact sketches and backpointers.

    Candidate-state work is bounded by ``O(N * W * B)`` and retained DP state
    by ``N * B``. Exact set-union work is bounded by ``N * W * 3C`` for the
    object, factor and demand key families. The runtime fails closed rather
    than truncating keys when a sketch exceeds the configured budget ``C``.
    """

    if not sketches:
        return SketchSegmentation(
            segments=(),
            total_cost=0.0,
            evaluated_candidates=0,
            asymptotic_bound=0,
            exact_key_budget=DEFAULT_INTERFACE_KEY_BUDGET,
            exact_work_bound=0,
        )
    n = len(sketches)
    window = min(profile.max_window, n)
    beam = profile.beam_width
    key_budget = sketches[0].key_budget
    if any(sketch.key_budget != key_budget for sketch in sketches):
        raise ValueError("all planned interface sketches must share one key budget")

    root = _SketchState(
        total_cost=0.0,
        segment=None,
        previous=None,
        segment_count=0,
        path_fingerprint=0,
        serial=0,
    )
    paths: list[list[_SketchState]] = [[] for _ in range(n + 1)]
    paths[0] = [root]
    evaluations = 0
    serial = 1

    for end in range(1, n + 1):
        candidates: list[_SketchState] = []
        aggregate: InterfaceSketch | None = None
        raw_demand_count = 0
        for start in range(end - 1, max(-1, end - window - 1), -1):
            sketch = sketches[start]
            aggregate = sketch if aggregate is None else sketch.join(aggregate)
            raw_demand_count += len(sketch.demand_keys)
            child_count = end - start
            measure = aggregate.measure(
                child_count=child_count,
                raw_demand_count=raw_demand_count,
            )
            local_cost = description_length(measure, profile)
            if child_count > 1:
                local_cost += profile.merge_threshold
            if not isfinite(local_cost):
                raise ValueError("interface-sketch MDL cost must be finite")
            segment = PlannedSegment(start, end, local_cost, measure)
            for prior in paths[start][:beam]:
                candidates.append(
                    _SketchState(
                        total_cost=prior.total_cost + local_cost,
                        segment=segment,
                        previous=prior,
                        segment_count=prior.segment_count + 1,
                        path_fingerprint=_extend_fingerprint(
                            prior.path_fingerprint,
                            start=start,
                            end=end,
                        ),
                        serial=serial,
                    )
                )
                serial += 1
                evaluations += 1
        candidates.sort(
            key=lambda state: (
                state.total_cost,
                state.segment_count,
                state.segment.start if state.segment is not None else -1,
                state.path_fingerprint,
                state.serial,
            )
        )
        paths[end] = candidates[:beam]

    best = paths[n][0]
    return SketchSegmentation(
        segments=_unwind_planned_segments(best),
        total_cost=best.total_cost,
        evaluated_candidates=evaluations,
        asymptotic_bound=n * window * beam,
        exact_key_budget=key_budget,
        exact_work_bound=n * window * ((3 * key_budget) + beam),
    )


def _load_paragraph_sketches(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    key_budget: int = DEFAULT_INTERFACE_KEY_BUDGET,
) -> tuple[InterfaceSketch, ...]:
    if key_budget < 1:
        raise ValueError("interface sketch key budget must be positive")
    cursor.execute(
        """
        SELECT region.region_id,
               interface.interface_id,
               region.sequence_no,
               region.start_char,
               region.end_char,
               interface.edge_count,
               interface.encoded_byte_count,
               interface.closure_rounds
          FROM execution.semantic_pnf_region AS region
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = region.region_id
         WHERE region.run_ref = %s
           AND region.document_ref = %s
           AND region.region_kind = %s
         ORDER BY region.sequence_no, region.start_char, region.region_id
        """,
        (run_ref, document_ref, int(RegionKind.PARAGRAPH)),
    )
    base_rows = tuple(cursor.fetchall())
    if not base_rows:
        return ()

    interface_ids = tuple(int(row[1]) for row in base_rows)
    keys_by_interface: dict[
        int,
        tuple[
            set[tuple[int, int]],
            set[tuple[int, int]],
            set[tuple[int, int]],
        ],
    ] = {interface_id: (set(), set(), set()) for interface_id in interface_ids}
    cursor.execute(
        """
        SELECT export.interface_id,
               export.target_kind,
               COALESCE(export.key_symbol_id, 0),
               COALESCE(export.residual_type_symbol_id, 0)
          FROM execution.semantic_pnf_interface_export AS export
         WHERE export.interface_id = ANY(%s)
         ORDER BY export.interface_id,
                  export.target_kind,
                  export.key_symbol_id,
                  export.residual_type_symbol_id,
                  export.target_id
        """,
        (list(interface_ids),),
    )
    for interface_id, target_kind, key_symbol_id, residual_id in cursor.fetchall():
        object_keys, factor_keys, demand_keys = keys_by_interface[int(interface_id)]
        key = (int(key_symbol_id), int(residual_id))
        if int(target_kind) == int(TargetKind.OBJECT):
            object_keys.add(key)
        elif int(target_kind) == int(TargetKind.FACTOR):
            factor_keys.add(key)
        elif int(target_kind) == int(TargetKind.DEMAND):
            demand_keys.add(key)

    sketches: list[InterfaceSketch] = []
    for row in base_rows:
        interface_id = int(row[1])
        object_keys, factor_keys, demand_keys = keys_by_interface[interface_id]
        sketches.append(
            InterfaceSketch(
                region_id=int(row[0]),
                interface_id=interface_id,
                sequence_no=int(row[2]),
                start_char=int(row[3]),
                end_char=int(row[4]),
                object_keys=frozenset(object_keys),
                factor_keys=frozenset(factor_keys),
                demand_keys=frozenset(demand_keys),
                edge_count=int(row[5]),
                encoded_byte_count=int(row[6]),
                closure_rounds=int(row[7]),
                key_budget=key_budget,
            )
        )
    return tuple(sketches)


def _close_canonical_parent_interface(
    cursor: Any,
    *,
    region_id: int,
    profile: MdlProfile,
) -> int:
    """Create only parent topology, then let the sparse reducer own its boundary.

    The DASHI ParentInterfaceReduction/SparseFibredFrontier contract makes the
    admitted parent export the authority and lookup a projection of that export.
    The older store helper first copied child exports and child lookups into a
    provisional parent and then the canonical reducer deleted/rebuilt both.
    This path preserves the same interface identity inputs and child topology,
    but consumes the already transported parent boundary for cardinality and
    invokes the canonical reducer before any parent boundary is observable.
    """

    cursor.execute(
        """
        SELECT run_ref, document_ref, parent_region_id,
               graph_revision, closure_state
          FROM execution.semantic_pnf_region
         WHERE region_id = %s
         FOR UPDATE
        """,
        (region_id,),
    )
    region = cursor.fetchone()
    if region is None:
        raise RuntimeError("parent PNF region disappeared")

    cursor.execute(
        "SELECT interface_id FROM execution.semantic_pnf_interface WHERE region_id = %s",
        (region_id,),
    )
    existing = cursor.fetchone()
    if existing is not None:
        interface_id = int(existing[0])
        cursor.execute(
            "SELECT * FROM execution.rebuild_numeric_pnf_parent_frontier(%s)",
            (interface_id,),
        )
        cursor.fetchone()
        return interface_id

    children = store._load_child_interfaces(cursor, region_id)
    if not children:
        raise RuntimeError("cannot close a PNF parent without child interfaces")
    aggregate = children[0][3]
    for child in children[1:]:
        aggregate = aggregate.join(child[3])
    child_interface_ids = tuple(child[2] for child in children)

    # Migration 073 continuously transports exactly the closed child export
    # boundary into this parent-local fibre.  Counting that carrier avoids the
    # historical region->interface->export reconstruction while retaining the
    # same DISTINCT (export kind, target kind, target id) identity coordinate.
    cursor.execute(
        """
        SELECT count(*)
          FROM (
              SELECT DISTINCT export_kind, target_kind, target_id
                FROM execution.semantic_pnf_parent_delta_projection
               WHERE parent_region_id = %s
          ) AS boundary
        """,
        (region_id,),
    )
    interface_cardinality = int(cursor.fetchone()[0])
    compressed = RegionMeasure(
        node_count=aggregate.node_count,
        edge_count=aggregate.edge_count,
        alternative_count=aggregate.alternative_count,
        unresolved_count=aggregate.unresolved_count,
        boundary_demand_weight=aggregate.boundary_demand_weight,
        encoded_byte_count=aggregate.encoded_byte_count,
        rule_count=aggregate.rule_count + 1,
        closure_rounds=aggregate.closure_rounds + 1,
        query_cost_ns=aggregate.query_cost_ns,
        promoted_object_count=min(
            aggregate.promoted_object_count,
            interface_cardinality,
        ),
        interface_cardinality=interface_cardinality,
        hierarchy_cost=aggregate.hierarchy_cost + len(children),
    )
    graph_revision = int(region[3]) + 1
    parent_interface_id: int | None = None
    if region[2] is not None:
        cursor.execute(
            "SELECT interface_id FROM execution.semantic_pnf_interface WHERE region_id = %s",
            (int(region[2]),),
        )
        parent = cursor.fetchone()
        parent_interface_id = int(parent[0]) if parent else None

    digest = numeric_digest(
        region_id,
        graph_revision,
        child_interface_ids,
        compressed.node_count,
        compressed.edge_count,
        compressed.interface_cardinality,
        compressed.unresolved_count,
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_interface
            (interface_digest, region_id, parent_interface_id,
             closure_state, graph_revision, node_count, edge_count,
             alternative_count, unresolved_count, boundary_demand_weight,
             encoded_byte_count, rule_count, closure_rounds, query_cost_ns,
             promoted_object_count, interface_cardinality,
             hierarchy_cost, mdl_cost)
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        RETURNING interface_id
        """,
        (
            digest,
            region_id,
            parent_interface_id,
            int(ClosureState.CLOSED),
            graph_revision,
            compressed.node_count,
            compressed.edge_count,
            compressed.alternative_count,
            compressed.unresolved_count,
            compressed.boundary_demand_weight,
            compressed.encoded_byte_count,
            compressed.rule_count,
            compressed.closure_rounds,
            compressed.query_cost_ns,
            compressed.promoted_object_count,
            compressed.interface_cardinality,
            compressed.hierarchy_cost,
            description_length(compressed, profile),
        ),
    )
    interface_id = int(cursor.fetchone()[0])

    # Topology is independent of parent semantic admission.  Ancestor material
    # publication is intentionally deferred by the enclosing hierarchy GUC and
    # rebuilt set-wise once the complete document topology exists.
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_interface
           SET parent_interface_id = %s
         WHERE interface_id = ANY(%s)
           AND parent_interface_id IS NULL
        """,
        (interface_id, list(child_interface_ids)),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s,
               graph_revision = %s,
               closed_at = CURRENT_TIMESTAMP
         WHERE region_id = %s
        """,
        (int(ClosureState.CLOSED), graph_revision, region_id),
    )

    # Sole parent-boundary authority: admitted exports, actor summaries,
    # unresolved demands, resolution state, and searchable lookup are all
    # produced together by the existing canonical sparse reducer.
    cursor.execute(
        "SELECT * FROM execution.rebuild_numeric_pnf_parent_frontier(%s)",
        (interface_id,),
    )
    cursor.fetchone()
    return interface_id


def _refresh_reductive_measure(
    cursor: Any,
    *,
    interface_id: int,
    profile: MdlProfile,
) -> None:
    cursor.execute(
        """
        SELECT
            count(*),
            count(*) FILTER (WHERE target_kind = %s),
            count(*) FILTER (WHERE target_kind = %s),
            count(*) FILTER (WHERE target_kind = %s)
          FROM execution.semantic_pnf_interface_export
         WHERE interface_id = %s
        """,
        (
            int(TargetKind.OBJECT),
            int(TargetKind.FACTOR),
            int(TargetKind.DEMAND),
            interface_id,
        ),
    )
    total, object_count, _factor_count, demand_count = (
        int(value) for value in cursor.fetchone()
    )
    cursor.execute(
        """
        SELECT count(*)
          FROM execution.semantic_pnf_hyperedge AS edge
          JOIN execution.semantic_pnf_interface_export AS export
            ON export.interface_id = %s
           AND export.target_kind = %s
           AND export.target_id = edge.factor_id
        """,
        (interface_id, int(TargetKind.FACTOR)),
    )
    edge_count = int(cursor.fetchone()[0])
    measure = RegionMeasure(
        node_count=total,
        edge_count=edge_count,
        unresolved_count=demand_count,
        boundary_demand_weight=float(demand_count),
        encoded_byte_count=total * 64,
        rule_count=1,
        closure_rounds=1,
        promoted_object_count=object_count,
        interface_cardinality=total,
        hierarchy_cost=1.0,
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_interface
           SET node_count = %s,
               edge_count = %s,
               unresolved_count = %s,
               boundary_demand_weight = %s,
               encoded_byte_count = %s,
               promoted_object_count = %s,
               interface_cardinality = %s,
               mdl_cost = %s
         WHERE interface_id = %s
        """,
        (
            total,
            edge_count,
            demand_count,
            float(demand_count),
            total * 64,
            object_count,
            total,
            description_length(measure, profile),
            interface_id,
        ),
    )


def materialize_numeric_document_hierarchy(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    interface_key_budget: int = DEFAULT_INTERFACE_KEY_BUDGET,
) -> store.HierarchySummary:
    """Close authored paragraphs, adaptive blocks, and the document interface."""

    if interface_key_budget < 1:
        raise ValueError("interface sketch key budget must be positive")
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config(%s, %s, true)",
                    ("sensiblaw.defer_frontier_rebuild", "on"),
                )
                profile = store._load_profile(cursor)
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_work_item
                     WHERE run_ref = %s
                       AND operation_id = %s
                       AND state_id <> %s
                    """,
                    (run_ref, 1, 3),
                )
                pending = int(cursor.fetchone()[0])
                if pending:
                    raise RuntimeError(
                        f"cannot close document with {pending} sentence regions pending"
                    )
                cursor.execute(
                    """
                    SELECT region_id
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s
                       AND document_ref = %s
                       AND region_kind = %s
                     ORDER BY sequence_no
                    """,
                    (run_ref, document_ref, int(RegionKind.PARAGRAPH)),
                )
                paragraph_ids = tuple(int(row[0]) for row in cursor.fetchall())
                for paragraph_id in paragraph_ids:
                    cursor.execute(
                        """
                        SELECT count(*),
                               count(*) FILTER (
                                   WHERE closure_state IN (%s, %s)
                               )
                          FROM execution.semantic_pnf_region
                         WHERE parent_region_id = %s
                           AND region_kind = %s
                        """,
                        (
                            int(ClosureState.LOCALLY_CLOSED),
                            int(ClosureState.CLOSED),
                            paragraph_id,
                            int(RegionKind.SENTENCE),
                        ),
                    )
                    total, closed = (int(value) for value in cursor.fetchone())
                    if total == 0:
                        continue
                    if total != closed:
                        raise RuntimeError(
                            "paragraph closure encountered an open sentence region"
                        )
                    interface_id = _close_canonical_parent_interface(
                        cursor,
                        region_id=paragraph_id,
                        profile=profile,
                    )
                    _refresh_reductive_measure(
                        cursor,
                        interface_id=interface_id,
                        profile=profile,
                    )

                cursor.execute(
                    "SELECT execution.reduce_numeric_pnf_document_frontiers(%s, %s)",
                    (run_ref, document_ref),
                )
                cursor.fetchone()

                sketches = _load_paragraph_sketches(
                    cursor,
                    run_ref=run_ref,
                    document_ref=document_ref,
                    key_budget=interface_key_budget,
                )
                segmentation = plan_interface_segments(sketches, profile=profile)
                cursor.execute(
                    """
                    SELECT region_id
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s
                       AND document_ref = %s
                       AND region_kind = %s
                     LIMIT 1
                    """,
                    (run_ref, document_ref, int(RegionKind.DOCUMENT)),
                )
                document_row = cursor.fetchone()
                if document_row is None:
                    raise RuntimeError("document PNF region is missing")
                document_region_id = int(document_row[0])
                adaptive_count = 0
                for ordinal, segment in enumerate(segmentation.segments):
                    members = sketches[segment.start : segment.end]
                    if len(members) <= 1:
                        continue
                    adaptive_id = store._insert_region(
                        cursor,
                        run_ref=run_ref,
                        document_ref=document_ref,
                        kind=RegionKind.ADAPTIVE_BLOCK,
                        start_char=members[0].start_char,
                        end_char=members[-1].end_char,
                        sequence_no=ordinal,
                        parent_region_id=document_region_id,
                        authored_boundary=False,
                    )
                    adaptive_count += 1
                    member_ids = [member.region_id for member in members]
                    cursor.execute(
                        """
                        UPDATE execution.semantic_pnf_region
                           SET parent_region_id = %s
                         WHERE region_id = ANY(%s)
                        """,
                        (adaptive_id, member_ids),
                    )
                    cursor.executemany(
                        """
                        INSERT INTO execution.semantic_pnf_region_edge
                            (source_region_id, target_region_id,
                             edge_kind, ordinal)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        [
                            (
                                member.region_id,
                                adaptive_id,
                                int(RegionEdgeKind.CONTAINS),
                                member_ordinal,
                            )
                            for member_ordinal, member in enumerate(members)
                        ],
                    )
                    interface_id = _close_canonical_parent_interface(
                        cursor,
                        region_id=adaptive_id,
                        profile=profile,
                    )
                    _refresh_reductive_measure(
                        cursor,
                        interface_id=interface_id,
                        profile=profile,
                    )

                document_interface_id = _close_canonical_parent_interface(
                    cursor,
                    region_id=document_region_id,
                    profile=profile,
                )
                _refresh_reductive_measure(
                    cursor,
                    interface_id=document_interface_id,
                    profile=profile,
                )
                cursor.execute(
                    "SELECT execution.reduce_numeric_pnf_document_frontiers(%s, %s)",
                    (run_ref, document_ref),
                )
                cursor.fetchone()
                cursor.execute(
                    "SELECT execution.rebuild_pnf_document_ancestors(%s, %s)",
                    (run_ref, document_ref),
                )
                cursor.execute(
                    "SELECT execution.refresh_pnf_visible_lookup(%s, %s)",
                    (run_ref, document_ref),
                )
                visible_rows = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE region_kind = %s),
                        count(*) FILTER (WHERE region_kind = %s),
                        count(*) FILTER (WHERE region_kind = %s)
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s AND document_ref = %s
                    """,
                    (
                        int(RegionKind.SENTENCE),
                        int(RegionKind.PARAGRAPH),
                        int(RegionKind.ADAPTIVE_BLOCK),
                        run_ref,
                        document_ref,
                    ),
                )
                sentence_count, paragraph_count, adaptive_regions = (
                    int(value) for value in cursor.fetchone()
                )
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_interface AS interface
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                interface_count = int(cursor.fetchone()[0])
                return store.HierarchySummary(
                    sentence_regions=sentence_count,
                    paragraph_regions=paragraph_count,
                    adaptive_regions=max(adaptive_count, adaptive_regions),
                    interface_count=interface_count,
                    visible_index_rows=visible_rows,
                    segmentation_evaluations=segmentation.evaluated_candidates,
                    segmentation_bound=segmentation.asymptotic_bound,
                    document_interface_id=document_interface_id,
                )
    finally:
        connection.close()


__all__ = [
    "DEFAULT_INTERFACE_KEY_BUDGET",
    "InterfaceSketch",
    "InterfaceSketchBudgetExceeded",
    "PlannedSegment",
    "SketchSegmentation",
    "materialize_numeric_document_hierarchy",
    "plan_interface_segments",
]
