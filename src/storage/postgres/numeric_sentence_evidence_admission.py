"""Evidence-keyed admission for direct sentence closures.

This keeps the existing set-wise sentence admission as the single persistence owner
while changing only the durable support carrier. Direct execution has evidence ids
in the fields historically named ``*_token_id``; the compatibility reference path
continues to use parser-token ids unchanged.

The direct cursor is also an authority boundary: legacy parser-token projection may
exist for reference/parity execution, but direct publication must neither read nor
write ``semantic_parser_token`` and must never persist the legacy token-support
relations. Violations fail closed before reaching PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from src.pnf.numeric_hyperfabric import MdlProfile
from src.pnf.numeric_operator_composition import NumericSentenceClosure
from src.storage.postgres.numeric_hyperfabric_store import WorkLease
from src.storage.postgres.numeric_sentence_admission import (
    persist_sentence_closure_setwise,
)


_OBJECT_TOKEN_TABLE = "execution.semantic_pnf_object_token_support"
_FACTOR_TOKEN_TABLE = "execution.semantic_pnf_factor_token_support"
_OBJECT_EVIDENCE_TABLE = "execution.semantic_pnf_object_evidence_support"
_FACTOR_EVIDENCE_TABLE = "execution.semantic_pnf_factor_evidence_support"
_PARSER_TOKEN_TABLE = "execution.semantic_parser_token"
_LEGACY_OCCURRENCE_TABLE = "execution.semantic_pnf_demand_occurrence_provenance"
_OBJECT_INSERT = f"INSERT INTO {_OBJECT_TOKEN_TABLE}"
_FACTOR_INSERT = f"INSERT INTO {_FACTOR_TOKEN_TABLE}"


class DirectProvenanceViolation(RuntimeError):
    """Direct publication attempted to cross into legacy parser-token authority."""


def _rewrite_evidence_support_sql(sql: str) -> str:
    """Translate only the two durable support INSERT targets.

    Local temp-stage columns intentionally keep compatibility names such as
    ``token_id``; on the direct path those values are stable evidence ids.  Do not
    globally replace support relation names because provenance/diagnostic SELECTs
    must remain visible to the direct authority guard rather than being silently
    mutated into malformed evidence SQL.
    """

    rewritten = sql
    if _OBJECT_INSERT in rewritten:
        rewritten = rewritten.replace(
            _OBJECT_INSERT, f"INSERT INTO {_OBJECT_EVIDENCE_TABLE}", 1
        )
        rewritten = rewritten.replace(
            "(object_id, token_id, ordinal)",
            "(object_id, evidence_id, ordinal)",
            1,
        )
    if _FACTOR_INSERT in rewritten:
        rewritten = rewritten.replace(
            _FACTOR_INSERT, f"INSERT INTO {_FACTOR_EVIDENCE_TABLE}", 1
        )
        rewritten = rewritten.replace(
            "(factor_id, token_id, ordinal)",
            "(factor_id, evidence_id, ordinal)",
            1,
        )
    return rewritten


def _direct_authority_sql(sql: str) -> str:
    """Translate support INSERTs and reject every remaining legacy dependency."""

    rewritten = _rewrite_evidence_support_sql(sql)
    lowered = rewritten.lower()
    forbidden = (
        _PARSER_TOKEN_TABLE,
        _OBJECT_TOKEN_TABLE,
        _FACTOR_TOKEN_TABLE,
        _LEGACY_OCCURRENCE_TABLE,
    )
    crossed = next((table for table in forbidden if table in lowered), None)
    if crossed is not None:
        compact = " ".join(rewritten.split())
        if len(compact) > 320:
            compact = compact[:317] + "..."
        raise DirectProvenanceViolation(
            "direct evidence publication crossed legacy provenance authority: "
            f"{crossed}; sql={compact!r}"
        )
    return rewritten


class EvidenceSupportCursor:
    """Cursor facade enforcing evidence-only durable provenance for direct mode."""

    __slots__ = ("_cursor",)
    uses_source_evidence_provenance = True

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        rewritten = _direct_authority_sql(str(query))
        if params is None:
            return self._cursor.execute(rewritten, *args, **kwargs)
        return self._cursor.execute(rewritten, params, *args, **kwargs)

    def executemany(
        self, query: Any, params_seq: Any, *args: Any, **kwargs: Any
    ) -> Any:
        return self._cursor.executemany(
            _direct_authority_sql(str(query)),
            params_seq,
            *args,
            **kwargs,
        )

    def copy(self, query: Any, *args: Any, **kwargs: Any) -> Any:
        return self._cursor.copy(
            _direct_authority_sql(str(query)),
            *args,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def persist_sentence_closure_evidence_setwise(
    cursor: Any,
    *,
    lease: WorkLease,
    closure: NumericSentenceClosure,
    profile: MdlProfile,
) -> int:
    """Persist direct closure semantics without any parser-token provenance."""

    return persist_sentence_closure_setwise(
        EvidenceSupportCursor(cursor),
        lease=lease,
        closure=closure,
        profile=profile,
    )


__all__ = [
    "DirectProvenanceViolation",
    "EvidenceSupportCursor",
    "persist_sentence_closure_evidence_setwise",
]
