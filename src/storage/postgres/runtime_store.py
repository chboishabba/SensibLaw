"""Revision-aware public PostgreSQL compiler store."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .compiler_store import PersistedCompilation
from .compiler_store import PostgresCompilerStore as _BasePostgresCompilerStore
from .semantic_store import persist_pnf_graph, persist_resolution_artifacts


class PostgresCompilerStore(_BasePostgresCompilerStore):
    """Public store with immutable factor-revision persistence."""

    def persist_pnf_graph(
        self, cursor: Any, *, document_ref: str, graph: Mapping[str, Any]
    ) -> dict[str, str]:
        return persist_pnf_graph(cursor, document_ref=document_ref, graph=graph)

    def persist_resolution_artifacts(
        self,
        cursor: Any,
        *,
        factor_revisions: Mapping[str, str],
        demands: Sequence[Mapping[str, Any]],
        evidence: Sequence[Mapping[str, Any]],
        meets: Sequence[Mapping[str, Any]],
        refinements: Sequence[Mapping[str, Any]],
    ) -> tuple[str, ...]:
        return persist_resolution_artifacts(
            cursor,
            factor_revisions=factor_revisions,
            demands=demands,
            evidence=evidence,
            meets=meets,
            refinements=refinements,
        )


__all__ = ["PersistedCompilation", "PostgresCompilerStore"]
