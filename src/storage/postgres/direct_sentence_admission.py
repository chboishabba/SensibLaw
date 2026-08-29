"""Canonical durable admission for a DB-free direct sentence closure.

The sentence-local compiler and its semantic digests remain authoritative. This
module performs only publication-time work: resolve local symbol/evidence addresses,
allocate durable sentence region/work leases, and reuse the canonical set-wise PNF
closure writer with stable source-evidence support.
"""

from __future__ import annotations

from typing import Any, Sequence
from uuid import uuid4

from src.pnf.direct_sentence_compiler import DirectSentenceCompileReceipt
from src.pnf.direct_sentence_publication import resolve_direct_publication
from src.pnf.numeric_hyperfabric import (
    ClosureState,
    RegionEdgeKind,
    RegionKind,
    WorkOperation,
    WorkState,
    numeric_digest,
)
from src.pnf.packed_sentence_fibre import PackedSentenceFibre
from src.storage.postgres.numeric_hyperfabric_store import WorkLease, _load_profile
from src.storage.postgres.numeric_sentence_evidence_admission import (
    persist_sentence_closure_evidence_setwise,
)


def _parent_region_id(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    start_char: int,
) -> int | None:
    cursor.execute(
        """
        SELECT region_id
          FROM execution.semantic_pnf_region
         WHERE run_ref = %s
           AND document_ref = %s
           AND region_kind IN (%s, %s, %s, %s, %s, %s)
           AND start_char <= %s
           AND end_char > %s
         ORDER BY
           CASE region_kind
               WHEN %s THEN 1
               WHEN %s THEN 2
               WHEN %s THEN 3
               WHEN %s THEN 4
               WHEN %s THEN 5
               ELSE 6
           END,
           end_char - start_char
         LIMIT 1
        """,
        (
            run_ref,
            document_ref,
            int(RegionKind.PARAGRAPH),
            int(RegionKind.ADAPTIVE_BLOCK),
            int(RegionKind.PROVISION),
            int(RegionKind.SECTION),
            int(RegionKind.CHAPTER),
            int(RegionKind.DOCUMENT),
            start_char,
            start_char,
            int(RegionKind.PARAGRAPH),
            int(RegionKind.ADAPTIVE_BLOCK),
            int(RegionKind.PROVISION),
            int(RegionKind.SECTION),
            int(RegionKind.CHAPTER),
        ),
    )
    row = cursor.fetchone()
    return int(row[0]) if row is not None else None


def _region_digest(*, run_ref: str, document_ref: str, fibre: PackedSentenceFibre) -> bytes:
    return numeric_digest(
        b"direct-sentence-region:v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        fibre.sentence_digest,
        fibre.start_char,
        fibre.end_char,
    )


def _work_digest(*, run_ref: str, document_ref: str, fibre: PackedSentenceFibre) -> bytes:
    return numeric_digest(
        b"direct-sentence-work:v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        fibre.sentence_digest,
        int(WorkOperation.SENTENCE_CLOSE),
    )


def _register_sentence_work(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibre: PackedSentenceFibre,
) -> tuple[int, int]:
    parent_region_id = _parent_region_id(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        start_char=fibre.start_char,
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_region
            (region_digest, run_ref, document_ref, region_kind,
             start_char, end_char, sequence_no, parent_region_id,
             closure_state, authored_boundary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        ON CONFLICT (run_ref, document_ref, region_kind, start_char, end_char)
        DO UPDATE SET
            parent_region_id = COALESCE(
                execution.semantic_pnf_region.parent_region_id,
                EXCLUDED.parent_region_id
            )
        RETURNING region_id
        """,
        (
            _region_digest(run_ref=run_ref, document_ref=document_ref, fibre=fibre),
            run_ref,
            document_ref,
            int(RegionKind.SENTENCE),
            fibre.start_char,
            fibre.end_char,
            fibre.ordinal,
            parent_region_id,
            int(ClosureState.OPEN),
        ),
    )
    region_id = int(cursor.fetchone()[0])
    if parent_region_id is not None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_region_edge
                (source_region_id, target_region_id, edge_kind, ordinal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                region_id,
                parent_region_id,
                int(RegionEdgeKind.CONTAINS),
                fibre.ordinal,
            ),
        )

    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_work_item
            (work_digest, run_ref, document_ref, region_id,
             operation_id, state_id, priority)
        VALUES (%s, %s, %s, %s, %s, %s, 10)
        ON CONFLICT (region_id, operation_id) DO UPDATE SET
            state_id = CASE
                WHEN execution.semantic_pnf_work_item.state_id = %s THEN %s
                ELSE execution.semantic_pnf_work_item.state_id
            END
        RETURNING work_id
        """,
        (
            _work_digest(run_ref=run_ref, document_ref=document_ref, fibre=fibre),
            run_ref,
            document_ref,
            region_id,
            int(WorkOperation.SENTENCE_CLOSE),
            int(WorkState.READY),
            int(WorkState.FAILED),
            int(WorkState.READY),
        ),
    )
    return region_id, int(cursor.fetchone()[0])


def _lease_sentence_work(cursor: Any, *, region_id: int, work_id: int) -> WorkLease:
    lease_token = uuid4().hex
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = 'direct-sentence-publication',
               lease_token = %s,
               lease_epoch = lease_epoch + 1,
               lease_expires_at = CURRENT_TIMESTAMP + INTERVAL '120 seconds',
               attempt_count = attempt_count + 1
         WHERE work_id = %s
           AND state_id IN (%s, %s)
        RETURNING lease_epoch
        """,
        (
            int(WorkState.LEASED),
            lease_token,
            work_id,
            int(WorkState.READY),
            int(WorkState.FAILED),
        ),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("direct sentence work could not be leased")
    return WorkLease(
        work_id=work_id,
        region_id=region_id,
        operation=WorkOperation.SENTENCE_CLOSE,
        lease_token=lease_token,
        lease_epoch=int(row[0]),
    )


def register_and_lease_sentence_work_batch(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibres: Sequence[PackedSentenceFibre],
) -> tuple[WorkLease, ...]:
    """Register and lease every sentence in one partition with bounded SQL calls.

    Sentence regions/work items remain individually durable.  The physical control
    plane is partition-wide: one parent lookup relation, one region upsert, one edge
    insert, one work upsert and one lease update rather than that sequence per sentence.
    """

    fibres = tuple(fibres)
    if not fibres:
        return ()

    starts = [int(f.start_char) for f in fibres]
    ends = [int(f.end_char) for f in fibres]
    ordinals = [int(f.ordinal) for f in fibres]
    region_digests = [
        _region_digest(run_ref=run_ref, document_ref=document_ref, fibre=f)
        for f in fibres
    ]

    cursor.execute(
        """
        WITH input AS (
            SELECT *
              FROM UNNEST(
                    %s::bytea[], %s::integer[], %s::integer[], %s::integer[]
              ) AS x(region_digest, start_char, end_char, sequence_no)
        ), parented AS (
            SELECT input.*,
                   (
                       SELECT region.region_id
                         FROM execution.semantic_pnf_region AS region
                        WHERE region.run_ref = %s
                          AND region.document_ref = %s
                          AND region.region_kind IN (%s, %s, %s, %s, %s, %s)
                          AND region.start_char <= input.start_char
                          AND region.end_char > input.start_char
                        ORDER BY
                          CASE region.region_kind
                              WHEN %s THEN 1
                              WHEN %s THEN 2
                              WHEN %s THEN 3
                              WHEN %s THEN 4
                              WHEN %s THEN 5
                              ELSE 6
                          END,
                          region.end_char - region.start_char
                        LIMIT 1
                   ) AS parent_region_id
              FROM input
        )
        INSERT INTO execution.semantic_pnf_region
            (region_digest, run_ref, document_ref, region_kind,
             start_char, end_char, sequence_no, parent_region_id,
             closure_state, authored_boundary)
        SELECT parented.region_digest, %s, %s, %s,
               parented.start_char, parented.end_char, parented.sequence_no,
               parented.parent_region_id, %s, FALSE
          FROM parented
        ON CONFLICT (run_ref, document_ref, region_kind, start_char, end_char)
        DO UPDATE SET
            parent_region_id = COALESCE(
                execution.semantic_pnf_region.parent_region_id,
                EXCLUDED.parent_region_id
            )
        RETURNING region_id, start_char, end_char, sequence_no, parent_region_id
        """,
        (
            region_digests,
            starts,
            ends,
            ordinals,
            run_ref,
            document_ref,
            int(RegionKind.PARAGRAPH),
            int(RegionKind.ADAPTIVE_BLOCK),
            int(RegionKind.PROVISION),
            int(RegionKind.SECTION),
            int(RegionKind.CHAPTER),
            int(RegionKind.DOCUMENT),
            int(RegionKind.PARAGRAPH),
            int(RegionKind.ADAPTIVE_BLOCK),
            int(RegionKind.PROVISION),
            int(RegionKind.SECTION),
            int(RegionKind.CHAPTER),
            run_ref,
            document_ref,
            int(RegionKind.SENTENCE),
            int(ClosureState.OPEN),
        ),
    )
    region_rows = cursor.fetchall()
    by_span = {
        (int(start), int(end)): (int(region_id), int(parent) if parent is not None else None)
        for region_id, start, end, _sequence_no, parent in region_rows
    }
    if len(by_span) != len(fibres):
        raise RuntimeError("direct partition sentence-region registration was incomplete")

    edge_rows = [
        (by_span[(f.start_char, f.end_char)][0], by_span[(f.start_char, f.end_char)][1], f.ordinal)
        for f in fibres
        if by_span[(f.start_char, f.end_char)][1] is not None
    ]
    if edge_rows:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_region_edge
                (source_region_id, target_region_id, edge_kind, ordinal)
            SELECT x.source_region_id, x.target_region_id, %s, x.ordinal
              FROM UNNEST(%s::bigint[], %s::bigint[], %s::integer[])
                   AS x(source_region_id, target_region_id, ordinal)
            ON CONFLICT DO NOTHING
            """,
            (
                int(RegionEdgeKind.CONTAINS),
                [row[0] for row in edge_rows],
                [row[1] for row in edge_rows],
                [row[2] for row in edge_rows],
            ),
        )

    region_ids = [by_span[(f.start_char, f.end_char)][0] for f in fibres]
    work_digests = [
        _work_digest(run_ref=run_ref, document_ref=document_ref, fibre=f)
        for f in fibres
    ]
    cursor.execute(
        """
        WITH input AS (
            SELECT * FROM UNNEST(%s::bytea[], %s::bigint[])
                 AS x(work_digest, region_id)
        )
        INSERT INTO execution.semantic_pnf_work_item
            (work_digest, run_ref, document_ref, region_id,
             operation_id, state_id, priority)
        SELECT input.work_digest, %s, %s, input.region_id, %s, %s, 10
          FROM input
        ON CONFLICT (region_id, operation_id) DO UPDATE SET
            state_id = CASE
                WHEN execution.semantic_pnf_work_item.state_id = %s THEN %s
                ELSE execution.semantic_pnf_work_item.state_id
            END
        RETURNING work_id, region_id
        """,
        (
            work_digests,
            region_ids,
            run_ref,
            document_ref,
            int(WorkOperation.SENTENCE_CLOSE),
            int(WorkState.READY),
            int(WorkState.FAILED),
            int(WorkState.READY),
        ),
    )
    work_by_region = {int(region_id): int(work_id) for work_id, region_id in cursor.fetchall()}
    if len(work_by_region) != len(region_ids):
        raise RuntimeError("direct partition sentence-work registration was incomplete")

    lease_tokens = [uuid4().hex for _ in fibres]
    work_ids = [work_by_region[region_id] for region_id in region_ids]
    cursor.execute(
        """
        WITH input AS (
            SELECT * FROM UNNEST(%s::bigint[], %s::text[])
                 AS x(work_id, lease_token)
        )
        UPDATE execution.semantic_pnf_work_item AS work
           SET state_id = %s,
               lease_owner = 'direct-partition-publication',
               lease_token = input.lease_token,
               lease_epoch = work.lease_epoch + 1,
               lease_expires_at = CURRENT_TIMESTAMP + INTERVAL '120 seconds',
               attempt_count = work.attempt_count + 1
          FROM input
         WHERE work.work_id = input.work_id
           AND work.state_id IN (%s, %s)
        RETURNING work.work_id, work.region_id, work.lease_token, work.lease_epoch
        """,
        (
            work_ids,
            lease_tokens,
            int(WorkState.LEASED),
            int(WorkState.READY),
            int(WorkState.FAILED),
        ),
    )
    leased = {
        int(work_id): WorkLease(
            work_id=int(work_id),
            region_id=int(region_id),
            operation=WorkOperation.SENTENCE_CLOSE,
            lease_token=str(lease_token),
            lease_epoch=int(lease_epoch),
        )
        for work_id, region_id, lease_token, lease_epoch in cursor.fetchall()
    }
    if len(leased) != len(work_ids):
        raise RuntimeError("direct partition sentence work could not be leased set-wise")
    return tuple(leased[work_id] for work_id in work_ids)


def publish_direct_sentence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibre: PackedSentenceFibre,
    direct: DirectSentenceCompileReceipt,
) -> int:
    """Admit one direct sentence closure with zero parser-token support writes."""

    publication = resolve_direct_publication(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        fibre=fibre,
        direct=direct,
    )
    if publication.parser_token_writes != 0:
        raise RuntimeError("direct publication unexpectedly declared parser-token writes")
    region_id, work_id = _register_sentence_work(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        fibre=fibre,
    )
    lease = _lease_sentence_work(cursor, region_id=region_id, work_id=work_id)
    profile = _load_profile(cursor)
    return persist_sentence_closure_evidence_setwise(
        cursor,
        lease=lease,
        closure=publication.closure,
        profile=profile,
    )


__all__ = [
    "publish_direct_sentence",
    "register_and_lease_sentence_work_batch",
]
