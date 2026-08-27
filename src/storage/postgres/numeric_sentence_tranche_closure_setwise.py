"""E0b sentence closure scheduler using fixed-family tranche admission.

This module deliberately reuses the already-certified E0 batch claim and token
load helpers.  It changes only the persistence call: the composed independent
sentence closures are admitted together by ``persist_sentence_tranche_setwise``.
"""

from __future__ import annotations

from src.pnf.numeric_operator_composition import compose_numeric_sentence
from src.storage.postgres.numeric_hyperfabric_store import _load_profile, _operator_lexicon
from src.storage.postgres.numeric_sentence_tranche_admission import (
    persist_sentence_tranche_setwise,
)
from src.storage.postgres.numeric_sentence_tranche_closure import (
    SentenceTrancheClosureReceipt,
    _claim_sentence_work_tranche,
    _load_sentence_tokens_tranche,
)
from src.storage.postgres.spacy_parser_model import connect


def close_sentence_tranche_setwise(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    lease_seconds: int = 120,
) -> SentenceTrancheClosureReceipt:
    """Close one independent sentence tranche with fixed-per-family SQL work."""

    if limit < 1:
        raise ValueError("numeric sentence closure limit must be positive")
    connection = connect(database_url)
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
                tokens_by_region = _load_sentence_tokens_tranche(
                    cursor,
                    tuple(lease.region_id for lease in leases),
                )
                profile = _load_profile(cursor)
                lexicon = _operator_lexicon(cursor, database_url)
                admissions = tuple(
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
                receipt = persist_sentence_tranche_setwise(
                    cursor,
                    admissions=admissions,
                    profile=profile,
                )
                if receipt.sentence_count != len(leases):
                    raise RuntimeError("sentence tranche admission count changed")
                return SentenceTrancheClosureReceipt(
                    sentence_count=receipt.sentence_count,
                    tranche_count=1,
                    work_claim_batch_count=1,
                    authority_transaction_count=1,
                    source_token_batch_load_count=1,
                    per_sentence_claim_round_trip_count=0,
                    per_sentence_transaction_count=0,
                )
    finally:
        connection.close()


def drain_sentence_closure_tranches_setwise(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    tranche_size: int = 64,
) -> SentenceTrancheClosureReceipt:
    """Drain sentence closure through E0b fixed-family tranche admissions."""

    if limit < 1 or tranche_size < 1:
        raise ValueError("numeric sentence closure limits must be positive")
    completed = tranches = claims = transactions = token_loads = 0
    while completed < limit:
        receipt = close_sentence_tranche_setwise(
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
        tranches += 1
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
    "close_sentence_tranche_setwise",
    "drain_sentence_closure_tranches_setwise",
]
