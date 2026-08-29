"""Admit already-resolved direct sentence closures.

Partition publication resolves symbols/evidence set-wise before entering this seam.
Sentence region/work fencing remains canonical, while durable graph admission reuses
the existing set-wise owner with evidence support instead of parser-token support.
"""

from __future__ import annotations

from typing import Any

from src.pnf.direct_sentence_publication import DirectPublicationReceipt
from src.pnf.numeric_hyperfabric import MdlProfile
from src.pnf.packed_sentence_fibre import PackedSentenceFibre
from src.storage.postgres.direct_sentence_admission import (
    _lease_sentence_work,
    _register_sentence_work,
)
from src.storage.postgres.numeric_hyperfabric_store import WorkLease
from src.storage.postgres.numeric_sentence_evidence_admission import (
    persist_sentence_closure_evidence_setwise,
)


def publish_preleased_resolved_direct_sentence(
    cursor: Any,
    *,
    lease: WorkLease,
    publication: DirectPublicationReceipt,
    profile: MdlProfile,
) -> int:
    """Admit one pre-resolved closure using an already-created sentence fence.

    Partition projection has no ancestor consumer between sentence admission and the
    hierarchy publication barrier. Migrations 143/194 permit these intermediate
    projections to be deferred, while migration 142 owns the exact set-wise final
    document projection.
    """

    if publication.parser_token_writes != 0:
        raise RuntimeError("direct publication unexpectedly declared parser-token writes")
    return persist_sentence_closure_evidence_setwise(
        cursor,
        lease=lease,
        closure=publication.closure,
        profile=profile,
        defer_interface_ancestors=True,
    )


def publish_resolved_direct_sentence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibre: PackedSentenceFibre,
    publication: DirectPublicationReceipt,
    profile: MdlProfile,
) -> int:
    """Admit one pre-resolved sentence through canonical set-wise persistence."""

    if publication.parser_token_writes != 0:
        raise RuntimeError("direct publication unexpectedly declared parser-token writes")
    region_id, work_id = _register_sentence_work(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        fibre=fibre,
    )
    lease = _lease_sentence_work(cursor, region_id=region_id, work_id=work_id)
    return publish_preleased_resolved_direct_sentence(
        cursor,
        lease=lease,
        publication=publication,
        profile=profile,
    )


__all__ = [
    "publish_preleased_resolved_direct_sentence",
    "publish_resolved_direct_sentence",
]
