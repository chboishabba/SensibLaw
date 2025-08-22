from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import csv
import os
from typing import List, Optional


@dataclass
class CorrectionEntry:
    date: str
    description: str
    author: str


DEFAULT_LEDGER_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "corrections.csv"
)


def _resolve_path(path: Optional[Path] = None) -> Path:
    """Resolve ledger file path, optionally overridden via env var."""
    if path is not None:
        return Path(path)
    env_path = os.getenv("SENSIBLAW_CORRECTIONS_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_LEDGER_PATH


class CorrectionLedger:
    """Append-only ledger for corrections."""

    def __init__(self, path: Optional[Path] = None):
        self.path = _resolve_path(path)

    def append(self, description: str, author: str, date: Optional[str] = None) -> CorrectionEntry:
        entry = CorrectionEntry(
            date=date or datetime.utcnow().date().isoformat(),
            description=description,
            author=author,
        )
        is_new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["date", "description", "author"])
            writer.writerow([entry.date, entry.description, entry.author])
        return entry

    def list_entries(self) -> List[CorrectionEntry]:
        if not self.path.exists():
            return []
        with self.path.open() as f:
            reader = csv.DictReader(f)
            return [CorrectionEntry(**row) for row in reader]

    def to_dicts(self) -> List[dict]:
        return [asdict(e) for e in self.list_entries()]

"""Simple in-memory ledger for corrections.

This module provides a minimal API for storing correction entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LedgerEntry:
    """Represents a single correction entry."""

    name: str
    message: str


class Ledger:
    """Store :class:`LedgerEntry` items in memory."""

    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []

    def add_entry(self, entry: LedgerEntry) -> None:
        """Add a new ``entry`` to the ledger."""
        self._entries.append(entry)

    def list_entries(self) -> List[LedgerEntry]:
        """Return all stored entries."""
        return list(self._entries)


# A module-level singleton for convenience
ledger = Ledger()
