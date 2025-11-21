from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from src.models.document import Document
from src.models.provision import RuleAtom
from src.rules import derive_party_metadata


@dataclass(frozen=True)
class AnchorResult:
    """Result of anchoring a rule atom into normalized tables."""

    rule_id: str
    legal_source_id: str
    actor_classes: List[str]


DEFAULT_ACTOR_CLASS_MAP: Mapping[str, str] = {
    "defence": "individual",
    "prosecution": "state_actor",
    "plaintiff": "individual",
    "claimant": "individual",
    "respondent": "individual",
    "unknown": "unknown_actor",
}


class NormalizedOntologyStore:
    """Lightweight SQLite-backed store for ontology anchoring."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self._ensure_schema()

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.connection.close()

    # ------------------------------------------------------------------
    def __enter__(self) -> "NormalizedOntologyStore":
        return self

    # ------------------------------------------------------------------
    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS legal_sources (
                id TEXT PRIMARY KEY,
                citation TEXT NOT NULL,
                jurisdiction TEXT,
                category TEXT
            );
            CREATE TABLE IF NOT EXISTS actor_classes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS rule_atoms (
                id TEXT PRIMARY KEY,
                modality TEXT,
                action TEXT,
                text TEXT
            );
            CREATE TABLE IF NOT EXISTS rule_atom_sources (
                rule_id TEXT NOT NULL,
                legal_source_id TEXT NOT NULL,
                PRIMARY KEY (rule_id, legal_source_id),
                FOREIGN KEY (rule_id) REFERENCES rule_atoms(id),
                FOREIGN KEY (legal_source_id) REFERENCES legal_sources(id)
            );
            CREATE TABLE IF NOT EXISTS rule_actor_classes (
                rule_id TEXT NOT NULL,
                actor_class_id TEXT NOT NULL,
                PRIMARY KEY (rule_id, actor_class_id),
                FOREIGN KEY (rule_id) REFERENCES rule_atoms(id),
                FOREIGN KEY (actor_class_id) REFERENCES actor_classes(id)
            );
            """
        )
        self.connection.commit()

    # ------------------------------------------------------------------
    def upsert_legal_source(self, document: Document, *, category: Optional[str] = None) -> str:
        identifier = document.metadata.canonical_id or document.metadata.citation
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO legal_sources (id, citation, jurisdiction, category)
            VALUES (?, ?, ?, ?)
            """,
            (identifier, document.metadata.citation, document.metadata.jurisdiction, category),
        )
        self.connection.commit()
        return identifier

    # ------------------------------------------------------------------
    def upsert_actor_class(self, actor_class: str, *, description: Optional[str] = None) -> str:
        actor_class = actor_class.strip() or DEFAULT_ACTOR_CLASS_MAP["unknown"]
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO actor_classes (id, label, description)
            VALUES (?, ?, ?)
            """,
            (actor_class, actor_class, description),
        )
        if description:
            cursor.execute(
                "UPDATE actor_classes SET description = COALESCE(description, ?) WHERE id = ?",
                (description, actor_class),
            )
        self.connection.commit()
        return actor_class

    # ------------------------------------------------------------------
    def _insert_rule_atom(self, atom: RuleAtom, *, legal_source_id: str) -> str:
        rule_id = atom.stable_id or atom.toc_id or f"rule:{hash(atom.text or '')}"  # type: ignore[arg-type]
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO rule_atoms (id, modality, action, text)
            VALUES (?, ?, ?, ?)
            """,
            (rule_id, atom.modality, atom.action, atom.text),
        )
        cursor.execute(
            """
            INSERT OR REPLACE INTO rule_atom_sources (rule_id, legal_source_id)
            VALUES (?, ?)
            """,
            (rule_id, legal_source_id),
        )
        return rule_id

    # ------------------------------------------------------------------
    def _insert_rule_actor_classes(self, rule_id: str, actor_classes: Iterable[str]) -> None:
        cursor = self.connection.cursor()
        rows = [(rule_id, actor) for actor in actor_classes]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO rule_actor_classes (rule_id, actor_class_id)
            VALUES (?, ?)
            """,
            rows,
        )
        self.connection.commit()

    # ------------------------------------------------------------------
    def anchor_rule_atoms(
        self,
        document: Document,
        rule_atoms: Iterable[RuleAtom],
        *,
        category: Optional[str] = None,
        actor_class_overrides: Optional[Mapping[str, str]] = None,
    ) -> List[AnchorResult]:
        actor_class_overrides = actor_class_overrides or {}
        legal_source_id = self.upsert_legal_source(document, category=category)
        results: List[AnchorResult] = []
        for atom in rule_atoms:
            party, role, who_text = derive_party_metadata(atom.actor or atom.who or atom.who_text or "")
            override = actor_class_overrides.get(party) or actor_class_overrides.get(role or "")
            actor_class = override or DEFAULT_ACTOR_CLASS_MAP.get(party, DEFAULT_ACTOR_CLASS_MAP["unknown"])
            rule_id = self._insert_rule_atom(atom, legal_source_id=legal_source_id)
            actor_classes = [actor_class]
            if role and role not in actor_classes:
                actor_classes.append(role)
            if who_text:
                actor_classes.append(who_text)
            normalized_ids = [self.upsert_actor_class(label) for label in actor_classes]
            self._insert_rule_actor_classes(rule_id, normalized_ids)
            results.append(
                AnchorResult(
                    rule_id=rule_id,
                    legal_source_id=legal_source_id,
                    actor_classes=normalized_ids,
                )
            )
        return results


__all__ = ["AnchorResult", "NormalizedOntologyStore", "DEFAULT_ACTOR_CLASS_MAP"]
