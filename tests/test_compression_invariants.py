from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.models.document import Document, DocumentMetadata
from src.storage.versioned_store import VersionedStore
from src.text.tokenize_simple import count_tokens

pdfminer = pytest.importorskip("pdfminer.high_level")


def _latest_bodies(store: VersionedStore) -> dict[int, str]:
    rows = store.conn.execute(
        """
        SELECT r.doc_id, r.body
        FROM revisions r
        JOIN (
            SELECT doc_id, MAX(rev_id) AS rev_id
            FROM revisions
            GROUP BY doc_id
        ) latest ON r.doc_id = latest.doc_id AND r.rev_id = latest.rev_id
        ORDER BY r.doc_id
        """
    ).fetchall()
    return {int(row["doc_id"]): row["body"] or "" for row in rows}


def _token_counts(store: VersionedStore) -> dict[int, int]:
    return {doc_id: count_tokens(body) for doc_id, body in _latest_bodies(store).items()}


def _extract_pdf_text(path: Path, *, limit: int = 6000) -> str:
    text = pdfminer.extract_text(path)
    return (text or "")[:limit].strip()


def test_reingesting_same_document_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        meta = DocumentMetadata(
            jurisdiction="au",
            citation="[1992] HCA 23",
            date=date(1992, 1, 1),
            title="House v The King",
        )
        body = "Authoritative text with repeated citation [1992] HCA 23."
        doc_id = store.generate_id()
        store.add_revision(doc_id, Document(meta, body), meta.date)

        first_counts = _token_counts(store)

        # Re-ingest identical bytes as a new revision should not change latest token count.
        store.add_revision(
            doc_id,
            Document(meta, body),
            meta.date + timedelta(days=1),
        )
        second_counts = _token_counts(store)
    finally:
        store.close()

    assert first_counts == second_counts


def test_overlapping_documents_growth_is_sublinear(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        meta_a = DocumentMetadata(
            jurisdiction="au",
            citation="[1992] HCA 23",
            date=date(1992, 6, 3),
            title="Mabo (No 2)",
        )
        meta_b = DocumentMetadata(
            jurisdiction="au",
            citation="[1993] HCA 10",
            date=date(1993, 3, 10),
            title="Overlap Case",
        )
        shared = "native title land rights crown sovereignty doctrine "
        body_a = f"{shared}torres strait customary law judgment"
        body_b = f"{shared}judgment"

        id_a = store.generate_id()
        store.add_revision(id_a, Document(meta_a, body_a), meta_a.date)
        tokens_a = count_tokens(body_a)

        id_b = store.generate_id()
        store.add_revision(id_b, Document(meta_b, body_b), meta_b.date)
        counts = _token_counts(store)
    finally:
        store.close()

    delta = sum(counts.values()) - tokens_a
    assert delta < 0.7 * tokens_a
    assert counts[id_b] > 0


def test_pdf_fixture_overlap_growth_is_sublinear(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    fixture_dir = Path(__file__).resolve().parents[1]
    pdf_path = fixture_dir / "Mabo [No 2] - [1992] HCA 23.pdf"
    if not pdf_path.exists():
        pytest.skip("Mabo fixture PDF not found")

    try:
        text = _extract_pdf_text(pdf_path, limit=8000)
        assert text, "Expected extracted text from PDF fixture"

        meta_a = DocumentMetadata(
            jurisdiction="au",
            citation="[1992] HCA 23",
            date=date(1992, 6, 3),
            title="Mabo (No 2)",
        )
        body_a = text

        meta_b = DocumentMetadata(
            jurisdiction="au",
            citation="[1992] HCA 23 overlap excerpt",
            date=date(1992, 6, 3),
            title="Mabo (No 2) excerpt",
        )
        body_b = text[:2000] + " additional reasoning context"

        id_a = store.generate_id()
        store.add_revision(id_a, Document(meta_a, body_a), meta_a.date)
        tokens_a = count_tokens(body_a)

        id_b = store.generate_id()
        store.add_revision(id_b, Document(meta_b, body_b), meta_b.date)
        counts = _token_counts(store)
    finally:
        store.close()

    delta = sum(counts.values()) - tokens_a
    assert delta < 0.5 * tokens_a
    assert counts[id_b] > 0


def test_following_citation_does_not_mutate_existing_tokens(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        meta_a = DocumentMetadata(
            jurisdiction="au",
            citation="[2000] HCA 1",
            date=date(2000, 1, 1),
            title="Primary Case",
        )
        body_a = "Primary case with citation [1999] HCA 50 for later follow up."
        doc_id_a = store.generate_id()
        store.add_revision(doc_id_a, Document(meta_a, body_a), meta_a.date)

        hash_before = hashlib.sha256(_latest_bodies(store)[doc_id_a].encode("utf-8")).hexdigest()

        # Follow citation → ingest referenced authority.
        meta_b = DocumentMetadata(
            jurisdiction="au",
            citation="[1999] HCA 50",
            date=date(1999, 12, 1),
            title="Followed Authority",
        )
        body_b = "Followed authority full text."
        store.add_revision(store.generate_id(), Document(meta_b, body_b), meta_b.date)

        hash_after = hashlib.sha256(_latest_bodies(store)[doc_id_a].encode("utf-8")).hexdigest()
    finally:
        store.close()

    assert hash_before == hash_after
