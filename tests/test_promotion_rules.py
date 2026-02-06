from __future__ import annotations

from datetime import date

from src.ingestion.promotion_rules import PromotionConfig, evaluate_promotions
from src.ingestion.span_role_hypotheses import build_span_role_hypotheses
from src.models.document import Document, DocumentMetadata
from src.models.span_signal_hypothesis import SpanSignalHypothesis
from src.storage import VersionedStore


def _make_document() -> Document:
    meta = DocumentMetadata(
        jurisdiction="AU",
        citation="Promotion Act",
        date=date(2020, 1, 1),
        title="Promotion Act",
    )
    body = 'In this Act, "Employee" means a person. The Employee must comply.'
    return Document(meta, body)


def _span_source(doc: Document) -> str:
    return doc.metadata.canonical_id or doc.metadata.citation or "unknown"


def test_evaluate_promotions_defined_term() -> None:
    doc = _make_document()
    hypotheses = build_span_role_hypotheses(doc)
    candidates, receipts = evaluate_promotions(doc, hypotheses)
    assert candidates, "expected at least one promotion candidate"
    assert receipts, "expected promotion receipts"
    assert candidates[0].gate_id == "defined_term"
    assert any(receipt.status == "promoted" for receipt in receipts)


def test_signal_blocks_promotion() -> None:
    doc = _make_document()
    hypotheses = build_span_role_hypotheses(doc)
    signal = SpanSignalHypothesis(
        span_start=hypotheses[0].span_start,
        span_end=hypotheses[0].span_end,
        span_source=_span_source(doc),
        signal_type="ocr_uncertain",
    )
    _candidates, receipts = evaluate_promotions(doc, hypotheses, [signal])
    assert any(receipt.status == "blocked" for receipt in receipts)


def test_promotion_receipts_storage(tmp_path) -> None:
    store = VersionedStore(tmp_path / "promo.sqlite")
    try:
        doc = _make_document()
        doc_id = store.generate_id()
        rev_id = store.add_revision(doc_id, doc, doc.metadata.date)

        hypotheses = build_span_role_hypotheses(doc)
        _candidates, receipts = evaluate_promotions(
            doc,
            hypotheses,
            config=PromotionConfig(min_repetition=2),
        )
        stored = store.replace_promotion_receipts(doc_id, rev_id, receipts)
        assert stored == len(receipts)

        loaded = store.list_promotion_receipts(doc_id, rev_id)
        assert [r.gate_id for r in loaded] == [r.gate_id for r in receipts]
    finally:
        store.close()
