from __future__ import annotations

from pathlib import Path
from sqlite3 import Connection
from typing import Iterable


MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"


class MigrationRunner:
    """Apply SQL migrations bundled with the repository."""

    def __init__(self, connection: Connection, migration_paths: Iterable[Path] | None = None):
        self.connection = connection
        self.migration_paths = list(migration_paths) if migration_paths else self._default_paths()

    def _default_paths(self) -> list[Path]:
        if not MIGRATIONS_DIR.exists():
            return []
        return sorted(MIGRATIONS_DIR.glob("*.sql"))

    def apply_all(self) -> None:
        """Execute all configured migrations in order."""

        for path in self.migration_paths:
            sql = path.read_text()
            self.connection.executescript(sql)
        self.connection.commit()
