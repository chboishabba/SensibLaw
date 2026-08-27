"""Atomic tranche scheduling for independent numeric sentence closures.

This is the E0 execution shape: claim several independent sentence-close work
items in one SQL statement, load all typed parser tokens in one query, compose
sentence semantics independently in Python, and admit every closure through the
existing authoritative ``persist_sentence_closure_setwise`` writer inside one
transaction.

Batching changes execution partitioning only.  It does not change the semantic
producer, authority tables, work fences, or sentence-local closure meaning.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.pnf.numeric_hyperfabric import WorkOperation, WorkState
from src.pnf.numeric_operator_composition import NumericToken, compose_numeric_sentence
from src.storage.postgres.numeric_hyperfabric_store import (
    WorkLease,
    _load_profile,
    _operator_lexicon,
)
from src.storage.postgres.numeric_sentence_admission import (
    persist_sentence_closure_setwise,
)
from src.storage.postgres.spacy_parser_model import connect


_STAGE_TABLES = (
    "tmp_numeric_sentence_object",
    "tmp_numeric_sentence_factor",
    "tmp_numeric_sentence_factor_support",
    "tmp_numeric_sentence_factor_slot",
    "tmp_numeric_sentence_demand",
)


@dataclass(frozen=True, slots=True)
class SentenceTrancheClosureReceipt:
    sentence_count: int
    tranche_count: int
    work_claim_batch_count: int
    authority_transaction_count: int
    source_token_batch_load_count: int
    per_sentence_claim_round_trip_count: int
    per_sentence_transaction_count: int


def _claim_sentence_work_tranche(
    cursor: Any,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int,
    lease_seconds: int = 120,
) -> tuple[WorkLease, ...]:
    if limit < 1:
        raise ValueError("sentence tranche limit must be positive")
    if lease_seconds < 1:
        raise ValueError("numeric PNF work lease must be positive")
    token = uuid4().hex
    cursor.execute(
        """
        WITH picked AS (
            SELECT work_id
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
             LIMIT %s
        )
        UPDATE execution.semantic_pnf_work_item AS work
           SET state_id = %s,
               lease_owner = %s,
               lease_token = %s,
               lease_epoch = work.lease_epoch + 1,
               lease_expires_at = CURRENT_TIMESTAMP
                   + (%s * INTERVAL '1 second'),
               attempt_count = work.attempt_count + 1
          FROM picked
         WHERE work.work_id = picked.work_id
        RETURNING work.work_id, work.region_id, work.lease_epoch
        """,
        (
            run_ref,
            int(WorkOperation.SENTENCE_CLOSE),
            int(WorkState.READY),
            int(WorkState.LEASED),
            limit,
            int(WorkState.LEASED),
            worker_ref,
            token,
            lease_seconds,
        ),
    )
    rows = cursor.fetchall()
    return tuple(
        WorkLease(
            work_id=int(work_id),
            region_id=int(region_id),
            operation=WorkOperation.SENTENCE_CLOSE,
            lease_token=token,
            lease_epoch=int(lease_epoch),
        )
        for work_id, region_id, lease_epoch in rows
    )


def _load_sentence_tokens_tranche(
    cursor: Any,
    region_ids: tuple[int, ...],
) -> dict[int, tuple[NumericToken, ...]]:
    if not region_ids:
        return {}
    cursor.execute(
        """
        SELECT link.region_id,
               token.token_id,
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
         WHERE link.region_id = ANY(%s)
           AND token.representation_version = 2
         ORDER BY link.region_id, token.local_token_ordinal, token.token_id
        """,
        (list(region_ids),),
    )
    grouped: dict[int, list[NumericToken]] = defaultdict(list)
    for row in cursor.fetchall():
        region_id = int(row[0])
        if row[7] is None:
            raise RuntimeError(
                "numeric parser token has missing dependency head "
                f"for sentence region {region_id}: token_id={row[1]}"
            )
        grouped[region_id].append(
            NumericToken(
                token_id=int(row[1]),
                orth_id=int(row[2]),
                lemma_id=int(row[3]),
                pos_id=int(row[4]),
                tag_id=int(row[5]),
                dependency_id=int(row[6]),
                head_token_id=int(row[7]),
                morph_set_id=int(row[8]) if row[8] is not None else None,
                start_char=int(row[9]),
                end_char=int(row[10]),
            )
        )
    missing = [region_id for region_id in region_ids if not grouped.get(region_id)]
    if missing:
        raise RuntimeError(
            "numeric sentence tranche contains regions without typed parser tokens: "
            f"count={len(missing)} first={missing[:20]!r}"
        )
    return {region_id: tuple(tokens) for region_id, tokens in grouped.items()}


def _drop_sentence_stage_tables(cursor: Any) -> None:
    # ``persist_sentence_closure_setwise`` owns fixed-name ON COMMIT DROP temp
    # tables.  Recycle them between independent sentences while retaining one
    # outer authority transaction for the whole tranche.
    cursor.execute(
        "DROP TABLE IF EXISTS " + ", ".join(_STAGE_TABLES)
    )


def close_sentence_tranche(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    lease_seconds: int = 120,
) -> SentenceTrancheClosureReceipt:
    """Close at most ``limit`` sentence fibres in one authority transaction."""

    if limit < 1:
        raise ValueError("numeric sentence closure limit must be positive")
    connection = connect(database_url)
    sentence_count = 0
    claimed = False
    token_loaded = False
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                leases = _claim_sentence_work_tranche(
                    cursor,
                    run_ref=run_ref,
                    worker_ref=worker_ref,
                    limit=limit,
                    lease_seconds=lease_seconds,
                )
                if not leases:
                    return SentenceTrancheClosureReceipt(0, 0, 1, 1, 0, 0, 0)
                claimed = True
                tokens_by_region = _load_sentence_tokens_tranche(
                    cursor,
                    tuple(lease.region_id for lease in leases),
                )
                token_loaded = True
                profile = _load_profile(cursor)
                lexicon = _operator_lexicon(cursor, database_url)
                closures = tuple(
                    (
                        lease,
                        compose_numeric_sentence(
                            region_id=lease.region_id,
                            tokens=tokens_by_region[lease.region_id],
                            lexicon=lexicon,
                        ),
                    )
                    for lease in leases
                )
                for index, (lease, closure) in enumerate(closures):
                    if index:
                        _drop_sentence_stage_tables(cursor)
                    persist_sentence_closure_setwise(
                        cursor,
                        lease=lease,
                        closure=closure,
                        profile=profile,
                    )
                    sentence_count += 1
    finally:
        connection.close()
    return SentenceTrancheClosureReceipt(
        sentence_count=sentence_count,
        tranche_count=1 if claimed else 0,
        work_claim_batch_count=1,
        authority_transaction_count=1,
        source_token_batch_load_count=1 if token_loaded else 0,
        per_sentence_claim_round_trip_count=0,
        per_sentence_transaction_count=0,
    )


def drain_sentence_closure_tranches(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    tranche_size: int = 64,
) -> SentenceTrancheClosureReceipt:
    """Drain bounded sentence closure using tranche-sized atomic admissions."""

    if limit < 1 or tranche_size < 1:
        raise ValueError("numeric sentence closure limits must be positive")
    completed = 0
    tranches = 0
    claims = 0
    transactions = 0
    token_loads = 0
    while completed < limit:
        receipt = close_sentence_tranche(
            database_url,
            run_ref=run_ref,
            worker_ref=worker_ref,
            limit=min(tranche_size, limit - completed),
        )
        claims += receipt.work_claim_batch_count
        transactions += receipt.authority_transaction_count
        token_loads += receipt.source_token_batch_load_count
        if receipt.sentence_count == 0:
            break
        completed += receipt.sentence_count
        tranches += receipt.tranche_count
    return SentenceTrancheClosureReceipt(
        sentence_count=completed,
        tranche_count=tranches,
        work_claim_batch_count=claims,
        authority_transaction_count=transactions,
        source_token_batch_load_count=token_loads,
        per_sentence_claim_round_trip_count=0,
        per_sentence_transaction_count=0,
    )


__all__ = [
    "SentenceTrancheClosureReceipt",
    "close_sentence_tranche",
    "drain_sentence_closure_tranches",
]
