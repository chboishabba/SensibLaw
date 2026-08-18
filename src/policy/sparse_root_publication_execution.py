"""Preserve the root-only sparse publication boundary after paragraph adjacency.

Migrations 062/068/071 make the closed document frontier the only visible/global
lookup authority. Paragraph-adjacency fibres are overlapping residual/evidence
carriers: their executor records checked evidence but does not mutate demand
resolution or the canonical parent frontier.

The hierarchy phase has already reduced canonical frontiers, refreshed proof
relevant derivations and published the exact root-visible row count. Under that
current semantic contract, the later ``refresh_pnf_global_lookup`` call can only
re-publish the same root interface. This execution strategy retains the exact
hierarchy count and makes that second publication zero work.

If the wrapper is installed after hierarchy construction and therefore lacks the
root-count certificate, it fails safe to the canonical refresh.
"""

from __future__ import annotations

from threading import Lock
from typing import Any


_INSTALL_MARKER = "_sparse_root_publication_execution_installed"
_LOCK = Lock()
_ROOT_VISIBLE_ROWS: dict[tuple[str, str, str], int] = {}


def _key(database_url: str, run_ref: str, document_ref: str) -> tuple[str, str, str]:
    return (str(database_url), str(run_ref), str(document_ref))


def install_sparse_root_publication_execution() -> bool:
    from src.storage.postgres import streaming_spacy_execution as streaming

    if getattr(streaming, _INSTALL_MARKER, False):
        return False

    original_hierarchy = streaming.materialize_numeric_document_hierarchy
    canonical_final_refresh = streaming._refresh_final_numeric_lookup

    def materialize_hierarchy(
        database_url: str,
        *,
        run_ref: str,
        document_ref: str,
        **kwargs: Any,
    ):
        summary = original_hierarchy(
            database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            **kwargs,
        )
        with _LOCK:
            _ROOT_VISIBLE_ROWS[_key(database_url, run_ref, document_ref)] = int(
                summary.visible_index_rows
            )
        return summary

    def refresh_final_lookup(
        database_url: str,
        *,
        run_ref: str,
        document_ref: str,
    ) -> int:
        state_key = _key(database_url, run_ref, document_ref)
        with _LOCK:
            root_rows = _ROOT_VISIBLE_ROWS.pop(state_key, None)
        if root_rows is None:
            return canonical_final_refresh(
                database_url,
                run_ref=run_ref,
                document_ref=document_ref,
            )
        return root_rows

    streaming.materialize_numeric_document_hierarchy = materialize_hierarchy
    streaming._refresh_final_numeric_lookup = refresh_final_lookup
    setattr(streaming, _INSTALL_MARKER, True)
    return True


__all__ = ["install_sparse_root_publication_execution"]
