"""Admit an already-resolved direct sentence closure.

Partition publication resolves symbols/evidence set-wise before entering this seam.
The existing sentence region/work fencing and canonical closure writer remain the
single durable admission authority.
"""

from __future__ import annotations

from typing import Any

from src.pnf.direct_sentence_publication import DirectPublicationReceipt
from src.pnf.numeric_hyperfabric import MdlProfile
from src.pnf.packed_sentence_fibre import PackedSentenceFibre
from src.storage.postgres.direct_sentence_admission import (
    _EvidenceSupportCursor,
    _lease_sentence_work,
    _register_sentence_work,
)
from src.storage.postgres.numeric_hyperfabric_store import _persist_sentence_closure


def publish_resolved_direct_sentence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibre: PackedSentenceFibre,
    publication: DirectPublicationReceipt,
    profile: MdlProfile,
) -> int:
    """Admit one pre-resolved sentence without repeating identity/profile queries."""

    if publication.parser_token_writes != 0:
        raise RuntimeError("direct publication unexpectedly declared parser-token writes")
    region_id, work_id = _register_sentence_work(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        fibre=fibre,
    )
    lease = _lease_sentence_work(cursor, region_id=region_id, work_id=work_id)
    return _persist_sentence_closure(
        _EvidenceSupportCursor(cursor),
        lease=lease,
        closure=publication.closure,
        profile=profile,
    )


__all__ = ["publish_resolved_direct_sentence"]
