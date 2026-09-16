from __future__ import annotations

from src.storage.postgres.mabo_radical_title_source import (
    MABO_RADICAL_TITLE_COORDINATE,
    load_mabo_radical_title_payment,
)
from src.storage.postgres.semantic_reader_projection import (
    ReaderIntent,
    compile_reader_intent,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed = (sql, params)

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


def test_radical_title_coordinate_is_source_manifestation_specific() -> None:
    coordinate = MABO_RADICAL_TITLE_COORDINATE

    assert coordinate.case_citation == "Mabo v Queensland (No 2) [1992] HCA 23"
    assert coordinate.clr_locator == "175 CLR 1, 48-49"
    assert coordinate.judge == "Brennan J"
    assert coordinate.source_revision_ref.startswith("source-revision:mabo:1992:hca:23:")
    assert coordinate.span_ref.startswith("span:mabo:brennan:radical-title:")
    assert coordinate.authority_identity_ref == "authority:mabo:1992:hca:23"
    assert coordinate.manifestation_ref != coordinate.authority_identity_ref
    assert coordinate.semantic_truth_paid is False
    assert coordinate.applicability_paid is False


def test_persisted_exact_span_executes_source_but_not_whole_proof_chain() -> None:
    coordinate = MABO_RADICAL_TITLE_COORDINATE
    canonical_text = (
        "Context before. "
        + coordinate.literal_anchor
        + " Context after."
    )
    start = canonical_text.index(coordinate.literal_anchor)
    end = start + len(coordinate.literal_anchor)
    cursor = _Cursor(
        (
            coordinate.source_revision_ref,
            coordinate.document_ref,
            "text/plain",
            "a" * 64,
            canonical_text,
            coordinate.span_ref,
            start,
            end,
            "authority_passage",
            "primary",
        )
    )

    payment = load_mabo_radical_title_payment(cursor)

    assert payment.exact_authority_span_paid is True
    assert payment.literal_span == coordinate.literal_anchor
    assert payment.proposition_chain_paid is False
    assert payment.claim_truth_paid is False
    assert compile_reader_intent(payment, ReaderIntent.OPEN_SOURCE).state == "execute"
    assert compile_reader_intent(payment, ReaderIntent.WHY).state == "defer"
    assert cursor.executed is not None
    assert cursor.executed[1] == (
        coordinate.span_ref,
        coordinate.source_revision_ref,
    )


def test_missing_persisted_span_stays_deferred() -> None:
    coordinate = MABO_RADICAL_TITLE_COORDINATE
    payment = load_mabo_radical_title_payment(_Cursor(None))

    assert payment.exact_authority_span_paid is False
    decision = compile_reader_intent(payment, ReaderIntent.OPEN_SOURCE)
    assert decision.state == "defer"
    assert decision.residual_ref == "reader-residual:exact-authority-span"
