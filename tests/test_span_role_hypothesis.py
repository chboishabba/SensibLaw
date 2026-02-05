from __future__ import annotations

from datetime import date

from src.ingestion.span_role_hypotheses import build_span_role_hypotheses
from src.models.document import Document, DocumentMetadata
from src.storage import VersionedStore


def _make_document() -> Document:
    meta = DocumentMetadata(
        jurisdiction="AU",
        citation="Test Act",
        date=date(2020, 1, 1),
        title="Test Act",
    )
    body = (
        'In this Act, "Employee" means a person. '
        'In this Act, “Employer” means a company.'
    )
    return Document(meta, body)


def test_span_role_hypotheses_regenerate(tmp_path) -> None:
    store = VersionedStore(tmp_path / "span_role.sqlite")
    try:
        doc = _make_document()
        doc_id = store.generate_id()
        rev_id = store.add_revision(doc_id, doc, doc.metadata.date)

        hypotheses = build_span_role_hypotheses(doc)
        stored = store.replace_span_role_hypotheses(doc_id, rev_id, hypotheses)
        assert stored == 2

        first = store.list_span_role_hypotheses(doc_id, rev_id)
        assert first
        assert (
            doc.body[first[0].span_start:first[0].span_end]
            == first[0].metadata.get("term_text")
        )

        snapshot = store.snapshot(doc_id, doc.metadata.date)
        assert snapshot is not None
        rebuilt = build_span_role_hypotheses(snapshot)

        store.replace_span_role_hypotheses(doc_id, rev_id, [])
        store.replace_span_role_hypotheses(doc_id, rev_id, rebuilt)

        second = store.list_span_role_hypotheses(doc_id, rev_id)
        assert [item.to_record() for item in first] == [
            item.to_record() for item in second
        ]
    finally:
        store.close()
