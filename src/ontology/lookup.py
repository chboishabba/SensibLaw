from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from src.glossary.service import GlossEntry, lookup as glossary_lookup


LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ontology_lookup_log (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT,
    label TEXT,
    description TEXT,
    confidence REAL,
    looked_up_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INSERT_SQL = """
INSERT INTO ontology_lookup_log (
    term, provider, external_id, label, description, confidence
) VALUES (?, ?, ?, ?, ?, ?);
"""


@dataclass(frozen=True)
class LookupRecord:
    """Result of an ontology lookup suitable for persistence."""

    term: str
    provider: str
    external_id: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = None

    def asdict(self) -> dict:
        return asdict(self)


def _ensure_log_table(connection: sqlite3.Connection) -> None:
    connection.executescript(LOG_TABLE_SQL)


def _coerce_confidence(entry: Optional[GlossEntry]) -> Optional[float]:
    if not entry or not entry.metadata:
        return None
    confidence = entry.metadata.get("confidence")
    if confidence is None:
        return None
    try:
        return float(confidence)
    except (TypeError, ValueError):
        return None


def _extract_external_id(entry: Optional[GlossEntry]) -> Optional[str]:
    if not entry or not entry.metadata:
        return None
    external_id = entry.metadata.get("id")
    return str(external_id) if external_id is not None else None


def persist_lookup_logs(db_path: Path, lookups: Iterable[LookupRecord]) -> None:
    """Persist lookup records to the ontology lookup log table."""

    lookups = list(lookups)
    if not lookups:
        return
    connection = sqlite3.connect(db_path)
    try:
        _ensure_log_table(connection)
        rows = [
            (
                record.term,
                record.provider,
                record.external_id,
                record.label,
                record.description,
                record.confidence,
            )
            for record in lookups
        ]
        connection.executemany(INSERT_SQL, rows)
        connection.commit()
    finally:
        connection.close()


def batch_lookup(
    terms: Iterable[str], *, provider: str = "glossary", db_path: Optional[Path] = None
) -> List[LookupRecord]:
    """Resolve a batch of ontology terms and optionally log the lookups."""

    results: List[LookupRecord] = []
    for term in terms:
        if term is None:
            continue
        cleaned = term.strip()
        if not cleaned:
            continue
        entry = glossary_lookup(cleaned)
        results.append(
            LookupRecord(
                term=cleaned,
                provider=provider,
                external_id=_extract_external_id(entry),
                label=entry.phrase if entry else None,
                description=entry.text if entry else None,
                confidence=_coerce_confidence(entry),
            )
        )
    if db_path:
        persist_lookup_logs(db_path, results)
    return results


__all__ = ["LookupRecord", "batch_lookup", "persist_lookup_logs"]
