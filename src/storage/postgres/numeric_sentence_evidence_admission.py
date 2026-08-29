"""Evidence-keyed admission for direct sentence closures.

This keeps the existing set-wise sentence admission as the single persistence owner
while changing only the durable support carrier. Direct execution has evidence ids
in the fields historically named ``*_token_id``; the compatibility reference path
continues to use parser-token ids unchanged.
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


def _rewrite_evidence_support_sql(sql: str) -> str:
    """Rewrite only the two durable support inserts; all other SQL is unchanged."""

    rewritten = sql.replace(_OBJECT_TOKEN_TABLE, _OBJECT_EVIDENCE_TABLE)
    rewritten = rewritten.replace(_FACTOR_TOKEN_TABLE, _FACTOR_EVIDENCE_TABLE)
    if _OBJECT_EVIDENCE_TABLE in rewritten:
        rewritten = rewritten.replace(
            "(object_id, token_id, ordinal)",
            "(object_id, evidence_id, ordinal)",
            1,
        )
    if _FACTOR_EVIDENCE_TABLE in rewritten:
        rewritten = rewritten.replace(
            "(factor_id, token_id, ordinal)",
            "(factor_id, evidence_id, ordinal)",
            1,
        )
    return rewritten


class EvidenceSupportCursor:
    """Cursor facade that changes only token-support persistence into evidence support."""

    __slots__ = ("_cursor",)

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        rewritten = _rewrite_evidence_support_sql(str(query))
        if params is None:
            return self._cursor.execute(rewritten, *args, **kwargs)
        return self._cursor.execute(rewritten, params, *args, **kwargs)

    def executemany(self, query: Any, params_seq: Any, *args: Any, **kwargs: Any) -> Any:
        return self._cursor.executemany(
            _rewrite_evidence_support_sql(str(query)),
            params_seq,
            *args,
            **kwargs,
        )

    def copy(self, query: Any, *args: Any, **kwargs: Any) -> Any:
        return self._cursor.copy(
            _rewrite_evidence_support_sql(str(query)),
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
    """Persist direct closure semantics without any parser-token support relation."""

    return persist_sentence_closure_setwise(
        EvidenceSupportCursor(cursor),
        lease=lease,
        closure=closure,
        profile=profile,
    )


__all__ = [
    "EvidenceSupportCursor",
    "persist_sentence_closure_evidence_setwise",
]
