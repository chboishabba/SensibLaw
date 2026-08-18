"""Changed-interface final lookup publication for strict numeric execution.

The hierarchy phase remains the authoritative full publication boundary.  This
strategy records that exact row count, records the paragraph pair interface ids
actually completed afterwards, and replaces the final whole-document lookup
rebuild with migration 145's changed-interface projection.

No semantic lookup rule changes.  The existing parser receipt still reports the
exact total global-lookup row count.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any

from src.storage.postgres.spacy_parser_model import connect


_INSTALL_MARKER = "_delta_lookup_publication_execution_installed"
_LOCK = Lock()
_HIERARCHY_LOOKUP_ROWS: dict[tuple[str, str, str], int] = {}
_CHANGED_PARAGRAPH_INTERFACES: dict[tuple[str, str], set[int]] = defaultdict(set)


def _key(database_url: str, run_ref: str, document_ref: str) -> tuple[str, str, str]:
    return (str(database_url), str(run_ref), str(document_ref))


def install_delta_lookup_publication_execution() -> bool:
    from src.storage.postgres import numeric_adjacent_reconciliation as adjacent
    from src.storage.postgres import streaming_spacy_execution as streaming

    if getattr(streaming, _INSTALL_MARKER, False):
        return False

    original_hierarchy = streaming.materialize_numeric_document_hierarchy
    original_drain = adjacent.drain_adjacent_reconciliation

    def materialize_hierarchy(database_url: str, *, run_ref: str, document_ref: str, **kwargs: Any):
        summary = original_hierarchy(
            database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            **kwargs,
        )
        with _LOCK:
            _HIERARCHY_LOOKUP_ROWS[_key(database_url, run_ref, document_ref)] = int(
                summary.visible_index_rows
            )
            _CHANGED_PARAGRAPH_INTERFACES.pop((str(database_url), str(run_ref)), None)
        return summary

    def drain_with_changed_interfaces(
        database_url: str,
        *,
        run_ref: str,
        worker_ref: str,
        limit: int = 64,
    ):
        # Reproduce only the leasing loop needed to retain every concrete pair
        # interface id.  The canonical SQL executor and failure fence remain the
        # authorities for each work item.
        if limit < 1:
            raise ValueError("adjacent reconciliation limit must be positive")

        completed = 0
        last_interface_id: int | None = None
        completed_interfaces: list[int] = []
        connection = connect(database_url)
        try:
            while completed < limit:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        lease = adjacent.claim_work(
                            cursor,
                            run_ref=run_ref,
                            worker_ref=worker_ref,
                            operation=adjacent.WorkOperation.ADJACENT_RECONCILE,
                        )
                if lease is None:
                    break
                try:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            last_interface_id = adjacent.execute_adjacent_lease(cursor, lease)
                    completed_interfaces.append(last_interface_id)
                    completed += 1
                except BaseException:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            adjacent._fail_adjacent_lease(cursor, lease)
                    raise
        finally:
            connection.close()

        if ":adjacent:paragraph" in worker_ref and completed_interfaces:
            with _LOCK:
                _CHANGED_PARAGRAPH_INTERFACES[(str(database_url), str(run_ref))].update(
                    completed_interfaces
                )

        return adjacent.AdjacentReconciliationSummary(
            completed_pairs=completed,
            last_pair_interface_id=last_interface_id,
        )

    def refresh_final_lookup(
        database_url: str,
        *,
        run_ref: str,
        document_ref: str,
    ) -> int:
        state_key = _key(database_url, run_ref, document_ref)
        changed_key = (str(database_url), str(run_ref))
        with _LOCK:
            base_rows = _HIERARCHY_LOOKUP_ROWS.pop(state_key, None)
            changed = tuple(sorted(_CHANGED_PARAGRAPH_INTERFACES.pop(changed_key, set())))

        # If the strategy was installed after hierarchy construction, fail safe
        # to the canonical full refresh rather than inventing a total count.
        if base_rows is None:
            return streaming._canonical_refresh_final_numeric_lookup(
                database_url,
                run_ref=run_ref,
                document_ref=document_ref,
            )
        if not changed:
            return base_rows

        connection = connect(database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT execution.refresh_pnf_global_lookup_interfaces(%s, %s, %s)",
                        (run_ref, document_ref, list(changed)),
                    )
                    row = cursor.fetchone()
                    delta = int(row[0]) if row is not None else 0
        finally:
            connection.close()
        return base_rows + delta

    # Keep an explicit fallback reference before replacing the global used by
    # run_streaming_spacy_execution.
    streaming._canonical_refresh_final_numeric_lookup = streaming._refresh_final_numeric_lookup
    streaming.materialize_numeric_document_hierarchy = materialize_hierarchy
    streaming.drain_adjacent_reconciliation = drain_with_changed_interfaces
    streaming._refresh_final_numeric_lookup = refresh_final_lookup
    setattr(streaming, _INSTALL_MARKER, True)
    return True


__all__ = ["install_delta_lookup_publication_execution"]
