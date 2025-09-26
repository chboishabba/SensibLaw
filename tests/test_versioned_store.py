from datetime import date, datetime
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.models.provision import Atom, Provision
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
        canonical_id="canon-123",
    )
    first_provision = Provision(
        text="First provision",
        identifier="s 1",
        atoms=[Atom(type="duty", text="Perform the first duty")],
    )
    second_provision = Provision(
        text="Second provision",
        identifier="s 2",
        atoms=[Atom(type="duty", text="Perform the second duty")],
    )
    store.add_revision(
        doc_id,
        Document(meta, "first", provisions=[first_provision]),
        date(2020, 1, 1),
    )
    store.add_revision(
        doc_id,
        Document(meta, "second", provisions=[second_provision]),
        date(2021, 1, 1),
    )
    return store, doc_id


def test_snapshot(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    snap = store.snapshot(doc_id, date(2020, 6, 1))
    assert snap is not None
    assert snap.body == "first"
    assert snap.provisions
    assert snap.provisions[0].atoms[0].text == "Perform the first duty"
    snap2 = store.snapshot(doc_id, date(2022, 1, 1))
    assert snap2.body == "second"
    assert snap2.provisions[0].atoms[0].text == "Perform the second duty"
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
    assert snap.provisions[0].text == "Second provision"
    store.close()


def test_get_by_canonical_id(tmp_path: Path):
    store, _ = make_store(tmp_path)
    doc = store.get_by_canonical_id("canon-123")
    assert doc is not None
    assert doc.body == "second"
    assert doc.provisions[0].atoms[0].text == "Perform the second duty"
    store.close()
