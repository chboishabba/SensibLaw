"""Persistent numeric PNF hyperfabric execution and indexed lookup.

Sentence regions close while parsing continues.  Authored paragraph boundaries
provide the initial hierarchy; a bounded-window MDL planner adds adaptive parent
regions without considering book-wide all-pairs intervals.  Parent interfaces
contain only promoted exports and unresolved demands, while provenance remains
in immutable child graphs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from src.pnf.numeric_hyperfabric import (
    ClosureState,
    ExportKind,
    KeyKind,
    MdlProfile,
    RegionEdgeKind,
    RegionKind,
    RegionMeasure,
    TargetKind,
    WorkOperation,
    WorkState,
    bounded_segmentation,
    description_length,
    numeric_digest,
    promotion_score,
    should_promote,
)
from src.pnf.numeric_operator_composition import (
    NumericSentenceClosure,
    NumericToken,
    OperatorLexicon,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)
from src.storage.postgres.numeric_symbol_store import intern_symbols
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class WorkLease:
    work_id: int
    region_id: int
    operation: WorkOperation
    lease_token: str
    lease_epoch: int


@dataclass(frozen=True, slots=True)
class LookupCandidate:
    target_kind: TargetKind
    target_id: int
    source_interface_id: int
    ancestor_distance: int
    rank: int


@dataclass(frozen=True, slots=True)
class HierarchySummary:
    sentence_regions: int
    paragraph_regions: int
    adaptive_regions: int
    interface_count: int
    visible_index_rows: int
    segmentation_evaluations: int
    segmentation_bound: int
    document_interface_id: int


_LEXICON_CACHE: dict[str, OperatorLexicon] = {}


def _region_digest(
    *,
    run_ref: str,
    document_ref: str,
    kind: RegionKind,
    start_char: int,
    end_char: int,
) -> bytes:
    return numeric_digest(
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        int(kind),
        start_char,
        end_char,
    )


def authored_paragraphs(text: str) -> tuple[tuple[int, int], ...]:
    """Return non-empty paragraph-like authored intervals.

    This executes once before parsing.  It is a structural-carrier operation,
    not a reparse of committed parser observations.
    """

    if not text:
        return ()
    boundaries: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"\n[ \t]*\n+", text):
        end = match.start()
        if text[start:end].strip():
            left = start
            while left < end and text[left].isspace():
                left += 1
            right = end
            while right > left and text[right - 1].isspace():
                right -= 1
            if right > left:
                boundaries.append((left, right))
        start = match.end()
    if text[start:].strip():
        left = start
        while left < len(text) and text[left].isspace():
            left += 1
        right = len(text)
        while right > left and text[right - 1].isspace():
            right -= 1
        if right > left:
            boundaries.append((left, right))
    return tuple(boundaries or ((0, len(text)),))


def _insert_region(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    kind: RegionKind,
    start_char: int,
    end_char: int,
    sequence_no: int,
    parent_region_id: int | None,
    authored_boundary: bool,
) -> int:
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_region
            (region_digest, run_ref, document_ref, region_kind,
             start_char, end_char, sequence_no, parent_region_id,
             closure_state, authored_boundary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (
            run_ref, document_ref, region_kind, start_char, end_char
        ) DO UPDATE SET
            parent_region_id = COALESCE(
                execution.semantic_pnf_region.parent_region_id,
                EXCLUDED.parent_region_id
            ),
            authored_boundary = (
                execution.semantic_pnf_region.authored_boundary
                OR EXCLUDED.authored_boundary
            )
        RETURNING region_id
        """,
        (
            _region_digest(
                run_ref=run_ref,
                document_ref=document_ref,
                kind=kind,
                start_char=start_char,
                end_char=end_char,
            ),
            run_ref,
            document_ref,
            int(kind),
            start_char,
            end_char,
            sequence_no,
            parent_region_id,
            int(ClosureState.OPEN),
            authored_boundary,
        ),
    )
    return int(cursor.fetchone()[0])


def register_authored_hierarchy(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    canonical_text: str,
    execution_window_chars: int = 65_536,
) -> tuple[int, tuple[int, ...]]:
    """Register the immutable document/paragraph/execution region skeleton."""

    if not canonical_text:
        raise ValueError("numeric PNF hierarchy requires non-empty source")
    if execution_window_chars < 4_096:
        raise ValueError("execution windows must be at least 4096 characters")
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"pnf-hierarchy:{run_ref}:{document_ref}",),
                )
                document_region_id = _insert_region(
                    cursor,
                    run_ref=run_ref,
                    document_ref=document_ref,
                    kind=RegionKind.DOCUMENT,
                    start_char=0,
                    end_char=len(canonical_text),
                    sequence_no=0,
                    parent_region_id=None,
                    authored_boundary=True,
                )
                paragraph_ids: list[int] = []
                for ordinal, (start, end) in enumerate(
                    authored_paragraphs(canonical_text)
                ):
                    region_id = _insert_region(
                        cursor,
                        run_ref=run_ref,
                        document_ref=document_ref,
                        kind=RegionKind.PARAGRAPH,
                        start_char=start,
                        end_char=end,
                        sequence_no=ordinal,
                        parent_region_id=document_region_id,
                        authored_boundary=True,
                    )
                    paragraph_ids.append(region_id)
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_region_edge
                            (source_region_id, target_region_id, edge_kind, ordinal)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            region_id,
                            document_region_id,
                            int(RegionEdgeKind.CONTAINS),
                            ordinal,
                        ),
                    )
                for ordinal, (left, right) in enumerate(
                    zip(paragraph_ids, paragraph_ids[1:])
                ):
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_region_edge
                            (source_region_id, target_region_id, edge_kind, ordinal)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            left,
                            right,
                            int(RegionEdgeKind.ADJACENT),
                            ordinal,
                        ),
                    )

                window_start = 0
                window_ordinal = 0
                while window_start < len(canonical_text):
                    window_end = min(
                        len(canonical_text),
                        window_start + execution_window_chars,
                    )
                    window_id = _insert_region(
                        cursor,
                        run_ref=run_ref,
                        document_ref=document_ref,
                        kind=RegionKind.EXECUTION_WINDOW,
                        start_char=window_start,
                        end_char=window_end,
                        sequence_no=window_ordinal,
                        parent_region_id=document_region_id,
                        authored_boundary=False,
                    )
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_pnf_region_edge
                            (source_region_id, target_region_id, edge_kind, ordinal)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            window_id,
                            document_region_id,
                            int(RegionEdgeKind.EXECUTION_CONTAINS),
                            window_ordinal,
                        ),
                    )
                    window_start = window_end
                    window_ordinal += 1
                return document_region_id, tuple(paragraph_ids)
    finally:
        connection.close()


def _operator_lexicon(cursor: Any, database_url: str) -> OperatorLexicon:
    cached = _LEXICON_CACHE.get(database_url)
    if cached is not None:
        return cached
    symbols = intern_symbols(cursor, operator_symbol_values())
    lexicon = build_operator_lexicon(symbols)
    _LEXICON_CACHE[database_url] = lexicon
    return lexicon


def claim_work(
    cursor: Any,
    *,
    run_ref: str,
    worker_ref: str,
    operation: WorkOperation,
    lease_seconds: int = 120,
) -> WorkLease | None:
    if lease_seconds < 1:
        raise ValueError("numeric PNF work lease must be positive")
    cursor.execute(
        """
        SELECT work_id, region_id, lease_epoch
          FROM execution.semantic_pnf_work_item
         WHERE run_ref = %s
           AND operation_id = %s
           AND (
               state_id = %s
               OR (
                   state_id = %s
                   AND lease_expires_at < CURRENT_TIMESTAMP
               )
           )
         ORDER BY priority, work_id
         FOR UPDATE SKIP LOCKED
         LIMIT 1
        """,
        (
            run_ref,
            int(operation),
            int(WorkState.READY),
            int(WorkState.LEASED),
        ),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    work_id, region_id, prior_epoch = (
        int(row[0]),
        int(row[1]),
        int(row[2]),
    )
    lease_epoch = prior_epoch + 1
    token = uuid4().hex
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = %s,
               lease_token = %s,
               lease_epoch = %s,
               lease_expires_at = CURRENT_TIMESTAMP
                   + (%s * INTERVAL '1 second'),
               attempt_count = attempt_count + 1
         WHERE work_id = %s
        """,
        (
            int(WorkState.LEASED),
            worker_ref,
            token,
            lease_epoch,
            lease_seconds,
            work_id,
        ),
    )
    return WorkLease(
        work_id=work_id,
        region_id=region_id,
        operation=operation,
        lease_token=token,
        lease_epoch=lease_epoch,
    )


def _load_sentence_tokens(
    cursor: Any,
    region_id: int,
) -> tuple[NumericToken, ...]:
    cursor.execute(
        """
        SELECT token.token_id,
               token.orth_symbol_id,
               token.lemma_symbol_id,
               token.pos_symbol_id,
               token.tag_symbol_id,
               token.dependency_symbol_id,
               token.head_token_id,
               token.morph_set_id,
               token.start_char,
               token.end_char
          FROM execution.semantic_pnf_sentence_region AS link
          JOIN execution.semantic_parser_token AS token
            ON token.sentence_id = link.sentence_id
         WHERE link.region_id = %s
           AND token.representation_version = 2
         ORDER BY token.local_token_ordinal, token.token_id
        """,
        (region_id,),
    )
    rows = cursor.fetchall()
    tokens = tuple(
        NumericToken(
            token_id=int(row[0]),
            orth_id=int(row[1]),
            lemma_id=int(row[2]),
            pos_id=int(row[3]),
            tag_id=int(row[4]),
            dependency_id=int(row[5]),
            head_token_id=int(row[6] or row[0]),
            morph_set_id=int(row[7]) if row[7] is not None else None,
            start_char=int(row[8]),
            end_char=int(row[9]),
        )
        for row in rows
    )
    if not tokens:
        raise RuntimeError("numeric sentence region has no typed parser tokens")
    return tokens


def _load_profile(cursor: Any, profile_id: int = 1) -> MdlProfile:
    cursor.execute(
        """
        SELECT node_weight, edge_weight, alternative_weight,
               unresolved_weight, boundary_weight, encoded_byte_weight,
               rule_weight, closure_round_weight, query_ns_weight,
               promoted_object_weight, interface_member_weight,
               hierarchy_weight, promotion_alpha, promotion_beta,
               promotion_threshold, merge_threshold,
               max_window, beam_width
          FROM execution.semantic_pnf_mdl_profile
         WHERE profile_id = %s
        """,
        (profile_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"numeric PNF MDL profile is missing: {profile_id}")
    return MdlProfile(
        node_weight=float(row[0]),
        edge_weight=float(row[1]),
        alternative_weight=float(row[2]),
        unresolved_weight=float(row[3]),
        boundary_weight=float(row[4]),
        encoded_byte_weight=float(row[5]),
        rule_weight=float(row[6]),
        closure_round_weight=float(row[7]),
        query_ns_weight=float(row[8]),
        promoted_object_weight=float(row[9]),
        interface_member_weight=float(row[10]),
        hierarchy_weight=float(row[11]),
        promotion_alpha=float(row[12]),
        promotion_beta=float(row[13]),
        promotion_threshold=float(row[14]),
        merge_threshold=float(row[15]),
        max_window=int(row[16]),
        beam_width=int(row[17]),
    )


def _persist_sentence_closure(
    cursor: Any,
    *,
    lease: WorkLease,
    closure: NumericSentenceClosure,
    profile: MdlProfile,
) -> int:
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
    run_ref = str(row[3])
    document_ref = str(row[4])
    parent_region_id = int(row[5]) if row[5] is not None else None
    graph_revision = int(row[6]) + 1

    object_id_by_token: dict[int, int] = {}
    promoted_object_ids: list[tuple[int, int, float]] = []
    for object_spec in closure.objects:
        score = promotion_score(object_spec.promotion_evidence, profile)
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_object
                (object_digest, region_id, object_kind_symbol_id,
                 head_symbol_id, scope_region_id, promotion_level,
                 information_gain, representation_cost, ambiguity_cost,
                 promotion_score, active)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, TRUE)
            ON CONFLICT (object_digest) DO UPDATE SET
                promotion_score = EXCLUDED.promotion_score,
                active = TRUE
            RETURNING object_id
            """,
            (
                object_spec.object_digest,
                lease.region_id,
                object_spec.object_kind_symbol_id,
                object_spec.head_symbol_id,
                lease.region_id,
                object_spec.information_gain,
                object_spec.representation_cost,
                object_spec.ambiguity_cost,
                score,
            ),
        )
        object_id = int(cursor.fetchone()[0])
        object_id_by_token[object_spec.source_token_id] = object_id
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_object_token_support
                (object_id, token_id, ordinal)
            VALUES (%s, %s, 0)
            ON CONFLICT DO NOTHING
            """,
            (object_id, object_spec.source_token_id),
        )
        if should_promote(object_spec.promotion_evidence, profile):
            promoted_object_ids.append(
                (object_id, object_spec.head_symbol_id, score)
            )

    factor_ids: list[tuple[int, int, int]] = []
    for factor_spec in closure.factors:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_factor
                (factor_digest, region_id, factor_type_symbol_id,
                 predicate_symbol_id, scope_region_id,
                 temporal_state, modal_state, promotion_level,
                 support_score, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, TRUE)
            ON CONFLICT (factor_digest) DO UPDATE SET active = TRUE
            RETURNING factor_id
            """,
            (
                factor_spec.factor_digest,
                lease.region_id,
                factor_spec.factor_type_symbol_id,
                factor_spec.predicate_symbol_id,
                lease.region_id,
                factor_spec.temporal_state,
                factor_spec.modal_state,
                factor_spec.support_score,
            ),
        )
        factor_id = int(cursor.fetchone()[0])
        factor_ids.append(
            (
                factor_id,
                factor_spec.factor_type_symbol_id,
                factor_spec.predicate_symbol_id,
            )
        )
        cursor.executemany(
            """
            INSERT INTO execution.semantic_pnf_factor_token_support
                (factor_id, token_id, ordinal)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            [
                (factor_id, token_id, ordinal)
                for ordinal, token_id in enumerate(
                    factor_spec.support_token_ids
                )
            ],
        )
        cursor.executemany(
            """
            INSERT INTO execution.semantic_pnf_hyperedge
                (factor_id, slot_ordinal, role_symbol_id,
                 object_id, resolution_state, required)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    factor_id,
                    ordinal,
                    slot.role_symbol_id,
                    object_id_by_token[slot.source_token_id],
                    int(slot.resolution_state),
                    slot.required,
                )
                for ordinal, slot in enumerate(factor_spec.slots)
                if slot.source_token_id in object_id_by_token
            ],
        )

    demand_ids: list[tuple[int, int, int | None, int | None]] = []
    for demand in closure.demands:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_demand
                (demand_digest, source_region_id,
                 expected_target_kind,
                 expected_factor_type_symbol_id,
                 expected_object_kind_symbol_id,
                 lexical_symbol_id, role_symbol_id,
                 residual_type_symbol_id, recency_class,
                 state, max_candidates)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
            ON CONFLICT (demand_digest) DO UPDATE SET
                state = LEAST(execution.semantic_pnf_demand.state, 1)
            RETURNING demand_id
            """,
            (
                demand.demand_digest,
                lease.region_id,
                int(demand.expected_target_kind),
                demand.expected_factor_type_symbol_id,
                demand.expected_object_kind_symbol_id,
                demand.lexical_symbol_id,
                demand.role_symbol_id,
                demand.residual_type_symbol_id,
                int(demand.recency_class),
                demand.max_candidates,
            ),
        )
        demand_ids.append(
            (
                int(cursor.fetchone()[0]),
                demand.residual_type_symbol_id,
                demand.expected_factor_type_symbol_id,
                demand.lexical_symbol_id,
            )
        )

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
            """
            SELECT interface_id
              FROM execution.semantic_pnf_interface
             WHERE region_id = %s
            """,
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
            (
                len(promoted_object_ids)
                + len(factor_ids)
                + len(demand_ids)
            ),
            measure.hierarchy_cost,
            description_length(measure, profile),
        ),
    )
    interface_id = int(cursor.fetchone()[0])

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
    for rank, (object_id, head_symbol_id, _score) in enumerate(
        promoted_object_ids
    ):
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
        "SELECT execution.rebuild_pnf_interface_ancestors(%s)",
        (interface_id,),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s,
               graph_revision = %s,
               closed_at = CURRENT_TIMESTAMP
         WHERE region_id = %s
        """,
        (
            int(ClosureState.LOCALLY_CLOSED),
            graph_revision,
            lease.region_id,
        ),
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


def drain_sentence_closure(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
) -> int:
    if limit < 1:
        raise ValueError("numeric sentence closure limit must be positive")
    completed = 0
    connection = connect(database_url)
    try:
        while completed < limit:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = claim_work(
                        cursor,
                        run_ref=run_ref,
                        worker_ref=worker_ref,
                        operation=WorkOperation.SENTENCE_CLOSE,
                    )
            if lease is None:
                break
            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        tokens = _load_sentence_tokens(cursor, lease.region_id)
                        profile = _load_profile(cursor)
                        lexicon = _operator_lexicon(cursor, database_url)
                        closure = compose_numeric_sentence(
                            region_id=lease.region_id,
                            tokens=tokens,
                            lexicon=lexicon,
                        )
                        _persist_sentence_closure(
                            cursor,
                            lease=lease,
                            closure=closure,
                            profile=profile,
                        )
                completed += 1
            except BaseException:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_pnf_work_item
                               SET state_id = %s,
                                   lease_owner = NULL,
                                   lease_token = NULL,
                                   lease_expires_at = NULL,
                                   completed_at = CURRENT_TIMESTAMP,
                                   last_error_code = 1
                             WHERE work_id = %s
                               AND lease_token = %s
                               AND lease_epoch = %s
                            """,
                            (
                                int(WorkState.FAILED),
                                lease.work_id,
                                lease.lease_token,
                                lease.lease_epoch,
                            ),
                        )
                        cursor.execute(
                            """
                            UPDATE execution.semantic_pnf_region
                               SET closure_state = %s
                             WHERE region_id = %s
                            """,
                            (int(ClosureState.FAILED), lease.region_id),
                        )
                raise
    finally:
        connection.close()
    return completed


def _measure_from_row(row: Sequence[Any]) -> RegionMeasure:
    return RegionMeasure(
        node_count=int(row[0]),
        edge_count=int(row[1]),
        alternative_count=int(row[2]),
        unresolved_count=int(row[3]),
        boundary_demand_weight=float(row[4]),
        encoded_byte_count=int(row[5]),
        rule_count=int(row[6]),
        closure_rounds=int(row[7]),
        query_cost_ns=int(row[8]),
        promoted_object_count=int(row[9]),
        interface_cardinality=int(row[10]),
        hierarchy_cost=float(row[11]),
    )


def _load_child_interfaces(
    cursor: Any,
    parent_region_id: int,
) -> tuple[tuple[int, int, int, RegionMeasure], ...]:
    cursor.execute(
        """
        SELECT child.region_id,
               child.sequence_no,
               interface.interface_id,
               interface.node_count,
               interface.edge_count,
               interface.alternative_count,
               interface.unresolved_count,
               interface.boundary_demand_weight,
               interface.encoded_byte_count,
               interface.rule_count,
               interface.closure_rounds,
               interface.query_cost_ns,
               interface.promoted_object_count,
               interface.interface_cardinality,
               interface.hierarchy_cost
          FROM execution.semantic_pnf_region AS child
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = child.region_id
         WHERE child.parent_region_id = %s
           AND child.region_kind <> %s
         ORDER BY child.sequence_no, child.start_char, child.region_id
        """,
        (parent_region_id, int(RegionKind.EXECUTION_WINDOW)),
    )
    return tuple(
        (
            int(row[0]),
            int(row[1]),
            int(row[2]),
            _measure_from_row(row[3:]),
        )
        for row in cursor.fetchall()
    )


def _close_parent_interface(
    cursor: Any,
    *,
    region_id: int,
    profile: MdlProfile,
) -> int:
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
        return int(existing[0])
    children = _load_child_interfaces(cursor, region_id)
    if not children:
        raise RuntimeError("cannot close a PNF parent without child interfaces")
    aggregate = children[0][3]
    for child in children[1:]:
        aggregate = aggregate.join(child[3])
    child_interface_ids = tuple(child[2] for child in children)

    cursor.execute(
        """
        SELECT count(*)
          FROM (
              SELECT DISTINCT export_kind, target_kind, target_id
                FROM execution.semantic_pnf_interface_export
               WHERE interface_id = ANY(%s)
          ) AS exports
        """,
        (list(child_interface_ids),),
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
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, role_symbol_id, residual_type_symbol_id,
             rank, promotion_score)
        SELECT %s,
               export_kind,
               target_kind,
               target_id,
               key_symbol_id,
               role_symbol_id,
               residual_type_symbol_id,
               min(rank),
               max(promotion_score)
          FROM execution.semantic_pnf_interface_export
         WHERE interface_id = ANY(%s)
         GROUP BY
               export_kind, target_kind, target_id,
               key_symbol_id, role_symbol_id, residual_type_symbol_id
        ON CONFLICT DO NOTHING
        """,
        (interface_id, list(child_interface_ids)),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        SELECT %s,
               key_kind,
               key_a,
               key_b,
               target_kind,
               target_id,
               min(rank)
          FROM execution.semantic_pnf_interface_lookup
         WHERE interface_id = ANY(%s)
         GROUP BY key_kind, key_a, key_b, target_kind, target_id
        ON CONFLICT DO NOTHING
        """,
        (interface_id, list(child_interface_ids)),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_interface
           SET parent_interface_id = %s
         WHERE interface_id = ANY(%s)
           AND parent_interface_id IS NULL
        """,
        (interface_id, list(child_interface_ids)),
    )
    for child_interface_id in child_interface_ids:
        cursor.execute(
            "SELECT execution.rebuild_pnf_interface_ancestors(%s)",
            (child_interface_id,),
        )
    cursor.execute(
        "SELECT execution.rebuild_pnf_interface_ancestors(%s)",
        (interface_id,),
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
    return interface_id


def materialize_document_hierarchy(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> HierarchySummary:
    """Close paragraph/adaptive/document interfaces in bounded near-linear work."""

    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                profile = _load_profile(cursor)
                cursor.execute(
                    """
                    SELECT count(*)
                      FROM execution.semantic_pnf_work_item
                     WHERE run_ref = %s
                       AND operation_id = %s
                       AND state_id <> %s
                    """,
                    (
                        run_ref,
                        int(WorkOperation.SENTENCE_CLOSE),
                        int(WorkState.COMPLETED),
                    ),
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
                paragraph_interfaces: list[
                    tuple[int, int, int, RegionMeasure]
                ] = []
                for paragraph_id in paragraph_ids:
                    cursor.execute(
                        """
                        SELECT count(*),
                               count(*) FILTER (
                                   WHERE child.closure_state IN (%s, %s)
                               )
                          FROM execution.semantic_pnf_region AS child
                         WHERE child.parent_region_id = %s
                           AND child.region_kind = %s
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
                    interface_id = _close_parent_interface(
                        cursor,
                        region_id=paragraph_id,
                        profile=profile,
                    )
                    cursor.execute(
                        """
                        SELECT region.sequence_no,
                               interface.node_count,
                               interface.edge_count,
                               interface.alternative_count,
                               interface.unresolved_count,
                               interface.boundary_demand_weight,
                               interface.encoded_byte_count,
                               interface.rule_count,
                               interface.closure_rounds,
                               interface.query_cost_ns,
                               interface.promoted_object_count,
                               interface.interface_cardinality,
                               interface.hierarchy_cost
                          FROM execution.semantic_pnf_region AS region
                          JOIN execution.semantic_pnf_interface AS interface
                            ON interface.region_id = region.region_id
                         WHERE region.region_id = %s
                        """,
                        (paragraph_id,),
                    )
                    row = cursor.fetchone()
                    paragraph_interfaces.append(
                        (
                            paragraph_id,
                            int(row[0]),
                            interface_id,
                            _measure_from_row(row[1:]),
                        )
                    )

                measures = tuple(row[3] for row in paragraph_interfaces)

                def reconcile_cost(
                    start: int,
                    end: int,
                    aggregate: RegionMeasure,
                ) -> float:
                    del aggregate
                    if end - start <= 1:
                        return 0.0
                    internal_boundaries = end - start - 1
                    exported_pressure = sum(
                        measures[index].boundary_demand_weight
                        for index in range(start, end)
                    )
                    return max(0.0, exported_pressure - internal_boundaries)

                segmentation = bounded_segmentation(
                    measures,
                    profile=profile,
                    reconcile_cost=reconcile_cost,
                )
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
                for segment_ordinal, segment in enumerate(segmentation.segments):
                    members = paragraph_interfaces[segment.start : segment.end]
                    if len(members) <= 1:
                        continue
                    cursor.execute(
                        """
                        SELECT min(start_char), max(end_char)
                          FROM execution.semantic_pnf_region
                         WHERE region_id = ANY(%s)
                        """,
                        ([row[0] for row in members],),
                    )
                    start_char, end_char = cursor.fetchone()
                    adaptive_id = _insert_region(
                        cursor,
                        run_ref=run_ref,
                        document_ref=document_ref,
                        kind=RegionKind.ADAPTIVE_BLOCK,
                        start_char=int(start_char),
                        end_char=int(end_char),
                        sequence_no=segment_ordinal,
                        parent_region_id=document_region_id,
                        authored_boundary=False,
                    )
                    adaptive_count += 1
                    cursor.execute(
                        """
                        UPDATE execution.semantic_pnf_region
                           SET parent_region_id = %s
                         WHERE region_id = ANY(%s)
                        """,
                        (adaptive_id, [row[0] for row in members]),
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
                                member[0],
                                adaptive_id,
                                int(RegionEdgeKind.CONTAINS),
                                ordinal,
                            )
                            for ordinal, member in enumerate(members)
                        ],
                    )
                    _close_parent_interface(
                        cursor,
                        region_id=adaptive_id,
                        profile=profile,
                    )

                document_interface_id = _close_parent_interface(
                    cursor,
                    region_id=document_region_id,
                    profile=profile,
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
                return HierarchySummary(
                    sentence_regions=sentence_count,
                    paragraph_regions=paragraph_count,
                    adaptive_regions=adaptive_regions,
                    interface_count=interface_count,
                    visible_index_rows=visible_rows,
                    segmentation_evaluations=segmentation.evaluated_candidates,
                    segmentation_bound=segmentation.asymptotic_bound,
                    document_interface_id=document_interface_id,
                )
    finally:
        connection.close()


def jump_ancestor(
    cursor: Any,
    *,
    interface_id: int,
    distance: int,
) -> int | None:
    if distance < 0:
        raise ValueError("ancestor distance must be non-negative")
    current = int(interface_id)
    bit = 0
    remaining = distance
    while remaining:
        if remaining & 1:
            cursor.execute(
                """
                SELECT ancestor_interface_id
                  FROM execution.semantic_pnf_interface_ancestor
                 WHERE interface_id = %s
                   AND distance_power = %s
                """,
                (current, bit),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            current = int(row[0])
        remaining >>= 1
        bit += 1
    return current


def nearest_typed_ancestor(
    cursor: Any,
    *,
    interface_id: int,
    region_kind: RegionKind,
) -> int | None:
    cursor.execute(
        """
        SELECT ancestor_interface_id
          FROM execution.semantic_pnf_interface_typed_ancestor
         WHERE interface_id = %s
           AND ancestor_region_kind = %s
        """,
        (interface_id, int(region_kind)),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def lookup_candidates(
    cursor: Any,
    *,
    interface_id: int,
    key_kind: KeyKind,
    key_a: int,
    key_b: int = 0,
    target_kind: TargetKind | None = None,
    limit: int = 16,
) -> tuple[LookupCandidate, ...]:
    """Direct indexed demand lookup followed by already-materialized visibility."""

    if not 1 <= limit <= 256:
        raise ValueError("numeric PNF lookup limit must be between 1 and 256")
    target_filter = (
        "AND target_kind = %s" if target_kind is not None else ""
    )
    parameters: list[Any] = [
        interface_id,
        int(key_kind),
        int(key_a),
        int(key_b),
    ]
    if target_kind is not None:
        parameters.append(int(target_kind))
    parameters.append(limit)
    cursor.execute(
        f"""
        SELECT target_kind, target_id, source_interface_id,
               ancestor_distance, rank
          FROM execution.semantic_pnf_visible_lookup
         WHERE interface_id = %s
           AND key_kind = %s
           AND key_a = %s
           AND key_b = %s
           {target_filter}
         ORDER BY ancestor_distance, rank, target_id
         LIMIT %s
        """,
        tuple(parameters),
    )
    return tuple(
        LookupCandidate(
            target_kind=TargetKind(int(row[0])),
            target_id=int(row[1]),
            source_interface_id=int(row[2]),
            ancestor_distance=int(row[3]),
            rank=int(row[4]),
        )
        for row in cursor.fetchall()
    )


def hyperfabric_counts(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> Mapping[str, int]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            queries = {
                "regions": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_region
                     WHERE run_ref = %s AND document_ref = %s
                """,
                "interfaces": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_interface AS interface
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
                "objects": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_object AS object
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = object.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
                "factors": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_factor AS factor
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = factor.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
                "hyperedges": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_hyperedge AS edge
                      JOIN execution.semantic_pnf_factor AS factor
                        ON factor.factor_id = edge.factor_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = factor.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
                "demands": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_demand AS demand
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = demand.source_region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
                "visible_lookup": """
                    SELECT count(*)
                      FROM execution.semantic_pnf_visible_lookup AS visible
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id = visible.interface_id
                      JOIN execution.semantic_pnf_region AS region
                        ON region.region_id = interface.region_id
                     WHERE region.run_ref = %s
                       AND region.document_ref = %s
                """,
            }
            result: dict[str, int] = {}
            for key, query in queries.items():
                cursor.execute(query, (run_ref, document_ref))
                result[key] = int(cursor.fetchone()[0])
            return result
    finally:
        connection.close()


__all__ = [
    "HierarchySummary",
    "LookupCandidate",
    "WorkLease",
    "authored_paragraphs",
    "claim_work",
    "drain_sentence_closure",
    "hyperfabric_counts",
    "jump_ancestor",
    "lookup_candidates",
    "materialize_document_hierarchy",
    "nearest_typed_ancestor",
    "register_authored_hierarchy",
]
