from __future__ import annotations

from datetime import date
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.reports.research_health import compute_research_health
from src.storage.versioned_store import VersionedStore


def _make_doc(citation: str, body: str) -> Document:
    metadata = DocumentMetadata(
        jurisdiction="au",
        citation=citation,
        date=date(2024, 1, 1),
        title=citation,
    )
    return Document(metadata=metadata, body=body)


def test_research_health_counts_and_resolution(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        doc1 = _make_doc("[1992] HCA 23", "Doc text with [1992] HCA 23 and [2000] HCA 1.")
        doc2 = _make_doc("[2000] HCA 1", "Second doc without new cites.")

        id1 = store.generate_id()
        store.add_revision(id1, doc1, doc1.metadata.date)
        id2 = store.generate_id()
        store.add_revision(id2, doc2, doc2.metadata.date)
    finally:
        store.close()

    report = compute_research_health(db)
    assert report.documents == 2
    assert report.citations_total == 2  # both citations from doc1
    assert report.citations_unresolved == 0  # both citations match stored docs
    assert report.unresolved_percent == 0.0
    assert report.citations_per_doc_mean == round(report.citations_total / report.documents, 2)
    assert report.compression_ratio_mean > 0
    assert report.tokens_per_document_mean == 7.5


def test_research_health_empty_store(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    db.touch()
    report = compute_research_health(db)
    assert report.documents == 0
    assert report.citations_total == 0
    assert report.citations_unresolved == 0
    assert report.compression_ratio_mean == 0.0
    assert report.tokens_per_document_mean == 0.0
