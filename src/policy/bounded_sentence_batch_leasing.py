"""Lease producer-complete sentence fibres in bounded batches.

This is the runtime specialization of the typed eventual-consistency rule used by
DASHI: batching is permitted here only for physical queue acquisition.  Each
sentence still composes, persists, closes, fails and retries under its existing
individual semantic transaction and lease fence.

The strategy therefore reduces N+1 durable queue orchestration without claiming
that sentence outputs or later adjacent braid obligations share one transaction.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg

from src.pnf.numeric_hyperfabric import ClosureState, WorkOperation, WorkState
from src.storage.postgres.bounded_work_batch import (
    claim_work_batch,
    release_unstarted_leases,
)


_INSTALL_MARKER = "_bounded_sentence_batch_leasing_installed"
_DEFAULT_BATCH_SIZE = 16


def _batch_size() -> int:
    raw = os.environ.get("SENSIBLAW_PNF_LEASE_BATCH_SIZE")
    if raw is None or not raw.strip():
        return _DEFAULT_BATCH_SIZE
    value = int(raw)
    if value < 1:
        raise ValueError("SENSIBLAW_PNF_LEASE_BATCH_SIZE must be positive")
    return value


def _return_current_sentence_lease(cursor: Any, lease: Any) -> None:
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = NULL,
               lease_token = NULL,
               lease_expires_at = NULL,
               last_error_code = 2
         WHERE work_id = %s
           AND lease_token = %s
           AND lease_epoch = %s
        """,
        (
            int(WorkState.READY),
            lease.work_id,
            lease.lease_token,
            lease.lease_epoch,
        ),
    )


def _fail_current_sentence_lease(cursor: Any, lease: Any) -> None:
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


def install_bounded_sentence_batch_leasing() -> bool:
    """Install batch lease acquisition while preserving sentence semantics."""

    from src.storage.postgres import numeric_hyperfabric_store as store
    from src.storage.postgres import streaming_spacy_execution as streaming
    from src.storage.postgres.numeric_sentence_admission import (
        persist_sentence_closure_setwise,
    )

    if getattr(store, _INSTALL_MARKER, False):
        return False

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
        connection = store.connect(database_url)
        try:
            while completed < limit:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        leases = claim_work_batch(
                            cursor,
                            run_ref=run_ref,
                            worker_ref=worker_ref,
                            operation=WorkOperation.SENTENCE_CLOSE,
                            limit=min(_batch_size(), limit - completed),
                        )
                if not leases:
                    break

                retry_after_batch = False
                for index, lease in enumerate(leases):
                    try:
                        with connection.transaction():
                            with connection.cursor() as cursor:
                                tokens = store._load_sentence_tokens(
                                    cursor, lease.region_id
                                )
                                profile = store._load_profile(cursor)
                                lexicon = store._operator_lexicon(cursor, database_url)
                                closure = store.compose_numeric_sentence(
                                    region_id=lease.region_id,
                                    tokens=tokens,
                                    lexicon=lexicon,
                                )
                                persist_sentence_closure_setwise(
                                    cursor,
                                    lease=lease,
                                    closure=closure,
                                    profile=profile,
                                )
                        completed += 1
                    except (
                        psycopg.errors.DeadlockDetected,
                        psycopg.errors.OperationalError,
                    ):
                        with connection.transaction():
                            with connection.cursor() as cursor:
                                _return_current_sentence_lease(cursor, lease)
                                release_unstarted_leases(
                                    cursor, leases[index + 1 :]
                                )
                        retry_after_batch = True
                        break
                    except BaseException:
                        with connection.transaction():
                            with connection.cursor() as cursor:
                                _fail_current_sentence_lease(cursor, lease)
                                release_unstarted_leases(
                                    cursor, leases[index + 1 :]
                                )
                        raise

                if retry_after_batch:
                    continue
        finally:
            connection.close()
        return completed

    # ``streaming_spacy_execution`` imports the function by value, so update both
    # module surfaces.  No second semantic owner is introduced: both names point
    # to the same execution strategy.
    store.drain_sentence_closure = drain_sentence_closure
    streaming.drain_sentence_closure = drain_sentence_closure
    setattr(store, _INSTALL_MARKER, True)
    return True


__all__ = ["install_bounded_sentence_batch_leasing"]
