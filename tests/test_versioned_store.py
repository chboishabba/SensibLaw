from datetime import date, datetime
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.storage import VersionedStore


def make_store(tmp_path: Path) -> tuple[VersionedStore, int]:
    db_path = tmp_path / "store.db"
    store = VersionedStore(str(db_path))
    doc_id = store.generate_id()
    meta = DocumentMetadata(
        jurisdiction="US",
        citation="123",
        date=date(2020, 1, 1),
        source_url="http://example.com",
        retrieved_at=datetime(2020, 1, 2, 3, 4, 5),
        checksum="abc123",
        licence="CC-BY",
    )
    store.add_revision(doc_id, Document(meta, "first"), date(2020, 1, 1))
    store.add_revision(doc_id, Document(meta, "second"), date(2021, 1, 1))
    return store, doc_id


def test_snapshot(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    snap = store.snapshot(doc_id, date(2020, 6, 1))
    assert snap is not None
    assert snap.body == "first"
    snap2 = store.snapshot(doc_id, date(2022, 1, 1))
    assert snap2.body == "second"
    store.close()


def test_diff(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    diff = store.diff(doc_id, 1, 2)
    assert "-first" in diff
    assert "+second" in diff
    store.close()


def test_provenance_metadata(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    snap = store.snapshot(doc_id, date(2022, 1, 1))
    assert snap is not None
    meta = snap.metadata
    assert meta.source_url == "http://example.com"
    assert meta.retrieved_at == datetime(2020, 1, 2, 3, 4, 5)
    assert meta.checksum == "abc123"
    assert meta.licence == "CC-BY"
    store.close()
