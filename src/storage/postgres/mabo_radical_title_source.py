"""Exact Mabo radical-title source coordinate for the Semantic Reader.

The coordinate names one narrow passage in Brennan J's reasons.  PostgreSQL
remains the persistence/source-of-bytes owner; this module only binds stable
reader coordinates to the existing PG source-payment projection.

The archived manifestation is kept distinct from the legal authority identity.
Opening this exact span does not by itself pay applicability, the wider Mabo
proof chain, or legal truth.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from src.storage.postgres.semantic_reader_projection import (
    ReaderSourcePayment,
    load_reader_source_payment,
)


@dataclass(frozen=True)
class MaboRadicalTitleCoordinate:
    case_citation: str
    clr_locator: str
    judge: str
    authority_identity_ref: str
    manifestation_ref: str
    source_revision_ref: str
    document_ref: str
    span_ref: str
    literal_anchor: str
    manifestation_url: str
    upstream_source_url: str
    manifestation_kind: str
    source_role: str
    authority_level: str
    semantic_truth_paid: bool = False
    applicability_paid: bool = False
    proposition_chain_paid: bool = False


MABO_RADICAL_TITLE_COORDINATE = MaboRadicalTitleCoordinate(
    case_citation="Mabo v Queensland (No 2) [1992] HCA 23",
    clr_locator="175 CLR 1, 48-49",
    judge="Brennan J",
    authority_identity_ref="authority:mabo:1992:hca:23",
    manifestation_ref="manifestation:mabo:1992:hca:23:wikisource:page-39",
    source_revision_ref=(
        "source-revision:mabo:1992:hca:23:wikisource:page-39:2026-06-22"
    ),
    document_ref="document:mabo:1992:hca:23:brennan:wikisource-page-39",
    span_ref="span:mabo:brennan:radical-title:no-automatic-beneficial-ownership",
    literal_anchor=(
        "the radical title which is acquired with the acquisition of sovereignty "
        "cannot itself be taken to confer an absolute beneficial title"
    ),
    manifestation_url=(
        "https://en.wikisource.org/wiki/"
        "Page:Mabo_v_Queensland_(No_2)_(1992_HCA_23).pdf/39"
    ),
    upstream_source_url=(
        "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCASCF/1992/116.html"
    ),
    manifestation_kind="proofread_transcription_of_judgment_scan",
    source_role="judgment",
    authority_level="primary",
)


def load_mabo_radical_title_payment(cursor: Any) -> ReaderSourcePayment:
    """Load and verify the one paid radical-title source span from PostgreSQL.

    The generic reader projection checks same-document coordinates and valid
    character bounds.  This narrower owner also checks the expected literal
    anchor so a stale/wrong span row fails closed instead of paying the reader.
    """

    coordinate = MABO_RADICAL_TITLE_COORDINATE
    payment = load_reader_source_payment(
        cursor,
        source_revision_ref=coordinate.source_revision_ref,
        span_ref=coordinate.span_ref,
    )
    if not payment.exact_authority_span_paid:
        return payment
    if payment.literal_span != coordinate.literal_anchor:
        return replace(
            payment,
            exact_authority_span_paid=False,
            literal_span=None,
        )
    return payment


__all__ = [
    "MABO_RADICAL_TITLE_COORDINATE",
    "MaboRadicalTitleCoordinate",
    "load_mabo_radical_title_payment",
]
