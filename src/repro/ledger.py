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
