"""Canonical durable admission for a DB-free direct sentence closure.

The sentence-local compiler and its semantic digests remain authoritative. This
module performs only publication-time work: resolve local symbol/evidence addresses,
allocate a durable sentence region/work lease, and reuse the canonical set-wise PNF
closure writer with stable source-evidence support.
"""

from __future__ import annotations

from typing import Any
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
    region_digest = numeric_digest(
        b"direct-sentence-region:v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        fibre.sentence_digest,
        fibre.start_char,
        fibre.end_char,
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
            region_digest,
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

    work_digest = numeric_digest(
        b"direct-sentence-work:v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        fibre.sentence_digest,
        int(WorkOperation.SENTENCE_CLOSE),
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
            work_digest,
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


__all__ = ["publish_direct_sentence"]
