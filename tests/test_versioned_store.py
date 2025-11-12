"""Tests for the versioned store implementation."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
import sys

import pytest

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import src.pdf_ingest as pdf_ingest
from src.models.document import Document, DocumentMetadata, DocumentTOCEntry
from src.models.provision import (
    Atom,
    GlossaryLink,
    Provision,
    RuleAtom,
    RuleElement,
    RuleLint,
    RuleReference,
)
from src.models.sentence import Sentence
from src.storage import VersionedStore
from src.storage.versioned_store import PayloadTooLargeError


def index_columns(conn, index_name: str) -> list[str]:
    """Return the ordered column names for a SQLite index."""

    rows = conn.execute(f"PRAGMA index_xinfo('{index_name}')").fetchall()
    return [row["name"] for row in rows if row["cid"] >= 0]


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
        heading="First heading",
        node_type="section",
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
        heading="Second heading",
        node_type="section",
        atoms=[
            Atom(
                type="duty",
                text="Perform the second duty",
                refs=["Second reference"],
            )
        ],
    )
    toc_entry = DocumentTOCEntry(
        node_type="section",
        identifier="s 2",
        title="Second heading",
        page_number=42,
    )
    store.add_revision(
        doc_id,
        Document(meta, "first", provisions=[first_provision]),
        date(2020, 1, 1),
    )
    store.add_revision(
        doc_id,
        Document(
            meta,
            "second",
            provisions=[second_provision],
            toc_entries=[toc_entry],
        ),
        date(2021, 1, 1),
    )
    return store, doc_id


def _make_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        jurisdiction="AU",
        citation="Citation",
        date=date(2024, 1, 1),
    )


def test_add_revision_respects_body_limit(tmp_path: Path) -> None:
    store = VersionedStore(
        str(tmp_path / "store.db"),
        max_body_size=8,
    )
    try:
        doc_id = store.generate_id()
        metadata = _make_metadata()
        document = Document(
            metadata,
            "x" * 9,
            sentences=[Sentence(text="stub", start_char=0, end_char=0, index=0)],
        )
        with pytest.raises(PayloadTooLargeError, match="body payload"):
            store.add_revision(doc_id, document, metadata.date)
    finally:
        store.close()


def test_add_revision_respects_metadata_limit(tmp_path: Path) -> None:
    store = VersionedStore(
        str(tmp_path / "store.db"),
        max_metadata_size=10,
    )
    try:
        doc_id = store.generate_id()
        metadata = _make_metadata()
        document = Document(
            metadata,
            "short body",
            sentences=[Sentence(text="stub", start_char=0, end_char=0, index=0)],
        )
        with pytest.raises(PayloadTooLargeError, match="metadata payload"):
            store.add_revision(doc_id, document, metadata.date)
    finally:
        store.close()


def test_add_revision_respects_document_json_limit(tmp_path: Path) -> None:
    store = VersionedStore(
        str(tmp_path / "store.db"),
        max_document_size=10,
    )
    try:
        doc_id = store.generate_id()
        metadata = _make_metadata()
        document = Document(
            metadata,
            "short body",
            sentences=[Sentence(text="stub", start_char=0, end_char=0, index=0)],
        )
        with pytest.raises(PayloadTooLargeError, match="document JSON payload"):
            store.add_revision(doc_id, document, metadata.date)
    finally:
        store.close()


def test_snapshot(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    snap = store.snapshot(doc_id, date(2020, 6, 1))
    assert snap is not None
    assert snap.body == "first"
    assert snap.provisions
    assert snap.provisions[0].atoms[0].text == "Perform the first duty"
    assert snap.provisions[0].atoms[0].refs == ["First reference"]
    assert snap.provisions[0].toc_id is not None
    snap2 = store.snapshot(doc_id, date(2022, 1, 1))
    assert snap2.body == "second"
    assert snap2.provisions[0].atoms[0].text == "Perform the second duty"
    assert snap2.provisions[0].atoms[0].refs == ["Second reference"]
    assert snap2.provisions[0].toc_id is not None
    assert snap2.provisions[0].rule_atoms[0].toc_id == snap2.provisions[0].toc_id
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


def test_list_latest_documents(tmp_path: Path) -> None:
    store, doc_id = make_store(tmp_path)
    try:
        documents = store.list_latest_documents()
        assert len(documents) == 1
        summary = documents[0]
        assert summary["doc_id"] == doc_id
        assert summary["rev_id"] == 2
        assert summary["effective_date"] == date(2021, 1, 1)
        metadata = summary["metadata"]
        assert metadata.citation == "123"
        assert metadata.jurisdiction == "US"
    finally:
        store.close()


def test_atom_references_join_table(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            """
            SELECT citation_text
            FROM rule_atom_references
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id, ref_index
            """,
            (doc_id, 2),
        ).fetchall()
        assert [row["citation_text"] for row in rows] == ["Second reference"]

        snapshot = store.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        atom = snapshot.provisions[0].atoms[0]
        assert atom.refs == ["Second reference"]
    finally:
        store.close()


def test_rule_atom_subjects_persisted(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            """
            SELECT type, role, party, who, who_text, text, gloss
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id
            """,
            (doc_id, 2),
        ).fetchall()
        assert rows, "expected subject aggregation rows"
        row = rows[0]
        assert row["type"] == "duty"
        assert row["role"] is None
        assert row["who_text"] is None
        assert row["text"] == "Perform the second duty"
        assert row["gloss"] is None
    finally:
        store.close()


def test_provision_and_rule_atom_fts(tmp_path: Path) -> None:
    store, doc_id = make_store(tmp_path)
    try:
        provision_rows = store.conn.execute(
            """
            SELECT provision_id
            FROM provision_text_fts
            WHERE doc_id = ? AND rev_id = ? AND provision_text_fts MATCH ?
            ORDER BY provision_id
            """,
            (doc_id, 2, "second"),
        ).fetchall()
        assert provision_rows
        assert [row["provision_id"] for row in provision_rows] == [1]

        atom_rows = store.conn.execute(
            """
            SELECT rule_id
            FROM rule_atom_text_fts
            WHERE doc_id = ? AND rev_id = ? AND rule_atom_text_fts MATCH ?
            ORDER BY rule_id
            """,
            (doc_id, 2, "second"),
        ).fetchall()
        assert atom_rows
        assert [row["rule_id"] for row in atom_rows] == [1]
    finally:
        store.close()


def test_rule_atom_subjects_loaded(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        snapshot = store.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        provision = snapshot.provisions[0]
        assert provision.rule_atoms, "expected structured rule atoms"
        rule_atom = provision.rule_atoms[0]
        assert rule_atom.subject is not None
        assert rule_atom.subject.text == "Perform the second duty"
        assert rule_atom.subject.type == "duty"
        assert rule_atom.toc_id == provision.toc_id
        assert provision.atoms[0].text == "Perform the second duty"
    finally:
        store.close()


def test_rule_atom_indexes_include_rule_id(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    try:
        index_rows = store.conn.execute("PRAGMA index_list('rule_atoms')").fetchall()
        index_names = {row["name"] for row in index_rows}
        assert "idx_rule_atoms_doc_rev" in index_names
        assert index_columns(store.conn, "idx_rule_atoms_doc_rev") == [
            "doc_id",
            "rev_id",
            "provision_id",
            "rule_id",
        ]
    finally:
        store.close()


def test_rule_atom_subject_indexes_include_rule_id(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    try:
        index_rows = store.conn.execute("PRAGMA index_list('rule_atom_subjects')").fetchall()
        index_names = {row["name"] for row in index_rows}
        assert "idx_rule_atom_subjects_doc_rev" in index_names
        assert index_columns(store.conn, "idx_rule_atom_subjects_doc_rev") == [
            "doc_id",
            "rev_id",
            "provision_id",
            "rule_id",
        ]
    finally:
        store.close()


def test_rule_element_indexes_include_element_id(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    try:
        index_rows = store.conn.execute("PRAGMA index_list('rule_elements')").fetchall()
        index_names = {row["name"] for row in index_rows}
        assert "idx_rule_elements_doc_rev" in index_names
        assert index_columns(store.conn, "idx_rule_elements_doc_rev") == [
            "doc_id",
            "rev_id",
            "provision_id",
            "rule_id",
            "element_id",
        ]
    finally:
        store.close()


def test_atoms_view_created_for_new_store(tmp_path: Path):
    db_path = tmp_path / "store.db"
    store = VersionedStore(str(db_path))
    try:
        row = store.conn.execute(
            "SELECT type FROM sqlite_master WHERE name = 'atoms'"
        ).fetchone()
        assert row is not None
        assert row["type"] == "view"
    finally:
        store.close()


def test_revisions_table_excludes_document_json(tmp_path: Path) -> None:
    store = VersionedStore(str(tmp_path / "schema.db"))
    try:
        columns = {
            row["name"]
            for row in store.conn.execute("PRAGMA table_info(revisions)")
        }
        assert "document_json" not in columns
    finally:
        store.close()


def test_migration_script_removes_document_json(tmp_path: Path) -> None:
    store, doc_id = make_store(tmp_path)
    db_path = tmp_path / "store.db"
    store.close()

    legacy_conn = sqlite3.connect(str(db_path))
    legacy_conn.row_factory = sqlite3.Row
    with legacy_conn:
        legacy_conn.execute("ALTER TABLE revisions ADD COLUMN document_json TEXT")
        legacy_conn.execute(
            "UPDATE revisions SET document_json = '{}' WHERE doc_id = ?",
            (doc_id,),
        )

    from scripts.migrate_drop_document_json import drop_document_json_column

    dropped = drop_document_json_column(legacy_conn)
    assert dropped

    columns = {
        row["name"]
        for row in legacy_conn.execute("PRAGMA table_info(revisions)")
    }
    assert "document_json" not in columns
    legacy_conn.close()

    reopened = VersionedStore(str(db_path))
    try:
        snapshot = reopened.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        assert snapshot.provisions
    finally:
        reopened.close()


def test_toc_join(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            """
            SELECT p.provision_id, p.identifier, p.toc_id, t.title, t.position
            FROM provisions AS p
            JOIN toc AS t
              ON p.doc_id = t.doc_id
             AND p.rev_id = t.rev_id
             AND p.toc_id = t.toc_id
            WHERE p.doc_id = ? AND p.rev_id = ?
            ORDER BY p.provision_id
            """,
            (doc_id, 2),
        ).fetchall()
        assert rows, "expected provisions joined to toc"
        assert [row["identifier"] for row in rows] == ["s 2"]
        assert rows[0]["position"] == 1

        rule_rows = store.conn.execute(
            """
            SELECT DISTINCT toc_id
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY toc_id
            """,
            (doc_id, 2),
        ).fetchall()
        assert {row["toc_id"] for row in rule_rows} == {rows[0]["toc_id"]}
    finally:
        store.close()


def test_glossary_references_persist(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        with store.conn:
            cur = store.conn.execute(
                "INSERT INTO glossary(term, definition, metadata) VALUES (?, ?, ?)",
                ("Example term", "Example definition", None),
            )
        glossary_id = cur.lastrowid
        assert glossary_id is not None

        meta = DocumentMetadata(
            jurisdiction="US",
            citation="123",
            date=date(2022, 2, 1),
            source_url="http://example.com",
            retrieved_at=datetime(2020, 1, 2, 3, 4, 5),
            checksum="abc123",
            licence="CC-BY",
            canonical_id="canon-123",
        )

        shared_link = GlossaryLink(text="Example term", glossary_id=glossary_id)

        subject_atom = Atom(
            type="rule",
            text="Example subject",
            refs=[],
            glossary=shared_link,
        )

        rule_atom = RuleAtom(
            subject=subject_atom,
            subject_link=shared_link,
            references=[],
            elements=[
                RuleElement(
                    text="Element referencing term",
                    glossary=shared_link,
                    references=[],
                )
            ],
        )

        provision = Provision(
            text="Provision with glossary",
            identifier="s 3",
            heading="Third heading",
            node_type="section",
            rule_atoms=[rule_atom],
        )

        new_rev = store.add_revision(
            doc_id,
            Document(meta, "third", provisions=[provision]),
            date(2022, 2, 1),
        )

        atom_rows = store.conn.execute(
            """
            SELECT rar.glossary_id, g.term
            FROM rule_atom_references AS rar
            JOIN glossary AS g ON g.id = rar.glossary_id
            WHERE rar.doc_id = ? AND rar.rev_id = ?
            ORDER BY rar.ref_index
            """,
            (doc_id, new_rev),
        ).fetchall()
        assert atom_rows, "expected glossary-backed atom reference"
        assert {row["glossary_id"] for row in atom_rows} == {glossary_id}

        element_rows = store.conn.execute(
            """
            SELECT rer.glossary_id, g.term
            FROM rule_element_references AS rer
            JOIN glossary AS g ON g.id = rer.glossary_id
            WHERE rer.doc_id = ? AND rer.rev_id = ?
            ORDER BY rer.element_id, rer.ref_index
            """,
            (doc_id, new_rev),
        ).fetchall()
        assert element_rows, "expected glossary-backed element reference"
        assert {row["glossary_id"] for row in element_rows} == {glossary_id}

        snapshot = store.snapshot(doc_id, date(2022, 2, 2))
        assert snapshot is not None
        provision_snapshot = snapshot.provisions[0]
        rule_atom_snapshot = provision_snapshot.rule_atoms[0]
        assert any(
            ref.glossary_id == glossary_id for ref in rule_atom_snapshot.references
        )
        assert rule_atom_snapshot.elements
        assert any(
            ref.glossary_id == glossary_id
            for ref in rule_atom_snapshot.elements[0].references
        )
    finally:
        store.close()


def test_repeated_rule_ingestion_updates_existing_rows(tmp_path: Path) -> None:
    store = VersionedStore(str(tmp_path / "store.db"))
    try:
        doc_id = store.generate_id()
        metadata = DocumentMetadata(
            jurisdiction="AU",
            citation="[2024] ABC 1",
            date=date(2024, 1, 1),
            source_url="http://example.com",
            checksum="checksum",
            licence="CC",
            canonical_id="canon-upsert",
        )
        subject_link = GlossaryLink(
            text="Initial gloss",
            metadata={"stage": "initial"},
            glossary_id=3,
        )
        subject = Atom(
            type="rule",
            role="initial-role",
            party="Initial party",
            who="Initial who",
            who_text="Initial who text",
            conditions="Initial conditions",
            text="Initial subject text",
            refs=["Initial ref"],
            glossary=subject_link,
        )
        initial_rule_atom = RuleAtom(
            atom_type="rule",
            role="initial-role",
            party="Initial party",
            who="Initial who",
            who_text="Initial who text",
            actor="Initial actor",
            modality="must",
            action="Initial action",
            conditions="Initial conditions",
            scope="Initial scope",
            text="Initial rule text",
            subject=subject,
            subject_link=subject_link,
            references=[RuleReference(citation_text="Initial citation")],
            elements=[
                RuleElement(
                    role="initial element",
                    text="Initial element text",
                    conditions="Initial element conditions",
                    glossary=GlossaryLink(
                        text="Initial element gloss",
                        metadata={"stage": "initial"},
                        glossary_id=5,
                    ),
                    references=[
                        RuleReference(citation_text="Initial element citation")
                    ],
                    atom_type="requirement",
                )
            ],
            lints=[
                RuleLint(
                    atom_type="rule",
                    code="initial",
                    message="Initial lint",
                    metadata={"severity": "low"},
                )
            ],
        )
        provision = Provision(
            text="Provision body",
            identifier="s 1",
            heading="Heading",
            node_type="section",
            rule_atoms=[initial_rule_atom],
            atoms=[subject],
        )
        document = Document(metadata, "Body text", provisions=[provision])

        rev_id = store.add_revision(doc_id, document, date(2024, 1, 1))

        provision_id = store.conn.execute(
            "SELECT provision_id FROM provisions WHERE doc_id = ? AND rev_id = ? LIMIT 1",
            (doc_id, rev_id),
        ).fetchone()[0]
        toc_id = store.conn.execute(
            "SELECT toc_id FROM toc WHERE doc_id = ? AND rev_id = ? LIMIT 1",
            (doc_id, rev_id),
        ).fetchone()[0]
        initial_hash = store.conn.execute(
            """
            SELECT text_hash
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()[0]
        initial_element_hash = store.conn.execute(
            """
            SELECT text_hash
            FROM rule_elements
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1 AND element_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()[0]

        updated_subject_link = GlossaryLink(
            text="Updated gloss",
            metadata={"stage": "updated"},
            glossary_id=11,
        )
        updated_subject = Atom(
            type="rule",
            role="updated-role",
            party="Updated party",
            who="Updated who",
            who_text="Updated who text",
            conditions="Updated subject conditions",
            text="Updated subject text",
            refs=["Updated subject ref"],
            glossary=updated_subject_link,
        )
        updated_rule_atom = RuleAtom(
            toc_id=toc_id,
            atom_type="rule",
            role="updated-role",
            party="Updated party",
            who="Updated who",
            who_text="Updated who text",
            actor="Updated actor",
            modality="may",
            action="Updated action",
            conditions="Updated rule conditions",
            scope="Updated scope",
            text="Updated rule text",
            subject=updated_subject,
            subject_link=updated_subject_link,
            references=[
                RuleReference(
                    work="Updated Work",
                    section="S2",
                    pinpoint="p.5",
                    citation_text="Updated citation",
                )
            ],
            elements=[
                RuleElement(
                    role="updated element",
                    text="Updated element text",
                    conditions="Updated element conditions",
                    glossary=GlossaryLink(
                        text="Updated element gloss",
                        metadata={"stage": "updated"},
                        glossary_id=13,
                    ),
                    references=[
                        RuleReference(
                            work="Elem Work",
                            section="1",
                            pinpoint="p.10",
                            citation_text="Updated element citation",
                        )
                    ],
                    atom_type="requirement",
                )
            ],
            lints=[
                RuleLint(
                    atom_type="rule",
                    code="updated",
                    message="Updated lint message",
                    metadata={"severity": "high"},
                )
            ],
        )

        with store.conn:
            store._persist_rule_structures(
                doc_id, rev_id, provision_id, [updated_rule_atom], toc_id
            )

        rule_row = store.conn.execute(
            """
            SELECT modality, action, scope, text, text_hash, subject_gloss, subject_gloss_metadata
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert rule_row["modality"] == "may"
        assert rule_row["action"] == "Updated action"
        assert rule_row["scope"] == "Updated scope"
        assert rule_row["text"] == "Updated subject text"
        assert rule_row["text_hash"] != initial_hash
        assert rule_row["subject_gloss"] == "Updated gloss"
        assert json.loads(rule_row["subject_gloss_metadata"]) == {"stage": "updated"}

        subject_row = store.conn.execute(
            """
            SELECT text, refs, gloss, gloss_metadata, glossary_id
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert subject_row["text"] == "Updated subject text"
        assert json.loads(subject_row["refs"]) == ["Updated subject ref"]
        assert subject_row["gloss"] == "Updated gloss"
        assert json.loads(subject_row["gloss_metadata"]) == {"stage": "updated"}
        assert subject_row["glossary_id"] == 11

        ref_row = store.conn.execute(
            """
            SELECT work, section, pinpoint, citation_text
            FROM rule_atom_references
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1 AND ref_index = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert ref_row["work"] == "Updated Work"
        assert ref_row["section"] == "S2"
        assert ref_row["pinpoint"] == "p.5"
        assert ref_row["citation_text"] == "Updated citation"

        element_row = store.conn.execute(
            """
            SELECT text, conditions, gloss, text_hash
            FROM rule_elements
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1 AND element_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert element_row["text"] == "Updated element text"
        assert element_row["conditions"] == "Updated element conditions"
        assert element_row["gloss"] == "Updated element gloss"
        assert element_row["text_hash"] != initial_element_hash

        element_ref_row = store.conn.execute(
            """
            SELECT work, section, pinpoint, citation_text
            FROM rule_element_references
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
              AND rule_id = 1 AND element_id = 1 AND ref_index = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert element_ref_row["work"] == "Elem Work"
        assert element_ref_row["section"] == "1"
        assert element_ref_row["pinpoint"] == "p.10"
        assert element_ref_row["citation_text"] == "Updated element citation"

        lint_row = store.conn.execute(
            """
            SELECT code, message, metadata
            FROM rule_lints
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = 1 AND lint_id = 1
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()
        assert lint_row["code"] == "updated"
        assert lint_row["message"] == "Updated lint message"
        assert json.loads(lint_row["metadata"]) == {"severity": "high"}

        atom_count = store.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
            """,
            (doc_id, rev_id, provision_id),
        ).fetchone()["count"]
        assert atom_count == 1
    finally:
        store.close()


def test_toc_page_numbers_persisted(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            "SELECT page_number FROM toc WHERE doc_id = ? AND rev_id = ? ORDER BY toc_id",
            (doc_id, 2),
        ).fetchall()
        assert rows, "expected toc rows for revision"
        assert rows[-1]["page_number"] == 42

        snapshot = store.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        assert snapshot.toc_entries
        assert snapshot.toc_entries[0].page_number == 42
    finally:
        store.close()


def test_rule_atom_subjects_backfill(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        store.conn.execute(
            "DELETE FROM rule_atom_subjects WHERE doc_id = ?",
            (doc_id,),
        )
        store.conn.commit()

        count = store.conn.execute(
            "SELECT COUNT(*) FROM rule_atom_subjects WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()[0]
        assert count == 0

        store._backfill_rule_tables()

        rows = store.conn.execute(
            """
            SELECT text
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id
            """,
            (doc_id, 2),
        ).fetchall()
        assert rows
        assert rows[0]["text"] == "Perform the second duty"
    finally:
        store.close()


def test_atoms_view_reconstructs_subject_rows(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        rows = store.conn.execute(
            """
            SELECT atom_id, type, role, text, refs
            FROM atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY atom_id
            """,
            (doc_id, 2),
        ).fetchall()

        assert rows, "expected reconstructed atoms"
        first = rows[0]
        assert first["atom_id"] == 1
        assert first["type"] == "duty"
        assert first["role"] is None
        assert first["text"] == "Perform the second duty"
        assert first["refs"] == '["Second reference"]'
    finally:
        store.close()


def test_atoms_view_includes_elements_and_lints(tmp_path: Path) -> None:
    store = VersionedStore(str(tmp_path / "store.db"))
    try:
        doc_id = store.generate_id()
        metadata = DocumentMetadata(
            jurisdiction="TestState",
            citation="Test Act 2024",
            date=date(2024, 5, 1),
        )

        subject_link = GlossaryLink(
            text="Subject gloss",
            metadata={"phase": "subject"},
            glossary_id=101,
        )
        subject_atom = Atom(
            type="rule",
            text="Structured subject text",
            refs=["Subject reference"],
            glossary=subject_link,
        )

        element_link = GlossaryLink(
            text="Element gloss",
            metadata={"phase": "element"},
            glossary_id=202,
        )
        element = RuleElement(
            atom_type="element",
            role="requirement",
            text="Element detail",
            references=[
                RuleReference(
                    work="  Work Title",
                    section="s 2  ",
                    pinpoint="   p. 10",
                    glossary=GlossaryLink(glossary_id=element_link.glossary_id),
                )
            ],
            glossary=element_link,
        )

        lint_metadata = {"severity": "medium", "note": "Check element text"}
        lint = RuleLint(
            atom_type="lint",
            code="LINT01",
            message="Element lint message",
            metadata=lint_metadata,
        )

        rule_atom = RuleAtom(
            atom_type="rule",
            text="Structured subject text",
            subject=subject_atom,
            subject_link=subject_link,
            references=[RuleReference(citation_text="Explicit citation")],
            elements=[element],
            lints=[lint],
        )

        provision = Provision(
            text="Provision with structured rule atom",
            identifier="s 10",
            heading="Section 10",
            node_type="section",
            rule_atoms=[rule_atom],
        )

        rev_id = store.add_revision(
            doc_id,
            Document(metadata, "Structured body", provisions=[provision]),
            metadata.date,
        )

        rows = store.conn.execute(
            """
            SELECT atom_id, type, text, refs, gloss_metadata, glossary_id
            FROM atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY atom_id
            """,
            (doc_id, rev_id),
        ).fetchall()

        assert len(rows) >= 3, "expected subject, element, and lint rows"
        subject_row, element_row, lint_row = rows[0], rows[1], rows[2]

        assert subject_row["atom_id"] == 1
        assert subject_row["text"] == "Structured subject text"
        assert subject_row["refs"] == json.dumps(["Subject reference"])
        assert subject_row["glossary_id"] == subject_link.glossary_id

        assert element_row["atom_id"] == 2
        assert element_row["type"] == "element"
        element_refs = json.loads(element_row["refs"])
        assert element_refs, "expected aggregated element references"
        assert all(ref == ref.strip() for ref in element_refs if ref)
        normalised_refs = [" ".join(ref.split()) for ref in element_refs if ref]
        assert normalised_refs == ["Work Title s 2 p. 10"]
        assert element_row["glossary_id"] == element_link.glossary_id

        assert lint_row["atom_id"] == 3
        assert lint_row["type"] == "lint"
        assert lint_row["refs"] is None
        assert json.loads(lint_row["gloss_metadata"]) == lint_metadata
        assert lint_row["glossary_id"] == subject_link.glossary_id
    finally:
        store.close()


def test_legacy_atoms_loaded_from_view_when_structured_absent(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        object_type = store.conn.execute(
            "SELECT type FROM sqlite_master WHERE name = 'atoms'"
        ).fetchone()
        if object_type and object_type["type"] == "view":
            store.conn.execute("CREATE TABLE atoms_materialized AS SELECT * FROM atoms")
            store.conn.execute("DROP VIEW atoms")
            store.conn.execute("ALTER TABLE atoms_materialized RENAME TO atoms")
        store.conn.execute("ALTER TABLE atoms RENAME TO atoms_legacy")
        store.conn.execute("CREATE VIEW atoms AS SELECT * FROM atoms_legacy")

        for table in (
            "rule_element_references",
            "rule_elements",
            "rule_atom_references",
            "rule_lints",
            "rule_atom_subjects",
            "rule_atoms",
        ):
            store.conn.execute(
                f"DELETE FROM {table} WHERE doc_id = ? AND rev_id = ?",
                (doc_id, 1),
            )
        store.conn.commit()

        snapshot = store.snapshot(doc_id, date(2020, 6, 1))
        assert snapshot is not None
        provision = snapshot.provisions[0]

        assert provision.rule_atoms, (
            "expected rule atoms to be derived from legacy view"
        )
        assert provision.atoms, "expected atoms to load from compatibility view"
        assert provision.atoms[0].text == "Perform the first duty"
        assert provision.atoms[0].refs == ["First reference"]
    finally:
        store.close()


def test_rule_atoms_deduplicated_by_text_hash(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    try:
        snapshot = store.snapshot(doc_id, date(2022, 1, 1))
        assert snapshot is not None
        meta = snapshot.metadata

        subject_a = Atom(type="duty", text="Consistent duty")
        subject_b = Atom(type="duty", text="Consistent duty")
        duplicate_rule_atoms = [
            RuleAtom(atom_type="duty", text="Consistent duty", subject=subject_a),
            RuleAtom(atom_type="duty", text="Consistent duty", subject=subject_b),
        ]

        provision = Provision(
            text="Duplicate rule atoms provision",
            identifier="s 3",
            rule_atoms=duplicate_rule_atoms,
        )

        document = Document(meta, "third", provisions=[provision])
        store.add_revision(doc_id, document, date(2023, 1, 1))

        rule_atom_count = store.conn.execute(
            "SELECT COUNT(*) FROM rule_atoms WHERE doc_id = ? AND rev_id = ?",
            (doc_id, 3),
        ).fetchone()[0]
        assert rule_atom_count == 1

        legacy_atom_count = store.conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE doc_id = ? AND rev_id = ?",
            (doc_id, 3),
        ).fetchone()[0]
        assert legacy_atom_count == 1
    finally:
        store.close()


def test_migration_removes_duplicate_rule_atoms(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    db_path = store.path
    try:
        provision_row = store.conn.execute(
            """
            SELECT provision_id, rule_id
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id
            LIMIT 1
            """,
            (doc_id, 2),
        ).fetchone()
        assert provision_row is not None
        provision_id = provision_row["provision_id"]
        base_rule_id = provision_row["rule_id"]

        store.conn.execute("DROP INDEX IF EXISTS idx_rule_atoms_unique_text")

        duplicate_rule_id = base_rule_id + 100

        store.conn.execute(
            """
            INSERT INTO rule_atoms (
                doc_id, rev_id, provision_id, rule_id, text_hash, toc_id, atom_type,
                role, party, who, who_text, actor, modality, action, conditions,
                scope, text, subject_gloss, subject_gloss_metadata, glossary_id
            )
            SELECT doc_id, rev_id, provision_id, ?, text_hash, toc_id, atom_type,
                   role, party, who, who_text, actor, modality, action, conditions,
                   scope, text, subject_gloss, subject_gloss_metadata, glossary_id
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
            """,
            (duplicate_rule_id, doc_id, 2, provision_id, base_rule_id),
        )

        store.conn.execute(
            """
            INSERT INTO rule_atom_subjects (
                doc_id, rev_id, provision_id, rule_id, type, role, party, who,
                who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
            )
            SELECT doc_id, rev_id, provision_id, ?, type, role, party, who,
                   who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
            """,
            (duplicate_rule_id, doc_id, 2, provision_id, base_rule_id),
        )

        store.conn.commit()
    finally:
        store.close()

    migrated = VersionedStore(db_path)
    try:
        rule_atom_count = migrated.conn.execute(
            """
            SELECT COUNT(*)
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
            """,
            (doc_id, 2, provision_id),
        ).fetchone()[0]
        assert rule_atom_count == 1

        subject_count = migrated.conn.execute(
            """
            SELECT COUNT(*)
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
            """,
            (doc_id, 2, provision_id),
        ).fetchone()[0]
        assert subject_count == 1
    finally:
        migrated.close()


def test_migration_preserves_rule_atoms_with_distinct_party_role(tmp_path: Path):
    store, doc_id = make_store(tmp_path)
    db_path = store.path
    try:
        base_row = store.conn.execute(
            """
            SELECT provision_id, rule_id, party, role
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id
            LIMIT 1
            """,
            (doc_id, 2),
        ).fetchone()
        assert base_row is not None
        provision_id = base_row["provision_id"]
        base_rule_id = base_row["rule_id"]
        base_party = base_row["party"]
        base_role = base_row["role"]

        store.conn.execute("DROP INDEX IF EXISTS idx_rule_atoms_unique_text")

        distinct_rule_id = base_rule_id + 200

        store.conn.execute(
            """
            INSERT INTO rule_atoms (
                doc_id, rev_id, provision_id, rule_id, text_hash, toc_id, atom_type,
                role, party, who, who_text, actor, modality, action, conditions,
                scope, text, subject_gloss, subject_gloss_metadata, glossary_id
            )
            SELECT doc_id, rev_id, provision_id, ?, text_hash, toc_id, atom_type,
                   ?, ?, who, who_text, actor, modality, action, conditions,
                   scope, text, subject_gloss, subject_gloss_metadata, glossary_id
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
            """,
            (
                distinct_rule_id,
                "alternate-role",
                "Party B",
                doc_id,
                2,
                provision_id,
                base_rule_id,
            ),
        )

        store.conn.execute(
            """
            INSERT INTO rule_atom_subjects (
                doc_id, rev_id, provision_id, rule_id, type, role, party, who,
                who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
            )
            SELECT doc_id, rev_id, provision_id, ?, type, ?, ?, who,
                   who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
            FROM rule_atom_subjects
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
            """,
            (
                distinct_rule_id,
                "alternate-role",
                "Party B",
                doc_id,
                2,
                provision_id,
                base_rule_id,
            ),
        )

        store.conn.commit()
    finally:
        store.close()

    migrated = VersionedStore(db_path)
    try:
        rows = migrated.conn.execute(
            """
            SELECT party, role
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
            ORDER BY rule_id
            """,
            (doc_id, 2, provision_id),
        ).fetchall()
        assert len(rows) == 2
        parties = {row["party"] for row in rows}
        roles = {row["role"] for row in rows}
        assert parties == {base_party, "Party B"}
        assert roles == {base_role, "alternate-role"}
    finally:
        migrated.close()


def test_tables_use_without_rowid(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    try:
        for table_name in ("provisions", "rule_atoms", "rule_elements"):
            info_rows = store.conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
            assert info_rows, f"expected columns for {table_name}"

            with pytest.raises(sqlite3.OperationalError):
                store.conn.execute(f"SELECT rowid FROM {table_name} LIMIT 1")
    finally:
        store.close()


def test_migration_converts_rowid_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_rowid.db"
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                );

                CREATE TABLE revisions (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    effective_date TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source_url TEXT,
                    retrieved_at TEXT,
                    checksum TEXT,
                    licence TEXT,
                    document_json TEXT,
                    PRIMARY KEY (doc_id, rev_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(id)
                );

                CREATE TABLE toc (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    toc_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    node_type TEXT,
                    identifier TEXT,
                    title TEXT,
                    stable_id TEXT,
                    position INTEGER NOT NULL,
                    page_number INTEGER,
                    PRIMARY KEY (doc_id, rev_id, toc_id)
                );

                CREATE TABLE provisions (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    identifier TEXT,
                    heading TEXT,
                    node_type TEXT,
                    toc_id INTEGER,
                    text TEXT,
                    rule_tokens TEXT,
                    references_json TEXT,
                    principles TEXT,
                    customs TEXT,
                    cultural_flags TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id)
                );

                CREATE TABLE rule_atoms (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    text_hash TEXT NOT NULL,
                    toc_id INTEGER,
                    stable_id TEXT,
                    atom_type TEXT,
                    role TEXT,
                    party TEXT,
                    who TEXT,
                    who_text TEXT,
                    actor TEXT,
                    modality TEXT,
                    action TEXT,
                    conditions TEXT,
                    scope TEXT,
                    text TEXT,
                    subject_gloss TEXT,
                    subject_gloss_metadata TEXT,
                    glossary_id INTEGER,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id)
                );

                CREATE TABLE rule_elements (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    element_id INTEGER NOT NULL,
                    text_hash TEXT,
                    atom_type TEXT,
                    role TEXT,
                    text TEXT,
                    conditions TEXT,
                    gloss TEXT,
                    gloss_metadata TEXT,
                    glossary_id INTEGER,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id)
                );
                """
            )

            conn.execute("INSERT INTO documents (id) VALUES (1)")
            conn.execute(
                """
                INSERT INTO revisions (
                    doc_id, rev_id, effective_date, metadata, body,
                    source_url, retrieved_at, checksum, licence, document_json
                )
                VALUES (1, 1, '2020-01-01', '{}', 'body', NULL, NULL, NULL, NULL, NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO provisions (
                    doc_id, rev_id, provision_id, parent_id, identifier, heading,
                    node_type, toc_id, text, rule_tokens, references_json,
                    principles, customs, cultural_flags
                )
                VALUES (1, 1, 1, NULL, 's 1', 'Heading', 'section', NULL,
                        'Provision text', NULL, '{}', NULL, NULL, NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO rule_atoms (
                    doc_id, rev_id, provision_id, rule_id, text_hash, toc_id, stable_id,
                    atom_type, role, party, who, who_text, actor, modality, action,
                    conditions, scope, text, subject_gloss, subject_gloss_metadata, glossary_id
                )
                VALUES (1, 1, 1, 1, 'hash', NULL, 'stable', 'rule', 'role', 'party',
                        NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'Atom text',
                        NULL, NULL, NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO rule_elements (
                    doc_id, rev_id, provision_id, rule_id, element_id, text_hash,
                    atom_type, role, text, conditions, gloss, gloss_metadata, glossary_id
                )
                VALUES (1, 1, 1, 1, 1, NULL, 'element', 'role', 'Element text',
                        NULL, NULL, NULL, NULL)
                """
            )
    finally:
        conn.close()

    store = VersionedStore(str(db_path))
    try:
        heading = store.conn.execute(
            "SELECT heading FROM provisions WHERE doc_id = 1 AND rev_id = 1"
        ).fetchone()
        assert heading is not None
        assert heading["heading"] == "Heading"

        atom_row = store.conn.execute(
            "SELECT text FROM rule_atoms WHERE doc_id = 1 AND rev_id = 1 AND rule_id = 1"
        ).fetchone()
        assert atom_row is not None
        assert atom_row["text"] == "Atom text"

        element_row = store.conn.execute(
            "SELECT text FROM rule_elements WHERE doc_id = 1 AND rev_id = 1 AND element_id = 1"
        ).fetchone()
        assert element_row is not None
        assert element_row["text"] == "Element text"

        for table_name in ("provisions", "rule_atoms", "rule_elements"):
            with pytest.raises(sqlite3.OperationalError):
                store.conn.execute(f"SELECT rowid FROM {table_name} LIMIT 1")
    finally:
        store.close()


def test_process_pdf_persists_normalized(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 sample")
    db_path = tmp_path / "store.db"
    output_path = tmp_path / "out.json"

    def fake_extract_pdf_text(_path: Path):
        yield {
            "page": 1,
            "heading": "1 Heading",
            "text": "Alice must pay Bob.",
            "lines": ["1 Heading", "Alice must pay Bob."],
        }

    monkeypatch.setattr(pdf_ingest, "extract_pdf_text", fake_extract_pdf_text)
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

        rule_atom_rows = store.conn.execute(
            """
            SELECT atom_type, text
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY rule_id
            """,
            (stored_doc_id, 1),
        ).fetchall()
        assert rule_atom_rows
        assert any(row["atom_type"] == "rule" for row in rule_atom_rows)

        rule_element_rows = store.conn.execute(
            """
            SELECT role, text
            FROM rule_elements
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY rule_id, element_id
            """,
            (stored_doc_id, 1),
        ).fetchall()
        assert rule_element_rows

        snapshot = store.snapshot(stored_doc_id, document.metadata.date)
        assert snapshot is not None
        assert snapshot.provisions
        assert snapshot.provisions[0].atoms
    finally:
        store.close()


def test_toc_entries_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "toc_store.db"
    store = VersionedStore(str(db_path))
    doc_id = store.generate_id()
    metadata = DocumentMetadata(
        jurisdiction="Test", citation="Doc 1", date=date(2023, 1, 1)
    )
    section = Provision(
        text="Child provision",
        identifier="s 1",
        heading="Section 1",
        node_type="section",
    )
    part = Provision(
        text="Parent provision",
        identifier="Part 1",
        heading="Part 1",
        node_type="part",
        children=[section],
    )
    toc_structure = [
        DocumentTOCEntry(
            node_type="part",
            identifier="Part 1",
            title="Part 1",
            page_number=5,
            children=[
                DocumentTOCEntry(
                    node_type="section",
                    identifier="s 1",
                    title="Section 1",
                    page_number=6,
                )
            ],
        )
    ]

    store.add_revision(
        doc_id,
        Document(
            metadata,
            "body",
            provisions=[part],
            toc_entries=toc_structure,
        ),
        date(2023, 1, 1),
    )

    try:
        rows = store.conn.execute(
            """
            SELECT toc_id, parent_id, node_type, identifier, title, position, page_number, stable_id
            FROM toc
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY toc_id
            """,
            (doc_id, 1),
        ).fetchall()
        assert len(rows) == 2
        parent_row, child_row = rows
        assert parent_row["page_number"] == 5
        assert child_row["page_number"] == 6
        assert child_row["parent_id"] == parent_row["toc_id"]
        assert parent_row["stable_id"]
        assert child_row["stable_id"].startswith(parent_row["stable_id"])

        snapshot = store.snapshot(doc_id, date(2023, 1, 1))
        assert snapshot is not None
        assert snapshot.toc_entries
        assert snapshot.toc_entries[0].page_number == 5
        assert snapshot.toc_entries[0].children
        assert snapshot.toc_entries[0].children[0].page_number == 6
        assert snapshot.provisions[0].stable_id == parent_row["stable_id"]
        assert snapshot.provisions[0].children[0].stable_id == child_row["stable_id"]
    finally:
        store.close()


def test_revisions_effective_date_index(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    try:
        indexes = store.conn.execute("PRAGMA index_list(revisions)").fetchall()
        index_names = {row["name"] for row in indexes}
        assert "idx_revisions_doc_effective_desc" in index_names

        details = store.conn.execute(
            "PRAGMA index_xinfo(idx_revisions_doc_effective_desc)"
        ).fetchall()
        effective_row = next(row for row in details if row["name"] == "effective_date")
        assert effective_row["desc"] == 1
    finally:
        store.close()
