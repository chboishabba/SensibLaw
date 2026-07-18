"""Revision-aware public PostgreSQL compiler store."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256

from .compiler_store import PersistedCompilation
from .compiler_store import PostgresCompilerStore as _BasePostgresCompilerStore
from .semantic_store import persist_pnf_graph, persist_resolution_artifacts


class PostgresCompilerStore(_BasePostgresCompilerStore):
    """Public store with immutable factor-revision persistence."""

    def persist_tokens(
        self,
        cursor: Any,
        *,
        document_ref: str,
        tokenizer_ref: str,
        tokenizer_version: str,
        tokens: Sequence[tuple[str, int, int]],
        language_ref: str = "und",
        lexical_kind_ref: str = "surface",
    ) -> str:
        if tokens:
            return super().persist_tokens(
                cursor,
                document_ref=document_ref,
                tokenizer_ref=tokenizer_ref,
                tokenizer_version=tokenizer_version,
                tokens=tokens,
                language_ref=language_ref,
                lexical_kind_ref=lexical_kind_ref,
            )
        run_ref = "tokenizer-run:" + canonical_sha256(
            {
                "document_ref": document_ref,
                "tokenizer_ref": tokenizer_ref,
                "tokenizer_version": tokenizer_version,
                "tokens": (),
            }
        )
        cursor.execute(
            """
            INSERT INTO language.tokenizer_run
                (tokenizer_run_ref, document_ref, tokenizer_ref,
                 tokenizer_version, token_count, output_sha256)
            VALUES (%s, %s, %s, %s, 0, %s)
            ON CONFLICT (tokenizer_run_ref) DO NOTHING
            """,
            (
                run_ref,
                document_ref,
                tokenizer_ref,
                tokenizer_version,
                bytes.fromhex(canonical_sha256({"tokens": ()})),
            ),
        )
        return run_ref

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
