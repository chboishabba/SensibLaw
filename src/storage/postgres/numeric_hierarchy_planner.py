"""Bounded MDL planning over compact numeric PNF interface sketches."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence

from src.pnf.numeric_hyperfabric import (
    ClosureState,
    ExportKind,
    MdlProfile,
    RegionEdgeKind,
    RegionKind,
    RegionMeasure,
    TargetKind,
    description_length,
)
from src.storage.postgres import numeric_hyperfabric_store as store
from src.storage.postgres.spacy_parser_model import connect


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

    def join(self, other: "InterfaceSketch") -> "InterfaceSketch":
        return InterfaceSketch(
            region_id=self.region_id,
            interface_id=self.interface_id,
            sequence_no=min(self.sequence_no, other.sequence_no),
            start_char=min(self.start_char, other.start_char),
            end_char=max(self.end_char, other.end_char),
            object_keys=self.object_keys | other.object_keys,
            factor_keys=self.factor_keys | other.factor_keys,
            demand_keys=self.demand_keys | other.demand_keys,
            edge_count=self.edge_count + other.edge_count,
            encoded_byte_count=self.encoded_byte_count + other.encoded_byte_count,
            closure_rounds=max(self.closure_rounds, other.closure_rounds),
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


def plan_interface_segments(
    sketches: Sequence[InterfaceSketch],
    *,
    profile: MdlProfile,
) -> SketchSegmentation:
    """Windowed beam DP over incrementally joined interface sketches.

    Candidate construction is O(N * W * B) for fixed-width compact sketches.
    The cost is the reduced parent interface, not the sum of raw descendant
    graph populations, so recurrence and boundary discharge can justify merges.
    """

    if not sketches:
        return SketchSegmentation((), 0.0, 0, 0)
    n = len(sketches)
    window = min(profile.max_window, n)
    beam = profile.beam_width
    paths: list[list[tuple[float, tuple[PlannedSegment, ...]]]] = [
        [] for _ in range(n + 1)
    ]
    paths[0] = [(0.0, ())]
    evaluations = 0

    for end in range(1, n + 1):
        candidates: list[tuple[float, tuple[PlannedSegment, ...]]] = []
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
            for prior_cost, prior_segments in paths[start][:beam]:
                candidates.append(
                    (prior_cost + local_cost, (*prior_segments, segment))
                )
                evaluations += 1
        candidates.sort(
            key=lambda row: (
                row[0],
                len(row[1]),
                tuple((segment.start, segment.end) for segment in row[1]),
            )
        )
        paths[end] = candidates[:beam]

    total_cost, segments = paths[n][0]
    return SketchSegmentation(
        segments=segments,
        total_cost=total_cost,
        evaluated_candidates=evaluations,
        asymptotic_bound=n * window * beam,
    )


def _load_paragraph_sketches(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[InterfaceSketch, ...]:
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
    sketches: list[InterfaceSketch] = []
    for row in base_rows:
        interface_id = int(row[1])
        cursor.execute(
            """
            SELECT export.target_kind,
                   COALESCE(export.key_symbol_id, 0),
                   COALESCE(export.residual_type_symbol_id, 0)
              FROM execution.semantic_pnf_interface_export AS export
             WHERE export.interface_id = %s
             ORDER BY export.target_kind,
                      export.key_symbol_id,
                      export.residual_type_symbol_id,
                      export.target_id
            """,
            (interface_id,),
        )
        object_keys: set[tuple[int, int]] = set()
        factor_keys: set[tuple[int, int]] = set()
        demand_keys: set[tuple[int, int]] = set()
        for target_kind, key_symbol_id, residual_id in cursor.fetchall():
            key = (int(key_symbol_id), int(residual_id))
            if int(target_kind) == int(TargetKind.OBJECT):
                object_keys.add(key)
            elif int(target_kind) == int(TargetKind.FACTOR):
                factor_keys.add(key)
            elif int(target_kind) == int(TargetKind.DEMAND):
                demand_keys.add(key)
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
            )
        )
    return tuple(sketches)


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
    total, object_count, factor_count, demand_count = (
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
) -> store.HierarchySummary:
    """Close authored paragraphs, adaptive blocks, and the document interface."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
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
                    interface_id = store._close_parent_interface(
                        cursor,
                        region_id=paragraph_id,
                        profile=profile,
                    )
                    _refresh_reductive_measure(
                        cursor,
                        interface_id=interface_id,
                        profile=profile,
                    )

                sketches = _load_paragraph_sketches(
                    cursor,
                    run_ref=run_ref,
                    document_ref=document_ref,
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
                    interface_id = store._close_parent_interface(
                        cursor,
                        region_id=adaptive_id,
                        profile=profile,
                    )
                    _refresh_reductive_measure(
                        cursor,
                        interface_id=interface_id,
                        profile=profile,
                    )

                document_interface_id = store._close_parent_interface(
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
    "InterfaceSketch",
    "PlannedSegment",
    "SketchSegmentation",
    "materialize_numeric_document_hierarchy",
    "plan_interface_segments",
]
