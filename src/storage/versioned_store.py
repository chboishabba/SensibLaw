from __future__ import annotations

import sqlite3
import json
import difflib
from collections import defaultdict
import hashlib
import re
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Tuple

from models.document import Document, DocumentMetadata, DocumentTOCEntry
from models.provision import (
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
        self._ensure_toc_page_number_column()

    @contextmanager
    def _temporary_doc_prefix(
        self, metadata: Optional[DocumentMetadata | Mapping[str, Any]]
    ) -> Any:
        """Temporarily expose the stable ID prefix derived from ``metadata``."""

        previous = getattr(self, "_active_doc_prefix", None)
        if metadata is not None:
            self._active_doc_prefix = self._document_stable_prefix(metadata)
        try:
            yield
        finally:
            if metadata is not None:
                if previous is None:
                    try:
                        delattr(self, "_active_doc_prefix")
                    except AttributeError:
                        pass
                else:
                    self._active_doc_prefix = previous

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

                CREATE TABLE IF NOT EXISTS toc (
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
                    PRIMARY KEY (doc_id, rev_id, toc_id),
                    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id),
                    FOREIGN KEY (doc_id, rev_id, parent_id)
                        REFERENCES toc(doc_id, rev_id, toc_id)
                );

                CREATE INDEX IF NOT EXISTS idx_toc_doc_rev
                ON toc(doc_id, rev_id, toc_id);

                CREATE INDEX IF NOT EXISTS idx_toc_parent
                ON toc(doc_id, rev_id, parent_id);

                DROP INDEX IF EXISTS idx_toc_stable;
                CREATE UNIQUE INDEX idx_toc_stable
                ON toc(doc_id, stable_id);

                CREATE TABLE IF NOT EXISTS provisions (
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
                    PRIMARY KEY (doc_id, rev_id, provision_id),
                    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id),
                    FOREIGN KEY (doc_id, rev_id, toc_id)
                        REFERENCES toc(doc_id, rev_id, toc_id)
                );

                CREATE INDEX IF NOT EXISTS idx_provisions_doc_rev
                ON provisions(doc_id, rev_id, provision_id);


                CREATE TABLE IF NOT EXISTS rule_atoms (
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
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id)
                        REFERENCES provisions(doc_id, rev_id, provision_id),
                    FOREIGN KEY (doc_id, rev_id, toc_id)
                        REFERENCES toc(doc_id, rev_id, toc_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_atoms_doc_rev
                ON rule_atoms(doc_id, rev_id, provision_id);

                DROP INDEX IF EXISTS idx_rule_atoms_unique_text;
                CREATE UNIQUE INDEX idx_rule_atoms_unique_text
                ON rule_atoms(doc_id, stable_id, party, role, text_hash);


                CREATE INDEX IF NOT EXISTS idx_rule_atoms_toc
                ON rule_atoms(doc_id, rev_id, toc_id);

                CREATE TABLE IF NOT EXISTS rule_atom_subjects (
                    doc_id INTEGER NOT NULL,
                    rev_id INTEGER NOT NULL,
                    provision_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
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
                    glossary_id INTEGER,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
                        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_atom_subjects_doc_rev
                ON rule_atom_subjects(doc_id, rev_id, provision_id);

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
                    glossary_id INTEGER,
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
                    text_hash TEXT,
                    atom_type TEXT,
                    role TEXT,
                    text TEXT,
                    conditions TEXT,
                    gloss TEXT,
                    gloss_metadata TEXT,
                    glossary_id INTEGER,
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
                    glossary_id INTEGER,
                    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id, ref_index),
                    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id, element_id)
                        REFERENCES rule_elements(doc_id, rev_id, provision_id, rule_id, element_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rule_element_refs_doc_rev
                ON rule_element_references(doc_id, rev_id, provision_id, rule_id, element_id);

                CREATE TABLE IF NOT EXISTS glossary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT UNIQUE NOT NULL,
                    definition TEXT NOT NULL,
                    metadata TEXT
                );

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
                    PRIMARY KEY (doc_id, rev_id, provision_id, atom_id, ref_index)
                );

                CREATE INDEX IF NOT EXISTS idx_atom_references_doc_rev
                ON atom_references(doc_id, rev_id, provision_id, atom_id);

                CREATE VIRTUAL TABLE IF NOT EXISTS revisions_fts USING fts5(
                    body, metadata, content='revisions', content_rowid='rowid'
                );
                """
            )
        self._ensure_column("rule_atoms", "text_hash", "TEXT")
        self._ensure_column("rule_elements", "text_hash", "TEXT")
        self._populate_text_hashes()
        self._backfill_toc_stable_ids()
        self._deduplicate_rule_atoms()
        self._ensure_unique_indexes()
        self._ensure_document_json_column()
        self._backfill_rule_tables()
        self._ensure_atoms_view()
        self._ensure_column("rule_atoms", "glossary_id", "INTEGER")
        self._ensure_column("rule_atom_subjects", "glossary_id", "INTEGER")
        self._ensure_column("rule_elements", "glossary_id", "INTEGER")
        self._ensure_column("rule_atom_references", "glossary_id", "INTEGER")
        self._ensure_column("rule_element_references", "glossary_id", "INTEGER")

        self._backfill_glossary_ids()

    def _ensure_toc_page_number_column(self) -> None:
        cur = self.conn.execute("PRAGMA table_info(toc)")
        existing = {row["name"] for row in cur.fetchall()}
        if "page_number" in existing:
            return
        with self.conn:
            self.conn.execute("ALTER TABLE toc ADD COLUMN page_number INTEGER")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        if self._object_type(table) != "table":
            return
        cur = self.conn.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cur.fetchall()}
        if column not in existing:
            with self.conn:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )

    def _populate_text_hashes(self) -> None:
        """Populate missing text hash values for rule atoms and elements."""

        with self.conn:
            atom_rows = self.conn.execute(
                """
                SELECT doc_id, rev_id, provision_id, rule_id, atom_type, role, party,
                       who, who_text, actor, modality, action, conditions, scope, text,
                       subject_gloss, subject_gloss_metadata, text_hash
                FROM rule_atoms
                """
            ).fetchall()

            for row in atom_rows:
                normalised_metadata = self._normalise_json_text(
                    row["subject_gloss_metadata"]
                )
                text_hash = self._compute_rule_atom_hash(
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
                    gloss=row["subject_gloss"],
                    gloss_metadata=normalised_metadata,
                )
                if (
                    row["text_hash"] == text_hash
                    and row["subject_gloss_metadata"] == normalised_metadata
                ):
                    continue
                self.conn.execute(
                    """
                    UPDATE rule_atoms
                    SET text_hash = ?, subject_gloss_metadata = ?
                    WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                    """,
                    (
                        text_hash,
                        normalised_metadata,
                        row["doc_id"],
                        row["rev_id"],
                        row["provision_id"],
                        row["rule_id"],
                    ),
                )

            element_rows = self.conn.execute(
                """
                SELECT doc_id, rev_id, provision_id, rule_id, element_id, atom_type, role,
                       text, conditions, gloss, gloss_metadata, text_hash
                FROM rule_elements
                """
            ).fetchall()

            for row in element_rows:
                normalised_metadata = self._normalise_json_text(row["gloss_metadata"])
                text_hash = self._compute_element_hash(
                    atom_type=row["atom_type"],
                    role=row["role"],
                    text=row["text"],
                    conditions=row["conditions"],
                    gloss=row["gloss"],
                    gloss_metadata=normalised_metadata,
                )
                if (
                    row["text_hash"] == text_hash
                    and row["gloss_metadata"] == normalised_metadata
                ):
                    continue
                self.conn.execute(
                    """
                    UPDATE rule_elements
                    SET text_hash = ?, gloss_metadata = ?
                    WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
                      AND rule_id = ? AND element_id = ?
                    """,
                    (
                        text_hash,
                        normalised_metadata,
                        row["doc_id"],
                        row["rev_id"],
                        row["provision_id"],
                        row["rule_id"],
                        row["element_id"],
                    ),
                )

    def _deduplicate_rule_atoms(self) -> None:
        """Remove duplicated rule atoms prior to enforcing uniqueness."""

        with self.conn:
            duplicate_groups = self.conn.execute(
                """
                SELECT doc_id, stable_id, party, role, text_hash
                FROM rule_atoms
                GROUP BY doc_id, stable_id, party, role, text_hash
                HAVING COUNT(*) > 1
                """
            ).fetchall()

            for group in duplicate_groups:
                doc_id = group["doc_id"]
                stable_id = group["stable_id"]
                party = group["party"]
                role = group["role"]
                text_hash = group["text_hash"]

                rule_rows = self.conn.execute(
                    """
                    SELECT rev_id, provision_id, rule_id
                    FROM rule_atoms
                    WHERE doc_id = ?
                      AND (stable_id = ? OR (stable_id IS NULL AND ? IS NULL))
                      AND (party = ? OR (party IS NULL AND ? IS NULL))
                      AND (role = ? OR (role IS NULL AND ? IS NULL))
                      AND (text_hash = ? OR (text_hash IS NULL AND ? IS NULL))
                    ORDER BY rev_id, provision_id, rule_id
                    """,
                    (
                        doc_id,
                        stable_id,
                        stable_id,
                        party,
                        party,
                        role,
                        role,
                        text_hash,
                        text_hash,
                    ),
                ).fetchall()

                if len(rule_rows) <= 1:
                    continue

                for duplicate in rule_rows[1:]:
                    params = (
                        doc_id,
                        duplicate["rev_id"],
                        duplicate["provision_id"],
                        duplicate["rule_id"],
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_element_references
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_elements
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_atom_references
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_lints
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_atom_subjects
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )
                    self.conn.execute(
                        """
                        DELETE FROM rule_atoms
                        WHERE doc_id = ? AND rev_id = ? AND provision_id = ? AND rule_id = ?
                        """,
                        params,
                    )

    def _compute_rule_atom_hash(
        self,
        *,
        atom_type: Optional[str],
        role: Optional[str],
        party: Optional[str],
        who: Optional[str],
        who_text: Optional[str],
        actor: Optional[str],
        modality: Optional[str],
        action: Optional[str],
        conditions: Optional[str],
        scope: Optional[str],
        text: Optional[str],
        gloss: Optional[str],
        gloss_metadata: Optional[str],
    ) -> str:
        return self._hash_values(
            atom_type,
            role,
            party,
            who,
            who_text,
            actor,
            modality,
            action,
            conditions,
            scope,
            text,
            gloss,
            gloss_metadata,
        )

    def _compute_element_hash(
        self,
        *,
        atom_type: Optional[str],
        role: Optional[str],
        text: Optional[str],
        conditions: Optional[str],
        gloss: Optional[str],
        gloss_metadata: Optional[str],
    ) -> str:
        return self._hash_values(
            atom_type,
            role,
            text,
            conditions,
            gloss,
            gloss_metadata,
        )

    @staticmethod
    def _hash_values(*values: Optional[Any]) -> str:
        """Return a stable hash for the provided sequence of values."""

        normalised: list[str] = []
        for value in values:
            if value is None:
                normalised.append("")
            else:
                normalised.append(str(value).strip())
        payload = "\u241f".join(normalised)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalise_json_text(value: Optional[Any]) -> Optional[str]:
        """Return a normalised JSON string or ``None`` if no value is present."""

        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return text
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _serialise_metadata(metadata: Optional[Any]) -> Optional[str]:
        """Serialise metadata values into a deterministic JSON string."""

        if metadata is None:
            return None
        if isinstance(metadata, (str, bytes)):
            return VersionedStore._normalise_json_text(metadata)
        return json.dumps(metadata, sort_keys=True, separators=(",", ":"))

    def _ensure_unique_indexes(self) -> None:
        """Create the uniqueness constraint for structured rule atoms."""

        with self.conn:
            self.conn.execute("DROP INDEX IF EXISTS idx_rule_atoms_unique_text")
            self.conn.execute(
                """
                CREATE UNIQUE INDEX idx_rule_atoms_unique_text
                ON rule_atoms(doc_id, stable_id, party, role, text_hash)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rule_atoms_toc
                ON rule_atoms(doc_id, rev_id, toc_id)
                """
            )

    def _ensure_document_json_column(self) -> None:
        """Ensure the revisions table includes the ``document_json`` column."""

        cur = self.conn.execute("PRAGMA table_info(revisions)")
        columns = {row["name"] for row in cur.fetchall()}
        if "document_json" not in columns:
            with self.conn:
                self.conn.execute("ALTER TABLE revisions ADD COLUMN document_json TEXT")

    def _object_type(self, name: str) -> Optional[str]:
        """Return the SQLite object type for ``name`` if it exists."""

        row = self.conn.execute(
            "SELECT type FROM sqlite_master WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return row["type"]

    def _ensure_atoms_view(self) -> None:
        """Replace the legacy atoms table with a compatibility view."""

        object_type = self._object_type("atoms")
        with self.conn:
            if object_type == "table":
                self.conn.execute("DROP TABLE atoms")
            elif object_type == "view":
                self.conn.execute("DROP VIEW atoms")
            self.conn.execute("DROP INDEX IF EXISTS idx_atoms_doc_rev")
            self._create_atoms_view()

    def _create_atoms_view(self) -> None:
        """Create the atoms compatibility view."""

        self.conn.executescript(
            """
            CREATE VIEW IF NOT EXISTS atoms AS
            WITH subject_rows AS (
                SELECT
                    ra.doc_id AS doc_id,
                    ra.rev_id AS rev_id,
                    ra.provision_id AS provision_id,
                    ra.rule_id AS rule_id,
                    0 AS group_order,
                    0 AS sequence_order,
                    COALESCE(rs.type, ra.atom_type, 'rule') AS type,
                    COALESCE(rs.role, ra.role) AS role,
                    COALESCE(rs.party, ra.party) AS party,
                    COALESCE(rs.who, ra.who) AS who,
                    COALESCE(rs.who_text, ra.who_text) AS who_text,
                    COALESCE(rs.text, ra.text) AS text,
                    COALESCE(rs.conditions, ra.conditions) AS conditions,
                    rs.refs AS refs,
                    COALESCE(rs.gloss, ra.subject_gloss) AS gloss,
                    COALESCE(rs.gloss_metadata, ra.subject_gloss_metadata) AS gloss_metadata,
                    COALESCE(rs.glossary_id, ra.glossary_id) AS glossary_id
                FROM rule_atoms AS ra
                LEFT JOIN rule_atom_subjects AS rs
                    ON ra.doc_id = rs.doc_id
                    AND ra.rev_id = rs.rev_id
                    AND ra.provision_id = rs.provision_id
                    AND ra.rule_id = rs.rule_id
            ), element_reference_json AS (
                SELECT
                    doc_id,
                    rev_id,
                    provision_id,
                    rule_id,
                    element_id,
                    json_group_array(
                        COALESCE(
                            citation_text,
                            TRIM(
                                (CASE WHEN work IS NOT NULL AND work <> '' THEN work || ' ' ELSE '' END) ||
                                (CASE WHEN section IS NOT NULL AND section <> '' THEN section || ' ' ELSE '' END) ||
                                COALESCE(pinpoint, '')
                            )
                        )
                    ) AS refs
                FROM rule_element_references
                GROUP BY doc_id, rev_id, provision_id, rule_id, element_id
            ), element_rows AS (
                SELECT
                    ra.doc_id AS doc_id,
                    ra.rev_id AS rev_id,
                    ra.provision_id AS provision_id,
                    re.rule_id AS rule_id,
                    1 AS group_order,
                    re.element_id AS sequence_order,
                    COALESCE(re.atom_type, 'element') AS type,
                    re.role AS role,
                    ra.party AS party,
                    ra.who AS who,
                    ra.who_text AS who_text,
                    re.text AS text,
                    re.conditions AS conditions,
                    er.refs AS refs,
                    re.gloss AS gloss,
                    re.gloss_metadata AS gloss_metadata,
                    COALESCE(re.glossary_id, ra.glossary_id) AS glossary_id
                FROM rule_elements AS re
                JOIN rule_atoms AS ra
                    ON ra.doc_id = re.doc_id
                    AND ra.rev_id = re.rev_id
                    AND ra.provision_id = re.provision_id
                    AND ra.rule_id = re.rule_id
                LEFT JOIN element_reference_json AS er
                    ON re.doc_id = er.doc_id
                    AND re.rev_id = er.rev_id
                    AND re.provision_id = er.provision_id
                    AND re.rule_id = er.rule_id
                    AND re.element_id = er.element_id
            ), lint_rows AS (
                SELECT
                    ra.doc_id AS doc_id,
                    ra.rev_id AS rev_id,
                    ra.provision_id AS provision_id,
                    rl.rule_id AS rule_id,
                    2 AS group_order,
                    rl.lint_id AS sequence_order,
                    COALESCE(rl.atom_type, 'lint') AS type,
                    rl.code AS role,
                    ra.party AS party,
                    ra.who AS who,
                    ra.who_text AS who_text,
                    rl.message AS text,
                    NULL AS conditions,
                    NULL AS refs,
                    ra.subject_gloss AS gloss,
                    rl.metadata AS gloss_metadata,
                    ra.glossary_id AS glossary_id
                FROM rule_lints AS rl
                JOIN rule_atoms AS ra
                    ON rl.doc_id = ra.doc_id
                    AND rl.rev_id = ra.rev_id
                    AND rl.provision_id = ra.provision_id
                    AND rl.rule_id = ra.rule_id
            )
            SELECT
                doc_id,
                rev_id,
                provision_id,
                ROW_NUMBER() OVER (
                    PARTITION BY doc_id, rev_id, provision_id
                    ORDER BY rule_id, group_order, sequence_order
                ) AS atom_id,
                type,
                role,
                party,
                who,
                who_text,
                text,
                conditions,
                refs,
                gloss,
                gloss_metadata,
                glossary_id
            FROM (
                SELECT * FROM subject_rows
                UNION ALL
                SELECT * FROM element_rows
                UNION ALL
                SELECT * FROM lint_rows
            )
            ORDER BY doc_id, rev_id, provision_id, atom_id;
            """
        )
        # Migration: ensure the revisions table has a document_json column
        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(revisions)")
        }
        if "document_json" not in columns:
            self.conn.execute("ALTER TABLE revisions ADD COLUMN document_json TEXT")

        self._ensure_column("atoms", "glossary_id", "INTEGER")
        self._ensure_column("rule_atoms", "glossary_id", "INTEGER")
        self._ensure_column("rule_atom_subjects", "glossary_id", "INTEGER")
        self._ensure_column("rule_elements", "glossary_id", "INTEGER")
        self._ensure_column("rule_atom_references", "glossary_id", "INTEGER")
        self._ensure_column("rule_element_references", "glossary_id", "INTEGER")

        self._backfill_rule_tables()
        self._backfill_glossary_ids()

    # ------------------------------------------------------------------
    def _backfill_glossary_ids(self) -> None:
        """Populate glossary identifiers on stored atoms when possible."""

        rows = self.conn.execute(
            "SELECT id, definition FROM glossary WHERE definition IS NOT NULL"
        ).fetchall()
        if not rows:
            return

        def normalise(text: str) -> str:
            return " ".join(text.strip().split()).lower()

        definition_map = {
            normalise(row["definition"]): row["id"] for row in rows if row["definition"]
        }
        if not definition_map:
            return

        update_targets = [
            ("atoms", ("doc_id", "rev_id", "provision_id", "atom_id"), "gloss"),
            (
                "rule_atoms",
                ("doc_id", "rev_id", "provision_id", "rule_id"),
                "subject_gloss",
            ),
            (
                "rule_atom_subjects",
                ("doc_id", "rev_id", "provision_id", "rule_id"),
                "gloss",
            ),
            (
                "rule_elements",
                ("doc_id", "rev_id", "provision_id", "rule_id", "element_id"),
                "gloss",
            ),
        ]

        for table, key_columns, gloss_column in update_targets:
            if self._object_type(table) != "table":
                continue
            table_columns = {
                row["name"]
                for row in self.conn.execute(f"PRAGMA table_info({table})")
            }
            if "glossary_id" not in table_columns or gloss_column not in table_columns:
                continue
            query = (
                f"SELECT {', '.join(key_columns)}, {gloss_column} AS gloss, glossary_id "
                f"FROM {table} WHERE {gloss_column} IS NOT NULL AND glossary_id IS NULL"
            )
            pending = self.conn.execute(query).fetchall()
            if not pending:
                continue
            for row in pending:
                gloss_value = row["gloss"]
                if not gloss_value:
                    continue
                gloss_id = definition_map.get(normalise(gloss_value))
                if not gloss_id:
                    continue
                where_clause = " AND ".join(f"{col} = ?" for col in key_columns)
                params = [row[col] for col in key_columns]
                with self.conn:
                    self.conn.execute(
                        f"UPDATE {table} SET glossary_id = ? WHERE {where_clause}",
                        [gloss_id, *params],
                    )

        provision_columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(provisions)")
        }
        if "toc_id" not in provision_columns:
            with self.conn:
                self.conn.execute("ALTER TABLE provisions ADD COLUMN toc_id INTEGER")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_provisions_toc ON provisions(doc_id, rev_id, toc_id)"
        )

        rule_atom_columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(rule_atoms)")
        }
        if "toc_id" not in rule_atom_columns:
            with self.conn:
                self.conn.execute("ALTER TABLE rule_atoms ADD COLUMN toc_id INTEGER")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_atoms_toc ON rule_atoms(doc_id, rev_id, toc_id)"
        )

    # ------------------------------------------------------------------
    def _backfill_toc_stable_ids(self) -> None:
        """Ensure TOC rows and rule atoms have deterministic stable identifiers."""

        self._ensure_column("toc", "stable_id", "TEXT")
        self.conn.execute("DROP INDEX IF EXISTS idx_toc_stable")
        self.conn.execute(
            "CREATE UNIQUE INDEX idx_toc_stable ON toc(doc_id, stable_id)"
        )
        self._ensure_column("rule_atoms", "stable_id", "TEXT")
        self.conn.execute("DROP INDEX IF EXISTS idx_rule_atoms_stable")
        self.conn.execute(
            "CREATE INDEX idx_rule_atoms_stable ON rule_atoms(doc_id, stable_id)"
        )

        toc_pending = self.conn.execute(
            """
            SELECT doc_id, rev_id
            FROM toc
            WHERE stable_id IS NULL OR stable_id = ''
            GROUP BY doc_id, rev_id
            """
        ).fetchall()
        rule_pending = self.conn.execute(
            """
            SELECT doc_id, rev_id
            FROM rule_atoms
            WHERE stable_id IS NULL OR stable_id = ''
            GROUP BY doc_id, rev_id
            """
        ).fetchall()

        targets = {(row["doc_id"], row["rev_id"]) for row in toc_pending}
        targets.update((row["doc_id"], row["rev_id"]) for row in rule_pending)
        if not targets:
            return

        for doc_id, rev_id in sorted(targets):
            metadata_row = self.conn.execute(
                "SELECT metadata FROM revisions WHERE doc_id = ? AND rev_id = ?",
                (doc_id, rev_id),
            ).fetchone()
            metadata_dict: dict[str, Any] = {}
            if metadata_row and metadata_row["metadata"]:
                try:
                    metadata_dict = json.loads(metadata_row["metadata"])
                except json.JSONDecodeError:
                    metadata_dict = {}

            toc_rows = self.conn.execute(
                """
                SELECT toc_id, parent_id, node_type, identifier, title, position
                FROM toc
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY toc_id
                """,
                (doc_id, rev_id),
            ).fetchall()
            if not toc_rows:
                continue

            sibling_counters: defaultdict[Tuple[Optional[int], str], int] = defaultdict(
                int
            )
            path_segments: dict[Optional[int], List[str]] = {None: []}
            stable_lookup: dict[int, str] = {}
            doc_prefix = self._document_stable_prefix(metadata_dict)

            for toc_row in toc_rows:
                parent_id = toc_row["parent_id"]
                position = toc_row["position"] if "position" in toc_row.keys() else 0
                component = self._stable_component(
                    parent_id,
                    toc_row["node_type"],
                    toc_row["identifier"],
                    toc_row["title"],
                    position,
                    sibling_counters,
                )
                parent_path = path_segments.get(parent_id, [])
                path = [*parent_path, component]
                path_segments[toc_row["toc_id"]] = path
                stable_id = self._compose_stable_id(doc_prefix, path)
                stable_lookup[toc_row["toc_id"]] = stable_id

            if not stable_lookup:
                continue

            ordered_toc_ids = sorted(stable_lookup)
            update_values = [
                (stable_lookup[toc_id], doc_id, rev_id, toc_id)
                for toc_id in ordered_toc_ids
            ]
            rule_update_values = [
                (stable_lookup[toc_id], doc_id, rev_id, toc_id)
                for toc_id in ordered_toc_ids
            ]

            with self.conn:
                self.conn.executemany(
                    "UPDATE toc SET stable_id = ? WHERE doc_id = ? AND rev_id = ? AND toc_id = ?",
                    update_values,
                )
                self.conn.executemany(
                    """
                    UPDATE rule_atoms
                    SET stable_id = ?
                    WHERE doc_id = ? AND rev_id = ? AND toc_id = ?
                      AND (stable_id IS NULL OR stable_id = '')
                    """,
                    rule_update_values,
                )

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
        with self._temporary_doc_prefix(document.metadata):
            toc_entries = self._build_toc_entries(
                document.provisions, document.toc_entries
            )
        metadata_json = json.dumps(document.metadata.to_dict())
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
            self._store_provisions(
                doc_id, rev_id, document.provisions, toc_entries, document.metadata
            )
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
        toc_entries = self._load_toc_entries(doc_id, rev_id)
        provisions, has_rows = self._load_provisions(doc_id, rev_id)
        if has_rows:
            return Document(
                metadata=metadata,
                body=body,
                provisions=provisions,
                toc_entries=toc_entries,
            )
        if document_json:
            document = Document.from_json(document_json)
            if not document.toc_entries and toc_entries:
                document.toc_entries = toc_entries
            return document
        return Document(metadata=metadata, body=body, toc_entries=toc_entries)

    def _build_toc_entries(
        self,
        provisions: List[Provision],
        toc_structure: Optional[List[DocumentTOCEntry]] = None,
    ) -> List[
        Tuple[
            int,
            Optional[int],
            int,
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[int],
        ]
    ]:
        """Assign sequential TOC identifiers, merging parsed TOC structure."""

        if not provisions and not toc_structure:
            return []

        entries: List[dict[str, Any]] = []
        counter = 0
        position_counters: defaultdict[Optional[int], int] = defaultdict(int)
        sibling_counters: defaultdict[Tuple[Optional[int], str], int] = defaultdict(int)
        path_segments: dict[Optional[int], List[str]] = {None: []}
        toc_map: dict[Tuple[str, str], int] = {}
        rows_by_id: dict[int, dict[str, Any]] = {}

        doc_prefix = getattr(self, "_active_doc_prefix", None)
        if not doc_prefix:
            doc_prefix = self._document_stable_prefix({})

        def normalise_identifier(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            collapsed = re.sub(r"\s+", "", value).strip().lower()
            collapsed = collapsed.rstrip(".")
            return collapsed or None

        def make_key(
            node_type: Optional[str], identifier: Optional[str]
        ) -> Optional[Tuple[str, str]]:
            if not node_type:
                return None
            normalised_type = node_type.strip().lower()
            normalised_identifier = normalise_identifier(identifier)
            if not normalised_type or normalised_identifier is None:
                return None
            return normalised_type, normalised_identifier

        def register_entry(
            parent_id: Optional[int],
            node_type: Optional[str],
            identifier: Optional[str],
            title: Optional[str],
            page_number: Optional[int],
        ) -> int:
            nonlocal counter
            counter += 1
            toc_id = counter
            position_counters[parent_id] += 1
            position = position_counters[parent_id]
            component = self._stable_component(
                parent_id,
                node_type,
                identifier,
                title,
                position,
                sibling_counters,
            )
            path = [*path_segments.get(parent_id, []), component]
            path_segments[toc_id] = path
            stable_id = self._compose_stable_id(doc_prefix, path)
            row = {
                "toc_id": toc_id,
                "parent_id": parent_id,
                "position": position,
                "stable_id": stable_id,
                "node_type": node_type,
                "identifier": identifier,
                "title": title,
                "page_number": page_number,
            }
            entries.append(row)
            rows_by_id[toc_id] = row
            key = make_key(node_type, identifier)
            if key:
                toc_map[key] = toc_id
            return toc_id

        def flatten_toc(
            nodes: List[DocumentTOCEntry], parent_id: Optional[int]
        ) -> None:
            for node in nodes:
                toc_id = register_entry(
                    parent_id,
                    node.node_type,
                    node.identifier,
                    node.title,
                    node.page_number,
                )
                flatten_toc(node.children, toc_id)

        if toc_structure:
            flatten_toc(toc_structure, None)

        def traverse(provision: Provision, parent_toc_id: Optional[int]) -> None:
            key = make_key(provision.node_type, provision.identifier)
            toc_id = toc_map.get(key)
            if toc_id is None:
                toc_id = register_entry(
                    parent_toc_id,
                    provision.node_type,
                    provision.identifier,
                    provision.heading,
                    None,
                )
            row = rows_by_id[toc_id]
            if row.get("title") is None and provision.heading:
                row["title"] = provision.heading
            if row.get("node_type") is None and provision.node_type:
                row["node_type"] = provision.node_type
            if row.get("identifier") is None and provision.identifier:
                row["identifier"] = provision.identifier
                new_key = make_key(row.get("node_type"), row.get("identifier"))
                if new_key:
                    toc_map[new_key] = toc_id
            provision.toc_id = toc_id
            provision.stable_id = row["stable_id"]
            for child in provision.children:
                traverse(child, toc_id)

        for provision in provisions:
            traverse(provision, None)

        return [
            (
                row["toc_id"],
                row["parent_id"],
                row["position"],
                row["stable_id"],
                row.get("node_type"),
                row.get("identifier"),
                row.get("title"),
                row.get("page_number"),
            )
            for row in entries
        ]

    def _load_toc_entries(self, doc_id: int, rev_id: int) -> List[DocumentTOCEntry]:
        rows = self.conn.execute(
            """
            SELECT toc_id, parent_id, node_type, identifier, title, position, page_number
            FROM toc
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY toc_id
            """,
            (doc_id, rev_id),
        ).fetchall()
        if not rows:
            return []

        nodes: dict[int, DocumentTOCEntry] = {}
        children: defaultdict[Optional[int], List[Tuple[int, int]]] = defaultdict(list)

        for row in rows:
            entry = DocumentTOCEntry(
                node_type=row["node_type"],
                identifier=row["identifier"],
                title=row["title"],
                page_number=row["page_number"],
                children=[],
            )
            nodes[row["toc_id"]] = entry
            children[row["parent_id"]].append((row["position"], row["toc_id"]))

        def build(parent_id: Optional[int]) -> List[DocumentTOCEntry]:
            ordered = sorted(
                children.get(parent_id, []), key=lambda item: (item[0], item[1])
            )
            result: List[DocumentTOCEntry] = []
            for _, child_id in ordered:
                node = nodes[child_id]
                node.children = build(child_id)
                result.append(node)
            return result

        return build(None)

    def _slugify(self, value: Optional[str]) -> str:
        if value is None:
            return ""
        text = value.strip().lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")

    def _document_stable_prefix(
        self, metadata: DocumentMetadata | Mapping[str, Any]
    ) -> str:
        if isinstance(metadata, DocumentMetadata):
            jurisdiction_value: Any = metadata.jurisdiction
            citation_value: Any = metadata.citation
        else:
            jurisdiction_value = metadata.get("jurisdiction") if metadata else None
            citation_value = metadata.get("citation") if metadata else None
        jurisdiction = self._slugify(
            str(jurisdiction_value) if jurisdiction_value else None
        )
        citation = self._slugify(str(citation_value) if citation_value else None)
        if not jurisdiction:
            jurisdiction = "unknown-jurisdiction"
        if not citation:
            citation = "unknown-citation"
        return f"{jurisdiction}/{citation}"

    def _stable_component(
        self,
        parent_id: Optional[int],
        node_type: Optional[str],
        identifier: Optional[str],
        heading: Optional[str],
        position: int,
        sibling_counters: defaultdict[Tuple[Optional[int], str], int],
    ) -> str:
        slug_type = self._slugify(node_type) or "node"
        slug_identifier = self._slugify(identifier)
        slug_heading = self._slugify(heading)
        if slug_identifier:
            base = f"{slug_type}-{slug_identifier}"
        elif slug_heading:
            base = f"{slug_type}-{slug_heading}"
        else:
            base = f"{slug_type}-pos{position}"
        key = (parent_id, base)
        sibling_counters[key] += 1
        occurrence = sibling_counters[key]
        if occurrence > 1:
            base = f"{base}-{occurrence}"
        return base

    def _compose_stable_id(self, prefix: str, path: List[str]) -> str:
        segments = [prefix]
        segments.extend(segment for segment in path if segment)
        return "/".join(segments)

    def _store_provisions(
        self,
        doc_id: int,
        rev_id: int,
        provisions: List[Provision],
        toc_entries: Optional[
            List[
                Tuple[
                    int,
                    Optional[int],
                    int,
                    str,
                    Optional[str],
                    Optional[str],
                    Optional[str],
                    Optional[int],
                ]
            ]
        ] = None,
        metadata: Optional[DocumentMetadata] = None,
    ) -> None:
        """Persist provision and atom data for a revision."""

        atoms_is_table = self._object_type("atoms") == "table"

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
            "DELETE FROM rule_atom_subjects WHERE doc_id = ? AND rev_id = ?",
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
        if atoms_is_table:
            self.conn.execute(
                "DELETE FROM atoms WHERE doc_id = ? AND rev_id = ?",
                (doc_id, rev_id),
            )
        self.conn.execute(
            "DELETE FROM provisions WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )
        self.conn.execute(
            "DELETE FROM toc WHERE doc_id = ? AND rev_id = ?",
            (doc_id, rev_id),
        )

        if not provisions:
            return

        if toc_entries is None:
            if metadata is None:
                raise ValueError("Document metadata is required to build TOC entries")
            with self._temporary_doc_prefix(metadata):
                toc_entries = self._build_toc_entries(provisions)

        toc_values: List[
            Tuple[
                int,
                int,
                int,
                Optional[int],
                Optional[str],
                Optional[str],
                Optional[str],
                str,
                int,
                Optional[int],
            ]
        ] = []
        for (
            toc_id,
            parent_toc_id,
            position,
            stable_id,
            node_type,
            identifier,
            title,
            page_number,
        ) in toc_entries:
            toc_values.append(
                (
                    doc_id,
                    rev_id,
                    toc_id,
                    parent_toc_id,
                    node_type,
                    identifier,
                    title,
                    stable_id,
                    position,
                    page_number,
                )
            )

        if toc_values:
            self.conn.executemany(
                """
                INSERT INTO toc (
                    doc_id, rev_id, toc_id, parent_id, node_type, identifier, title,
                    stable_id, position, page_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                toc_values,
            )

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
                    heading, node_type, toc_id, text, rule_tokens, references_json,
                    principles, customs, cultural_flags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    rev_id,
                    current_id,
                    parent_id,
                    provision.identifier,
                    provision.heading,
                    provision.node_type,
                    provision.toc_id,
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
                    doc_id,
                    rev_id,
                    current_id,
                    provision.rule_atoms,
                    provision.toc_id,
                    provision.stable_id,
                )

            if atoms_is_table:
                unique_atoms: list[Atom] = []
                seen_atom_keys: set[tuple[Any, ...]] = set()

                for atom in provision.atoms:
                    metadata_json = self._serialise_metadata(atom.gloss_metadata)
                    key = (
                        atom.type,
                        atom.role,
                        atom.party,
                        atom.who,
                        atom.who_text,
                        atom.conditions,
                        atom.text,
                        tuple(atom.refs),
                        atom.gloss,
                        metadata_json,
                    )
                    if key in seen_atom_keys:
                        continue
                    seen_atom_keys.add(key)
                    unique_atoms.append(atom)

                for atom_index, atom in enumerate(unique_atoms, start=1):
                    gloss_metadata_json = self._serialise_metadata(
                        atom.gloss_metadata
                    )
                    refs_json = json.dumps(atom.refs) if atom.refs else None
                    self.conn.execute(
                        """
                        INSERT INTO atoms (
                            doc_id, rev_id, provision_id, atom_id, type, role,
                            party, who, who_text, text, conditions, refs, gloss,
                            gloss_metadata, glossary_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            refs_json,
                            atom.gloss,
                            gloss_metadata_json,
                            atom.glossary_id,
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
                   node_type, toc_id, text, rule_tokens, references_json, principles, customs,
                   cultural_flags
            FROM provisions
            WHERE doc_id = ? AND rev_id = ?
            ORDER BY provision_id
            """,
            (doc_id, rev_id),
        ).fetchall()
        if not provision_rows:
            return [], False

        toc_rows = self.conn.execute(
            """
            SELECT toc_id, stable_id
            FROM toc
            WHERE doc_id = ? AND rev_id = ?
            """,
            (doc_id, rev_id),
        ).fetchall()
        toc_stable_map = {row["toc_id"]: row["stable_id"] for row in toc_rows}

        rule_atom_rows = self.conn.execute(
            """
            SELECT
                ra.provision_id,
                ra.rule_id,
                ra.toc_id,
                ra.stable_id,
                ra.atom_type,
                ra.role,
                ra.party,
                ra.who,
                ra.who_text,
                ra.actor,
                ra.modality,
                ra.action,
                ra.conditions,
                ra.scope,
                ra.text,
                ra.subject_gloss,
                ra.subject_gloss_metadata,
                ra.glossary_id AS rule_glossary_id,
                rs.type AS subject_type,
                rs.role AS subject_role,
                rs.party AS subject_party,
                rs.who AS subject_who,
                rs.who_text AS subject_who_text,
                rs.text AS subject_text,
                rs.conditions AS subject_conditions,
                rs.refs AS subject_refs,
                rs.gloss AS subject_gloss_value,
                rs.gloss_metadata AS subject_gloss_metadata_json,
                rs.glossary_id AS subject_glossary_id
            FROM rule_atoms AS ra
            LEFT JOIN rule_atom_subjects AS rs
                ON ra.doc_id = rs.doc_id
                AND ra.rev_id = rs.rev_id
                AND ra.provision_id = rs.provision_id
                AND ra.rule_id = rs.rule_id
            WHERE ra.doc_id = ? AND ra.rev_id = ?
            ORDER BY ra.provision_id, ra.rule_id
            """,
            (doc_id, rev_id),
        ).fetchall()

        using_structured = bool(rule_atom_rows)

        rule_atoms_by_provision: dict[int, List[RuleAtom]] = defaultdict(list)

        if using_structured:
            atom_reference_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, ref_index, work, section, pinpoint, citation_text, glossary_id
                FROM rule_atom_references
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, ref_index
                """,
                (doc_id, rev_id),
            ).fetchall()
            element_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, element_id, atom_type, role, text, conditions,
                       gloss, gloss_metadata, glossary_id
                FROM rule_elements
                WHERE doc_id = ? AND rev_id = ?
                ORDER BY provision_id, rule_id, element_id
                """,
                (doc_id, rev_id),
            ).fetchall()
            element_reference_rows = self.conn.execute(
                """
                SELECT provision_id, rule_id, element_id, ref_index, work, section, pinpoint, citation_text, glossary_id
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
                        glossary_id=row["glossary_id"],
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
                        glossary_id=row["glossary_id"],
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
                        glossary_id=ref.glossary_id,
                    )
                    for ref in atom_refs_map.get(
                        (row["provision_id"], row["rule_id"]), []
                    )
                ]
                rule_atom = RuleAtom(
                    toc_id=row["toc_id"],
                    stable_id=row["stable_id"],
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
                    glossary_id=row["rule_glossary_id"],
                    references=references,
                )
                if not rule_atom.stable_id and row["toc_id"] is not None:
                    rule_atom.stable_id = toc_stable_map.get(row["toc_id"])

                subject_metadata = (
                    json.loads(row["subject_gloss_metadata_json"])
                    if row["subject_gloss_metadata_json"]
                    else None
                )
                raw_subject_refs = row["subject_refs"]
                subject_refs: List[str] = []
                if raw_subject_refs:
                    try:
                        parsed_refs = json.loads(raw_subject_refs)
                    except json.JSONDecodeError:
                        parsed_refs = [raw_subject_refs]
                    if isinstance(parsed_refs, list):
                        subject_refs = [str(ref) for ref in parsed_refs]
                    else:
                        subject_refs = [str(parsed_refs)]

                if any(
                    row[column] is not None
                    for column in (
                        "subject_type",
                        "subject_role",
                        "subject_party",
                        "subject_who",
                        "subject_who_text",
                        "subject_text",
                        "subject_conditions",
                        "subject_gloss_value",
                        "subject_gloss_metadata_json",
                    )
                ):
                    subject_atom = Atom(
                        type=row["subject_type"],
                        role=row["subject_role"],
                        party=row["subject_party"],
                        who=row["subject_who"],
                        who_text=row["subject_who_text"],
                        text=row["subject_text"],
                        conditions=row["subject_conditions"],
                        refs=subject_refs,
                        gloss=row["subject_gloss_value"],
                        gloss_metadata=subject_metadata,
                        glossary_id=row["subject_glossary_id"],
                    )
                    rule_atom.subject = subject_atom
                    if subject_atom.type is not None:
                        rule_atom.atom_type = subject_atom.type
                    if subject_atom.role is not None:
                        rule_atom.role = subject_atom.role
                    if subject_atom.party is not None:
                        rule_atom.party = subject_atom.party
                    if subject_atom.who is not None:
                        rule_atom.who = subject_atom.who
                    if subject_atom.who_text is not None:
                        rule_atom.who_text = subject_atom.who_text
                    if subject_atom.text is not None:
                        rule_atom.text = subject_atom.text
                    if subject_atom.conditions is not None:
                        rule_atom.conditions = subject_atom.conditions
                    if subject_atom.gloss is not None:
                        rule_atom.subject_gloss = subject_atom.gloss
                    if subject_atom.gloss_metadata is not None:
                        rule_atom.subject_gloss_metadata = subject_atom.gloss_metadata

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
                        glossary_id=ref.glossary_id,
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
                    glossary_id=row["glossary_id"],
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
            pass

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
                toc_id=row["toc_id"],
                rule_tokens=rule_tokens,
                cultural_flags=cultural_flags,
                references=references,
                principles=list(principles),
                customs=list(customs),
            )
            provision.stable_id = toc_stable_map.get(row["toc_id"])
            if using_structured:
                provision.rule_atoms.extend(
                    rule_atoms_by_provision.get(row["provision_id"], [])
                )
                provision.sync_legacy_atoms()
            else:
                provision.legacy_atoms_factory = self._make_legacy_atoms_factory(
                    doc_id, rev_id, row["provision_id"]
                )
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
        has_legacy_atoms = self._revision_has_atoms(doc_id, rev_id)
        has_rows = bool(provision_rows) and (using_structured or has_legacy_atoms)
        return ordered_roots, has_rows

    def _make_legacy_atoms_factory(
        self, doc_id: int, rev_id: int, provision_id: int
    ) -> Callable[[Optional[Any]], List[Atom]]:
        """Return a callable that lazily loads legacy atoms from the compatibility view."""

        def factory(_: Optional[Any] = None) -> List[Atom]:
            atom_rows = self.conn.execute(
                """
                SELECT atom_id, type, role, party, who, who_text, text,
                       conditions, refs, gloss, gloss_metadata, glossary_id
                FROM atoms
                WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
                ORDER BY atom_id
                """,
                (doc_id, rev_id, provision_id),
            ).fetchall()
            if not atom_rows:
                return []

            atom_reference_rows = self.conn.execute(
                """
                SELECT atom_id, ref_index, work, section, pinpoint, citation_text
                FROM atom_references
                WHERE doc_id = ? AND rev_id = ? AND provision_id = ?
                ORDER BY atom_id, ref_index
                """,
                (doc_id, rev_id, provision_id),
            ).fetchall()

            refs_by_atom: dict[int, List[str]] = {}
            for ref_row in atom_reference_rows:
                ref_text = ref_row["citation_text"]
                if not ref_text:
                    parts = [ref_row["work"], ref_row["section"], ref_row["pinpoint"]]
                    ref_text = " ".join(part for part in parts if part)
                refs_by_atom.setdefault(ref_row["atom_id"], []).append(ref_text or "")

            atoms: List[Atom] = []
            for atom_row in atom_rows:
                refs = refs_by_atom.get(atom_row["atom_id"])
                if refs is None:
                    refs = json.loads(atom_row["refs"]) if atom_row["refs"] else []
                gloss_metadata = (
                    json.loads(atom_row["gloss_metadata"])
                    if atom_row["gloss_metadata"]
                    else None
                )
                atoms.append(
                    Atom(
                        type=atom_row["type"],
                        role=atom_row["role"],
                        party=atom_row["party"],
                        who=atom_row["who"],
                        who_text=atom_row["who_text"],
                        conditions=atom_row["conditions"],
                        text=atom_row["text"],
                        refs=list(refs),
                        gloss=atom_row["gloss"],
                        gloss_metadata=gloss_metadata,
                        glossary_id=atom_row["glossary_id"],
                    )
                )
            return atoms

        return factory

    def _revision_has_atoms(self, doc_id: int, rev_id: int) -> bool:
        """Return ``True`` when legacy atoms exist for the revision."""

        row = self.conn.execute(
            "SELECT 1 FROM atoms WHERE doc_id = ? AND rev_id = ? LIMIT 1",
            (doc_id, rev_id),
        ).fetchone()
        return row is not None

    def _persist_rule_structures(
        self,
        doc_id: int,
        rev_id: int,
        provision_id: int,
        rule_atoms: List[RuleAtom],
        toc_id: Optional[int],
        stable_id: Optional[str],
    ) -> None:
        """Persist structured rule data for a provision."""

        def ensure_glossary_reference(
            references: List[RuleReference], glossary_id: Optional[int]
        ) -> List[RuleReference]:
            if glossary_id is None:
                return references
            for reference in references:
                if getattr(reference, "glossary_id", None) == glossary_id:
                    return references
            return [*references, RuleReference(glossary_id=glossary_id)]

        seen_hashes: set[str] = set()
        rule_counter = 0

        for rule_atom in rule_atoms:
            subject_atom = rule_atom.get_subject_atom()
            rule_atom.subject = subject_atom
            rule_atom.subject_gloss = subject_atom.gloss
            rule_atom.subject_gloss_metadata = subject_atom.gloss_metadata
            rule_atom.party = subject_atom.party
            rule_atom.who = subject_atom.who
            rule_atom.who_text = subject_atom.who_text
            rule_atom.text = subject_atom.text
            rule_atom.conditions = subject_atom.conditions
            current_toc_id = (
                rule_atom.toc_id if rule_atom.toc_id is not None else toc_id
            )
            rule_atom.toc_id = current_toc_id
            if rule_atom.stable_id is None:
                rule_atom.stable_id = stable_id
            subject_metadata_json = self._serialise_metadata(
                subject_atom.gloss_metadata
            )
            atom_hash = self._compute_rule_atom_hash(
                atom_type=rule_atom.atom_type,
                role=rule_atom.role,
                party=rule_atom.party,
                who=rule_atom.who,
                who_text=rule_atom.who_text,
                actor=rule_atom.actor,
                modality=rule_atom.modality,
                action=rule_atom.action,
                conditions=rule_atom.conditions,
                scope=rule_atom.scope,
                text=rule_atom.text,
                gloss=rule_atom.subject_gloss,
                gloss_metadata=subject_metadata_json,
            )
            if atom_hash in seen_hashes:
                continue
            seen_hashes.add(atom_hash)
            rule_counter += 1
            rule_index = rule_counter
            self.conn.execute(
                """
                INSERT INTO rule_atoms (
                    doc_id, rev_id, provision_id, rule_id, text_hash, toc_id, stable_id, atom_type, role, party,
                    who, who_text, actor, modality, action, conditions, scope,
                    text, subject_gloss, subject_gloss_metadata, glossary_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (doc_id, rev_id, provision_id, rule_id) DO UPDATE SET
                    text_hash = excluded.text_hash,
                    toc_id = excluded.toc_id,
                    atom_type = excluded.atom_type,
                    role = excluded.role,
                    party = excluded.party,
                    who = excluded.who,
                    who_text = excluded.who_text,
                    actor = excluded.actor,
                    modality = excluded.modality,
                    action = excluded.action,
                    conditions = excluded.conditions,
                    scope = excluded.scope,
                    text = excluded.text,
                    subject_gloss = excluded.subject_gloss,
                    subject_gloss_metadata = excluded.subject_gloss_metadata,
                    glossary_id = excluded.glossary_id
                """,
                (
                    doc_id,
                    rev_id,
                    provision_id,
                    rule_index,
                    atom_hash,
                    current_toc_id,
                    rule_atom.stable_id,
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
                    rule_atom.glossary_id,
                ),
            )

            refs_json = json.dumps(subject_atom.refs) if subject_atom.refs else None
            self.conn.execute(
                """
                INSERT INTO rule_atom_subjects (
                    doc_id, rev_id, provision_id, rule_id, type, role, party, who,
                    who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (doc_id, rev_id, provision_id, rule_id) DO UPDATE SET
                    type = excluded.type,
                    role = excluded.role,
                    party = excluded.party,
                    who = excluded.who,
                    who_text = excluded.who_text,
                    text = excluded.text,
                    conditions = excluded.conditions,
                    refs = excluded.refs,
                    gloss = excluded.gloss,
                    gloss_metadata = excluded.gloss_metadata,
                    glossary_id = excluded.glossary_id
                """,
                (
                    doc_id,
                    rev_id,
                    provision_id,
                    rule_index,
                    subject_atom.type,
                    subject_atom.role,
                    subject_atom.party,
                    subject_atom.who,
                    subject_atom.who_text,
                    subject_atom.text,
                    subject_atom.conditions,
                    refs_json,
                    subject_atom.gloss,
                    subject_metadata_json,
                    subject_atom.glossary_id,
                ),
            )

            rule_atom.references = ensure_glossary_reference(
                list(rule_atom.references), rule_atom.glossary_id
            )
            for ref_index, ref in enumerate(rule_atom.references, start=1):
                self.conn.execute(
                    """
                    INSERT INTO rule_atom_references (
                        doc_id, rev_id, provision_id, rule_id, ref_index,
                        work, section, pinpoint, citation_text, glossary_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (doc_id, rev_id, provision_id, rule_id, ref_index) DO UPDATE SET
                        work = excluded.work,
                        section = excluded.section,
                        pinpoint = excluded.pinpoint,
                        citation_text = excluded.citation_text
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
                        ref.glossary_id,
                    ),
                )

            for element_index, element in enumerate(rule_atom.elements, start=1):
                element_metadata_json = self._serialise_metadata(
                    element.gloss_metadata
                )
                element_hash = self._compute_element_hash(
                    atom_type=element.atom_type,
                    role=element.role,
                    text=element.text,
                    conditions=element.conditions,
                    gloss=element.gloss,
                    gloss_metadata=element_metadata_json,
                )
                self.conn.execute(
                    """
                    INSERT INTO rule_elements (
                        doc_id, rev_id, provision_id, rule_id, element_id, text_hash, atom_type,
                        role, text, conditions, gloss, gloss_metadata, glossary_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (doc_id, rev_id, provision_id, rule_id, element_id) DO UPDATE SET
                        text_hash = excluded.text_hash,
                        atom_type = excluded.atom_type,
                        role = excluded.role,
                        text = excluded.text,
                        conditions = excluded.conditions,
                        gloss = excluded.gloss,
                        gloss_metadata = excluded.gloss_metadata,
                        glossary_id = excluded.glossary_id
                    """,
                    (
                        doc_id,
                        rev_id,
                        provision_id,
                        rule_index,
                        element_index,
                        element_hash,
                        element.atom_type,
                        element.role,
                        element.text,
                        element.conditions,
                        element.gloss,
                        element_metadata_json,
                        element.glossary_id,
                    ),
                )

                element.references = ensure_glossary_reference(
                    list(element.references), element.glossary_id
                )
                for ref_index, ref in enumerate(element.references, start=1):
                    self.conn.execute(
                        """
                        INSERT INTO rule_element_references (
                            doc_id, rev_id, provision_id, rule_id, element_id, ref_index,
                            work, section, pinpoint, citation_text, glossary_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (
                            doc_id, rev_id, provision_id, rule_id, element_id, ref_index
                        ) DO UPDATE SET
                            work = excluded.work,
                            section = excluded.section,
                            pinpoint = excluded.pinpoint,
                            citation_text = excluded.citation_text
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
                            ref.glossary_id,
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
                    ON CONFLICT (doc_id, rev_id, provision_id, rule_id, lint_id) DO UPDATE SET
                        atom_type = excluded.atom_type,
                        code = excluded.code,
                        message = excluded.message,
                        metadata = excluded.metadata
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

        cur = self.conn.execute("SELECT COUNT(*) FROM rule_atoms")
        rule_atom_count = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) FROM rule_atom_subjects")
        subject_count = cur.fetchone()[0]
        if rule_atom_count and subject_count:
            return

        needs_rule_atoms = rule_atom_count == 0
        needs_subjects = subject_count == 0

        object_type = self._object_type("atoms")
        if object_type is None:
            return

        legacy_count = self.conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        if legacy_count == 0:
            return

        atom_rows = self.conn.execute(
            """
            SELECT doc_id, rev_id, provision_id, atom_id, type, role, party, who, who_text,
                   text, conditions, refs, gloss, gloss_metadata, glossary_id
            FROM atoms
            ORDER BY doc_id, rev_id, provision_id, atom_id
            """
        ).fetchall()
        if not atom_rows:
            return

        reference_rows = self.conn.execute(
            """
            SELECT doc_id, rev_id, provision_id, atom_id, work, section, pinpoint, citation_text
            FROM atom_references
            ORDER BY doc_id, rev_id, provision_id, atom_id, ref_index
            """
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
                    glossary_id=(
                        row["glossary_id"] if "glossary_id" in row.keys() else None
                    ),
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
                if needs_rule_atoms:
                    self._persist_rule_structures(
                        doc_id,
                        rev_id,
                        provision_id,
                        provision.rule_atoms,
                        None,
                        None,
                    )
                elif needs_subjects:
                    for rule_index, rule_atom in enumerate(
                        provision.rule_atoms, start=1
                    ):
                        subject_atom = rule_atom.get_subject_atom()
                        metadata_json = self._serialise_metadata(
                            subject_atom.gloss_metadata
                        )
                        refs_json = (
                            json.dumps(subject_atom.refs) if subject_atom.refs else None
                        )
                        self.conn.execute(
                            """
                                INSERT INTO rule_atom_subjects (
                                    doc_id, rev_id, provision_id, rule_id, type, role, party,
                                    who, who_text, text, conditions, refs, gloss, gloss_metadata, glossary_id
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(doc_id, rev_id, provision_id, rule_id)
                                DO UPDATE SET
                                    type=excluded.type,
                                    role=excluded.role,
                                    party=excluded.party,
                                    who=excluded.who,
                                    who_text=excluded.who_text,
                                    text=excluded.text,
                                    conditions=excluded.conditions,
                                    refs=excluded.refs,
                                    gloss=excluded.gloss,
                                    gloss_metadata=excluded.gloss_metadata,
                                    glossary_id=excluded.glossary_id
                            """,
                            (
                                doc_id,
                                rev_id,
                                provision_id,
                                rule_index,
                                subject_atom.type,
                                subject_atom.role,
                                subject_atom.party,
                                subject_atom.who,
                                subject_atom.who_text,
                                subject_atom.text,
                                subject_atom.conditions,
                                refs_json,
                                subject_atom.gloss,
                                metadata_json,
                                subject_atom.glossary_id,
                            ),
                        )
