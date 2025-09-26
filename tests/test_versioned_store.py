"""Tests for the versioned store implementation."""

from datetime import date, datetime
from pathlib import Path
import sys

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import src.pdf_ingest as pdf_ingest
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
        atoms=[
            Atom(
                type="duty",
                text="Perform the first duty",
                refs=["First reference"],
            )
        ],
    )
    second_provision = Provision(
        text="Second provision",
        identifier="s 2",
        atoms=[
            Atom(
                type="duty",
                text="Perform the second duty",
                refs=["Second reference"],
            )
        ],
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
    assert snap.provisions[0].atoms[0].refs == ["First reference"]
    snap2 = store.snapshot(doc_id, date(2022, 1, 1))
    assert snap2.body == "second"
    assert snap2.provisions[0].atoms[0].text == "Perform the second duty"
    assert snap2.provisions[0].atoms[0].refs == ["Second reference"]
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
    assert doc.provisions[0].atoms[0].refs == ["Second reference"]
    store.close()


def test_atom_references_join_table(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            """
            SELECT citation_text
            FROM atom_references
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, atom_id, ref_index
            """,
            (doc_id, 2),
        ).fetchall()
        assert [row["citation_text"] for row in rows] == ["Second reference"]

        store.conn.execute(
            "UPDATE revisions SET document_json = NULL WHERE doc_id = ? AND rev_id = ?",
            (doc_id, 2),
        )
        store.conn.commit()

        snapshot = store.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        atom = snapshot.provisions[0].atoms[0]
        assert atom.refs == ["Second reference"]
    finally:
        store.close()


def test_process_pdf_persists_normalized(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 sample")
    db_path = tmp_path / "store.db"
    output_path = tmp_path / "out.json"

    monkeypatch.setattr(
        pdf_ingest,
        "extract_text",
        lambda _: "1 Heading\nAlice must pay Bob.",
    )
    monkeypatch.setattr(pdf_ingest, "section_parser", None)

    document, stored_doc_id = pdf_ingest.process_pdf(
        pdf_path,
        output=output_path,
        jurisdiction="TestState",
        citation="Test Act",
        db_path=db_path,
    )

    assert stored_doc_id is not None

    store = VersionedStore(str(db_path))
    try:
        provision_rows = store.conn.execute(
            """
            SELECT provision_id, identifier, text
            FROM provisions
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id
            """,
            (stored_doc_id, 1),
        ).fetchall()
        assert provision_rows
        assert provision_rows[0]["identifier"] in {"1", None}

        atom_rows = store.conn.execute(
            """
            SELECT type, text
            FROM atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY atom_id
            """,
            (stored_doc_id, 1),
        ).fetchall()
        assert atom_rows
        assert any(row["type"] == "rule" for row in atom_rows)

        snapshot = store.snapshot(stored_doc_id, document.metadata.date)
        assert snapshot is not None
        assert snapshot.provisions
        assert snapshot.provisions[0].atoms

        # Removing JSON payload should still allow reconstruction from normalized tables.
        store.conn.execute(
            "UPDATE revisions SET document_json = NULL WHERE doc_id = ? AND rev_id = ?",
            (stored_doc_id, 1),
        )
        store.conn.commit()

        snapshot_no_json = store.snapshot(stored_doc_id, document.metadata.date)
        assert snapshot_no_json is not None
        assert snapshot_no_json.provisions
        assert snapshot_no_json.provisions[0].atoms
    finally:
        store.close()
