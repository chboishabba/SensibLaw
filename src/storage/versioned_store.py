from __future__ import annotations

import sqlite3
import json
import difflib
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ..models.document import Document, DocumentMetadata
from ..models.provision import (
    Atom,
    Provision,
    RuleAtom,
    RuleElement,
    RuleLint,
    RuleReference,
)


class VersionedStore:
    """SQLite-backed store maintaining versioned documents using FTS5."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                );

                CREATE TABLE IF NOT EXISTS revisions (
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

                CREATE TABLE IF NOT EXISTS provisions (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    identifier TEXT,
                    heading TEXT,
                    node_type TEXT,
                    text TEXT,
                    rule_tokens TEXT,
                    references_json TEXT,
                    principles TEXT,
                    customs TEXT,
                    cultural_flags TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id),
                    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id)
                );

                CREATE INDEX IF NOT EXISTS idx_provisions_doc_rev
                ON provisions(doc_id, rev_id, provision_id);

                CREATE TABLE IF NOT EXISTS atoms (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    atom_id INTEGER NOT NULL,
                    type TEXT,
                    role TEXT,
                    party TEXT,
                    who TEXT,
                    who_text TEXT,
                    text TEXT,
                    conditions TEXT,
                    refs TEXT,
                    gloss TEXT,
                    gloss_metadata TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, atom_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id)
                        REFERENCES provisions(doc_id, rev_id, provision_id)
                );

                CREATE INDEX IF NOT EXISTS idx_atoms_doc_rev
                ON atoms(doc_id, rev_id, provision_id);

                CREATE TABLE IF NOT EXISTS rule_atoms (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
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
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id)
                        REFERENCES provisions(doc_id, rev_id, provision_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_atoms_doc_rev
                ON rule_atoms(doc_id, rev_id, provision_id);

                CREATE TABLE IF NOT EXISTS rule_atom_references (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    ref_index INTEGER NOT NULL,
                    work TEXT,
                    section TEXT,
                    pinpoint TEXT,
                    citation_text TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, ref_index),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
                        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_atom_refs_doc_rev
                ON rule_atom_references(doc_id, rev_id, provision_id, rule_id);

                CREATE TABLE IF NOT EXISTS rule_elements (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    element_id INTEGER NOT NULL,
                    atom_type TEXT,
                    role TEXT,
                    text TEXT,
                    conditions TEXT,
                    gloss TEXT,
                    gloss_metadata TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
                        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_elements_doc_rev
                ON rule_elements(doc_id, rev_id, provision_id, rule_id);

                CREATE TABLE IF NOT EXISTS rule_element_references (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    element_id INTEGER NOT NULL,
                    ref_index INTEGER NOT NULL,
                    work TEXT,
                    section TEXT,
                    pinpoint TEXT,
                    citation_text TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id, ref_index),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id, element_id)
                        REFERENCES rule_elements(doc_id, rev_id, provision_id, rule_id, element_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_element_refs_doc_rev
                ON rule_element_references(doc_id, rev_id, provision_id, rule_id, element_id);

                CREATE TABLE IF NOT EXISTS rule_lints (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    lint_id INTEGER NOT NULL,
                    atom_type TEXT,
                    code TEXT,
                    message TEXT,
                    metadata TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, lint_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
                        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_lints_doc_rev
                ON rule_lints(doc_id, rev_id, provision_id, rule_id);

                CREATE TABLE IF NOT EXISTS atom_references (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    atom_id INTEGER NOT NULL,
                    ref_index INTEGER NOT NULL,
                    work TEXT,
                    section TEXT,
                    pinpoint TEXT,
                    citation_text TEXT,
                    PRIMARY KEY (doc_id, rev_id, provision_id, atom_id, ref_index),
                    FOREIGN KEY (doc_id, rev_id, provision_id, atom_id)
                        REFERENCES atoms(doc_id, rev_id, provision_id, atom_id)
                );

                CREATE INDEX IF NOT EXISTS idx_atom_references_doc_rev
                ON atom_references(doc_id, rev_id, provision_id, atom_id);

                CREATE VIRTUAL TABLE IF NOT EXISTS revisions_fts USING fts5(
                    body, metadata, content='revisions', content_rowid='rowid'
                );
                """
            )
        cur = self.conn.execute("PRAGMA table_info(revisions)")
        columns = {row["name"] for row in cur.fetchall()}
        if "document_json" not in columns:
            with self.conn:
                self.conn.execute("ALTER TABLE revisions ADD COLUMN document_json TEXT")

            # Migration: ensure the revisions table has a document_json column
            columns = {
                row["name"] for row in self.conn.execute("PRAGMA table_info(revisions)")
            }
            if "document_json" not in columns:
                self.conn.execute("ALTER TABLE revisions ADD COLUMN document_json TEXT")

        self._backfill_rule_tables()

    # ------------------------------------------------------------------
    # ID generation and revision storage
    # ------------------------------------------------------------------
    def generate_id(self) -> int:
        """Generate and return a new unique document ID."""
        with self.conn:
            cur = self.conn.execute("INSERT INTO documents DEFAULT VALUES")
            lastrowid = cur.lastrowid
            assert lastrowid is not None
            return lastrowid

    def add_revision(
        self, doc_id: int, document: Document, effective_date: date
    ) -> int:
        """Add a new revision for a document.

        Args:
            doc_id: Identifier of the document to update.
            document: Document content to store.
            effective_date: Date this revision takes effect.

        Returns:
            The revision number assigned to the stored revision.
        """
        metadata_json = json.dumps(document.metadata.to_dict())
        document_json = document.to_json()
        retrieved_at = (
            document.metadata.retrieved_at.isoformat()
            if document.metadata.retrieved_at
            else None
        )
        document_json = document.to_json()
        with self.conn:
            cur = self.conn.execute(
                "SELECT COALESCE(MAX(rev_id), 0) + 1 FROM revisions WHERE doc_id = ?",
                (doc_id,),
            )
            rev_id = cur.fetchone()[0]
            self.conn.execute(
                """
                INSERT INTO revisions (
                    doc_id, rev_id, effective_date, metadata, body,
                    source_url, retrieved_at, checksum, licence, document_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    rev_id,
                    effective_date.isoformat(),
                    metadata_json,
                    document.body,
                    document.metadata.source_url,
                    retrieved_at,
                    document.metadata.checksum,
                    document.metadata.licence,
                    document_json,
                ),
            )
            # keep FTS table in sync
            self.conn.execute(
                "INSERT INTO revisions_fts(rowid, body, metadata) VALUES (last_insert_rowid(), ?, ?)",
                (document.body, metadata_json),
            )
            self._store_provisions(doc_id, rev_id, document.provisions)
        return rev_id

    # ------------------------------------------------------------------
    # Retrieval and diff utilities
    # ------------------------------------------------------------------
    def snapshot(self, doc_id: int, as_at: date) -> Optional[Document]:
        """Return the document state as of a given date.

        Args:
            doc_id: Document identifier.
            as_at: Date for which the snapshot should be taken.
        """
        row = self.conn.execute(
            """
            SELECT rev_id, metadata, body, document_json
            FROM revisions
            WHERE doc_id = ? AND effective_date <= ?
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            (doc_id, as_at.isoformat()),
        ).fetchone()
        if row is None:
            return None
        return self._load_document(
            doc_id,
            row["rev_id"],
            row["metadata"],
            row["body"],
            row["document_json"],
        )

    def get_by_canonical_id(self, canonical_id: str) -> Optional[Document]:
        """Return the latest revision for a document by its canonical ID."""

        rows = self.conn.execute(
            """
            SELECT r.doc_id, r.rev_id, r.metadata, r.body, r.document_json
            FROM revisions r
            JOIN (
                SELECT doc_id, MAX(rev_id) AS rev_id
                FROM revisions
                GROUP BY doc_id
            ) latest ON r.doc_id = latest.doc_id AND r.rev_id = latest.rev_id
            """
        )
        for row in rows:
            document = self._load_document(
                row["doc_id"],
                row["rev_id"],
                row["metadata"],
                row["body"],
                row["document_json"],
            )
            if document.metadata.canonical_id == canonical_id:
                return document
        return None

    def _load_document(
        self,
        doc_id: int,
        rev_id: int,
        metadata_json: str,
        body: str,
        document_json: Optional[str],
    ) -> Document:
        """Reconstruct a :class:`Document` from stored state."""

        metadata = DocumentMetadata.from_dict(json.loads(metadata_json))
        provisions, has_rows = self._load_provisions(doc_id, rev_id)
        if has_rows:
            return Document(metadata=metadata, body=body, provisions=provisions)
        if document_json:
            return Document.from_json(document_json)
        return Document(metadata=metadata, body=body)

    def _store_provisions(
        self, doc_id: int, rev_id: int, provisions: List[Provision]
    ) -> None:
        """Persist provision and atom data for a revision."""

        self.conn.execute(
            "DELETE FROM rule_element_references WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM rule_atom_references WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM rule_lints WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM rule_elements WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM rule_atoms WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM atom_references WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM atoms WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM provisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )

        if not provisions:
            return

        provision_counter = 0

        def visit(provision: Provision, parent_id: Optional[int]) -> None:
            nonlocal provision_counter
            provision_counter += 1
            current_id = provision_counter

            references_json = None
            if provision.references:
                references_json = json.dumps(
                    [list(ref) for ref in provision.references]
                )
            principles_json = (
                json.dumps(list(provision.principles)) if provision.principles else None
            )
            customs_json = (
                json.dumps(list(provision.customs)) if provision.customs else None
            )
            cultural_flags_json = (
                json.dumps(list(provision.cultural_flags))
                if provision.cultural_flags
                else None
            )

            provision.ensure_rule_atoms()
            provision.sync_legacy_atoms()

            self.conn.execute(
                """
                INSERT INTO provisions (
                    doc_id, rev_id, provision_id, parent_id, identifier,
                    heading, node_type, text, rule_tokens, references_json,
                    principles, customs, cultural_flags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    rev_id,
                    current_id,
                    parent_id,
                    provision.identifier,
                    provision.heading,
                    provision.node_type,
                    provision.text,
                    json.dumps(provision.rule_tokens)
                    if provision.rule_tokens
                    else None,
                    references_json,
                    principles_json,
                    customs_json,
                    cultural_flags_json,
                ),
            )

            if provision.rule_atoms:
                self._persist_rule_structures(
                    doc_id, rev_id, current_id, provision.rule_atoms
                )

            for atom_index, atom in enumerate(provision.atoms, start=1):
                gloss_metadata_json = (
                    json.dumps(atom.gloss_metadata)
                    if atom.gloss_metadata is not None
                    else None
                )
                self.conn.execute(
                    """
                    INSERT INTO atoms (
                        doc_id, rev_id, provision_id, atom_id, type, role,
                        party, who, who_text, text, conditions, refs, gloss,
                        gloss_metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        rev_id,
                        current_id,
                        atom_index,
                        atom.type,
                        atom.role,
                        atom.party,
                        atom.who,
                        atom.who_text,
                        atom.text,
                        atom.conditions,
                        None,
                        atom.gloss,
                        gloss_metadata_json,
                    ),
                )

                if atom.refs:
                    for ref_index, ref in enumerate(atom.refs, start=1):
                        work = None
                        section = None
                        pinpoint = None
                        citation_text = None

                        if isinstance(ref, dict):
                            work = ref.get("work")
                            section = ref.get("section")
                            pinpoint = ref.get("pinpoint")
                            citation_text = (
                                ref.get("citation_text")
                                or ref.get("text")
                                or ref.get("citation")
                            )
                        elif isinstance(ref, (list, tuple)):
                            # Support positional data when provided as an iterable.
                            parts = list(ref)
                            if parts:
                                work = parts[0]
                            if len(parts) > 1:
                                section = parts[1]
                            if len(parts) > 2:
                                pinpoint = parts[2]
                            if len(parts) > 3:
                                citation_text = parts[3]
                            elif len(parts) == 3:
                                citation_text = parts[2]
                        else:
                            citation_text = str(ref)

                        self.conn.execute(
                            """
                            INSERT INTO atom_references (
                                doc_id, rev_id, provision_id, atom_id, ref_index,
                                work, section, pinpoint, citation_text
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                doc_id,
                                rev_id,
                                current_id,
                                atom_index,
                                ref_index,
                                work,
                                section,
                                pinpoint,
                                citation_text,
                            ),
                        )

            for child in provision.children:
                visit(child, current_id)

        for provision in provisions:
            visit(provision, None)

    def _load_provisions(
        self, doc_id: int, rev_id: int
    ) -> Tuple[List[Provision], bool]:
        """Load provisions and atoms for a revision."""

        provision_rows = self.conn.execute(
            """
            SELECT doc_id, rev_id, provision_id, parent_id, identifier, heading,
                   node_type, text, rule_tokens, references_json, principles, customs,
                   cultural_flags
            FROM provisions
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id
            """,
            (doc_id, rev_id),
        ).fetchall()
        if not provision_rows:
            return [], False

        rule_atom_rows = self.conn.execute(
            """
            SELECT provision_id, rule_id, atom_type, role, party, who, who_text,
                   actor, modality, action, conditions, scope, text, subject_gloss,
                   subject_gloss_metadata
            FROM rule_atoms
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id, rule_id
            """,
            (doc_id, rev_id),
        ).fetchall()

        using_structured = bool(rule_atom_rows)

        rule_atoms_by_provision: dict[int, List[RuleAtom]] = defaultdict(list)
        atoms_by_provision: dict[int, List[Atom]] = defaultdict(list)

        if using_structured:
            atom_reference_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, ref_index, work, section, pinpoint, citation_text
                FROM rule_atom_references
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, ref_index
                """,
                (doc_id, rev_id),
            ).fetchall()
            element_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, element_id, atom_type, role, text, conditions,
                       gloss, gloss_metadata
                FROM rule_elements
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, element_id
                """,
                (doc_id, rev_id),
            ).fetchall()
            element_reference_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, element_id, ref_index, work, section, pinpoint, citation_text
                FROM rule_element_references
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, element_id, ref_index
                """,
                (doc_id, rev_id),
            ).fetchall()
            lint_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, lint_id, atom_type, code, message, metadata
                FROM rule_lints
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, lint_id
                """,
                (doc_id, rev_id),
            ).fetchall()

            atom_refs_map: dict[tuple[int, int], List[RuleReference]] = defaultdict(
                list
            )
            for row in atom_reference_rows:
                atom_refs_map[(row["provision_id"], row["rule_id"])].append(
                    RuleReference(
                        work=row["work"],
                        section=row["section"],
                        pinpoint=row["pinpoint"],
                        citation_text=row["citation_text"],
                    )
                )

            element_refs_map: dict[tuple[int, int, int], List[RuleReference]] = (
                defaultdict(list)
            )
            for row in element_reference_rows:
                element_refs_map[
                    (row["provision_id"], row["rule_id"], row["element_id"])
                ].append(
                    RuleReference(
                        work=row["work"],
                        section=row["section"],
                        pinpoint=row["pinpoint"],
                        citation_text=row["citation_text"],
                    )
                )

            rule_lookup: dict[tuple[int, int], RuleAtom] = {}
            for row in rule_atom_rows:
                metadata = (
                    json.loads(row["subject_gloss_metadata"])
                    if row["subject_gloss_metadata"]
                    else None
                )
                references = [
                    RuleReference(
                        work=ref.work,
                        section=ref.section,
                        pinpoint=ref.pinpoint,
                        citation_text=ref.citation_text,
                    )
                    for ref in atom_refs_map.get(
                        (row["provision_id"], row["rule_id"]), []
                    )
                ]
                rule_atom = RuleAtom(
                    atom_type=row["atom_type"],
                    role=row["role"],
                    party=row["party"],
                    who=row["who"],
                    who_text=row["who_text"],
                    actor=row["actor"],
                    modality=row["modality"],
                    action=row["action"],
                    conditions=row["conditions"],
                    scope=row["scope"],
                    text=row["text"],
                    subject_gloss=row["subject_gloss"],
                    subject_gloss_metadata=metadata,
                    references=references,
                )
                rule_atoms_by_provision[row["provision_id"]].append(rule_atom)
                rule_lookup[(row["provision_id"], row["rule_id"])] = rule_atom

            for row in element_rows:
                metadata = (
                    json.loads(row["gloss_metadata"]) if row["gloss_metadata"] else None
                )
                references = [
                    RuleReference(
                        work=ref.work,
                        section=ref.section,
                        pinpoint=ref.pinpoint,
                        citation_text=ref.citation_text,
                    )
                    for ref in element_refs_map.get(
                        (row["provision_id"], row["rule_id"], row["element_id"]), []
                    )
                ]
                element = RuleElement(
                    atom_type=row["atom_type"],
                    role=row["role"],
                    text=row["text"],
                    conditions=row["conditions"],
                    gloss=row["gloss"],
                    gloss_metadata=metadata,
                    references=references,
                )
                parent = rule_lookup.get((row["provision_id"], row["rule_id"]))
                if parent is not None:
                    parent.elements.append(element)

            for row in lint_rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else None
                lint = RuleLint(
                    atom_type=row["atom_type"],
                    code=row["code"],
                    message=row["message"],
                    metadata=metadata,
                )
                parent = rule_lookup.get((row["provision_id"], row["rule_id"]))
                if parent is not None:
                    parent.lints.append(lint)

        else:
            atom_rows = self.conn.execute(
                """
                SELECT provision_id, atom_id, type, role, party, who, who_text, text,
                       conditions, refs, gloss, gloss_metadata
                FROM atoms
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, atom_id
                """,
                (doc_id, rev_id),
            ).fetchall()
            atom_reference_rows = self.conn.execute(
                """
                SELECT provision_id, atom_id, ref_index, work, section, pinpoint, citation_text
                FROM atom_references
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, atom_id, ref_index
                """,
                (doc_id, rev_id),
            ).fetchall()

            refs_by_atom: dict[tuple[int, int], List[str]] = {}
            for ref_row in atom_reference_rows:
                key = (ref_row["provision_id"], ref_row["atom_id"])
                ref_text = ref_row["citation_text"]
                if not ref_text:
                    parts = [
                        ref_row["work"],
                        ref_row["section"],
                        ref_row["pinpoint"],
                    ]
                    ref_text = " ".join(part for part in parts if part)
                refs_by_atom.setdefault(key, []).append(ref_text or "")

            for atom_row in atom_rows:
                key = (atom_row["provision_id"], atom_row["atom_id"])
                if key in refs_by_atom:
                    refs = list(refs_by_atom[key])
                else:
                    refs = json.loads(atom_row["refs"]) if atom_row["refs"] else []
                gloss_metadata = (
                    json.loads(atom_row["gloss_metadata"])
                    if atom_row["gloss_metadata"]
                    else None
                )
                atoms_by_provision[atom_row["provision_id"]].append(
                    Atom(
                        type=atom_row["type"],
                        role=atom_row["role"],
                        party=atom_row["party"],
                        who=atom_row["who"],
                        who_text=atom_row["who_text"],
                        conditions=atom_row["conditions"],
                        text=atom_row["text"],
                        refs=refs,
                        gloss=atom_row["gloss"],
                        gloss_metadata=gloss_metadata,
                    )
                )

        provisions: dict[int, Provision] = {}
        root_ids: List[int] = []

        for row in provision_rows:
            rule_tokens = json.loads(row["rule_tokens"]) if row["rule_tokens"] else {}
            references: List[
                Tuple[str, Optional[str], Optional[str], Optional[str], str]
            ] = []
            if row["references_json"]:
                for ref in json.loads(row["references_json"]):
                    if isinstance(ref, list):
                        references.append(tuple(ref))  # type: ignore[arg-type]
                    elif isinstance(ref, tuple):
                        references.append(ref)
                    else:
                        # fall back to treating as string reference id
                        references.append((str(ref), None, None, None, str(ref)))

            principles = json.loads(row["principles"]) if row["principles"] else []
            customs = json.loads(row["customs"]) if row["customs"] else []
            cultural_flags = (
                json.loads(row["cultural_flags"]) if row["cultural_flags"] else []
            )

            provision = Provision(
                text=row["text"] or "",
                identifier=row["identifier"],
                heading=row["heading"],
                node_type=row["node_type"],
                rule_tokens=rule_tokens,
                cultural_flags=cultural_flags,
                references=references,
                principles=list(principles),
                customs=list(customs),
            )
            if using_structured:
                provision.rule_atoms.extend(
                    rule_atoms_by_provision.get(row["provision_id"], [])
                )
                provision.sync_legacy_atoms()
            else:
                provision.atoms.extend(atoms_by_provision.get(row["provision_id"], []))
                provision.ensure_rule_atoms()
            provisions[row["provision_id"]] = provision

        for row in provision_rows:
            parent_id = row["parent_id"]
            current_id = row["provision_id"]
            provision = provisions[current_id]
            if parent_id is None:
                root_ids.append(current_id)
            else:
                parent = provisions.get(parent_id)
                if parent is None:
                    root_ids.append(current_id)
                else:
                    parent.children.append(provision)

        ordered_roots = [provisions[pid] for pid in root_ids]
        has_rows = using_structured or any(atoms_by_provision.values())
        return ordered_roots, has_rows

    def _persist_rule_structures(
        self,
        doc_id: int,
        rev_id: int,
        provision_id: int,
        rule_atoms: List[RuleAtom],
    ) -> None:
        """Persist structured rule data for a provision."""

        for rule_index, rule_atom in enumerate(rule_atoms, start=1):
            subject_metadata_json = (
                json.dumps(rule_atom.subject_gloss_metadata)
                if rule_atom.subject_gloss_metadata is not None
                else None
            )
            self.conn.execute(
                """
                INSERT INTO rule_atoms (
                    doc_id, rev_id, provision_id, rule_id, atom_type, role, party,
                    who, who_text, actor, modality, action, conditions, scope,
                    text, subject_gloss, subject_gloss_metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    rev_id,
                    provision_id,
                    rule_index,
                    rule_atom.atom_type,
                    rule_atom.role,
                    rule_atom.party,
                    rule_atom.who,
                    rule_atom.who_text,
                    rule_atom.actor,
                    rule_atom.modality,
                    rule_atom.action,
                    rule_atom.conditions,
                    rule_atom.scope,
                    rule_atom.text,
                    rule_atom.subject_gloss,
                    subject_metadata_json,
                ),
            )

            for ref_index, ref in enumerate(rule_atom.references, start=1):
                self.conn.execute(
                    """
                    INSERT INTO rule_atom_references (
                        doc_id, rev_id, provision_id, rule_id, ref_index,
                        work, section, pinpoint, citation_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        rev_id,
                        provision_id,
                        rule_index,
                        ref_index,
                        ref.work,
                        ref.section,
                        ref.pinpoint,
                        ref.citation_text,
                    ),
                )

            for element_index, element in enumerate(rule_atom.elements, start=1):
                element_metadata_json = (
                    json.dumps(element.gloss_metadata)
                    if element.gloss_metadata is not None
                    else None
                )
                self.conn.execute(
                    """
                    INSERT INTO rule_elements (
                        doc_id, rev_id, provision_id, rule_id, element_id, atom_type,
                        role, text, conditions, gloss, gloss_metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        rev_id,
                        provision_id,
                        rule_index,
                        element_index,
                        element.atom_type,
                        element.role,
                        element.text,
                        element.conditions,
                        element.gloss,
                        element_metadata_json,
                    ),
                )

                for ref_index, ref in enumerate(element.references, start=1):
                    self.conn.execute(
                        """
                        INSERT INTO rule_element_references (
                            doc_id, rev_id, provision_id, rule_id, element_id, ref_index,
                            work, section, pinpoint, citation_text
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc_id,
                            rev_id,
                            provision_id,
                            rule_index,
                            element_index,
                            ref_index,
                            ref.work,
                            ref.section,
                            ref.pinpoint,
                            ref.citation_text,
                        ),
                    )

            for lint_index, lint in enumerate(rule_atom.lints, start=1):
                lint_metadata_json = (
                    json.dumps(lint.metadata) if lint.metadata is not None else None
                )
                self.conn.execute(
                    """
                    INSERT INTO rule_lints (
                        doc_id, rev_id, provision_id, rule_id, lint_id, atom_type,
                        code, message, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        rev_id,
                        provision_id,
                        rule_index,
                        lint_index,
                        lint.atom_type,
                        lint.code,
                        lint.message or "",
                        lint_metadata_json,
                    ),
                )

    def diff(self, doc_id: int, rev_a: int, rev_b: int) -> str:
        """Return a unified diff between two revisions of a document."""
        row_a = self.conn.execute(
            "SELECT body FROM revisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_a),
        ).fetchone()
        row_b = self.conn.execute(
            "SELECT body FROM revisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_b),
        ).fetchone()
        if row_a is None or row_b is None:
            raise ValueError("Revision not found")
        a_lines = row_a["body"].splitlines()
        b_lines = row_b["body"].splitlines()
        diff = difflib.unified_diff(
            a_lines,
            b_lines,
            fromfile=f"rev{rev_a}",
            tofile=f"rev{rev_b}",
            lineterm="",
        )
        return "\n".join(diff)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------
    # Legacy migration helpers
    # ------------------------------------------------------------------
    def _backfill_rule_tables(self) -> None:
        """Populate structured rule tables from legacy atom storage if needed."""

        legacy_count = self.conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        if legacy_count == 0:
            return

        missing_provisions = self.conn.execute(
            """
            SELECT DISTINCT a.doc_id AS doc_id, a.rev_id AS rev_id, a.provision_id AS provision_id
            FROM atoms AS a
            LEFT JOIN rule_atoms AS r
                ON r.doc_id = a.doc_id
                AND r.rev_id = a.rev_id
                AND r.provision_id = a.provision_id
            WHERE r.doc_id IS NULL
            """
        ).fetchall()
        if not missing_provisions:
            return

        conditions = " OR ".join(
            "(doc_id = ? AND rev_id = ? AND provision_id = ?)" for _ in missing_provisions
        )
        params: list[int] = []
        for row in missing_provisions:
            params.extend([row["doc_id"], row["rev_id"], row["provision_id"]])

        atom_rows = self.conn.execute(
            f"""
            SELECT doc_id, rev_id, provision_id, atom_id, type, role, party, who, who_text,
                   text, conditions, refs, gloss, gloss_metadata
            FROM atoms
            WHERE {conditions}
            ORDER BY doc_id, rev_id, provision_id, atom_id
            """,
            params,
        ).fetchall()
        if not atom_rows:
            return

        reference_rows = self.conn.execute(
            f"""
            SELECT doc_id, rev_id, provision_id, atom_id, work, section, pinpoint, citation_text
            FROM atom_references
            WHERE {conditions}
            ORDER BY doc_id, rev_id, provision_id, atom_id, ref_index
            """,
            params,
        ).fetchall()

        refs_by_atom: dict[tuple[int, int, int, int], List[Any]] = defaultdict(list)
        for row in reference_rows:
            key = (row["doc_id"], row["rev_id"], row["provision_id"], row["atom_id"])
            refs_by_atom[key].append(
                {
                    "work": row["work"],
                    "section": row["section"],
                    "pinpoint": row["pinpoint"],
                    "citation_text": row["citation_text"],
                }
            )

        grouped_atoms: dict[tuple[int, int, int], List[Atom]] = defaultdict(list)
        for row in atom_rows:
            key = (row["doc_id"], row["rev_id"], row["provision_id"])
            metadata = (
                json.loads(row["gloss_metadata"]) if row["gloss_metadata"] else None
            )
            refs = refs_by_atom.get(
                (row["doc_id"], row["rev_id"], row["provision_id"], row["atom_id"])
            )
            if refs is None:
                raw_refs = row["refs"]
                if raw_refs:
                    try:
                        refs = json.loads(raw_refs)
                    except json.JSONDecodeError:
                        refs = [raw_refs]
            grouped_atoms[key].append(
                Atom(
                    type=row["type"],
                    role=row["role"],
                    party=row["party"],
                    who=row["who"],
                    who_text=row["who_text"],
                    conditions=row["conditions"],
                    text=row["text"],
                    refs=list(refs or []),
                    gloss=row["gloss"],
                    gloss_metadata=metadata,
                )
            )

        if not grouped_atoms:
            return

        with self.conn:
            for (doc_id, rev_id, provision_id), atoms in grouped_atoms.items():
                provision = Provision(text="", atoms=list(atoms))
                provision.ensure_rule_atoms()
                if not provision.rule_atoms:
                    continue
                self._persist_rule_structures(
                    doc_id, rev_id, provision_id, provision.rule_atoms
                )
