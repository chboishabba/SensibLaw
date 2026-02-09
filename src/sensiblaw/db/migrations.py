from __future__ import annotations

import hashlib
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

    def _ensure_migrations_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def _applied_migrations(self) -> dict[str, str]:
        rows = self.connection.execute(
            "SELECT filename, checksum FROM schema_migrations ORDER BY filename"
        ).fetchall()
        applied: dict[str, str] = {}
        for filename, checksum in rows:
            if filename:
                applied[str(filename)] = str(checksum or "")
        return applied

    def _db_table_names(self) -> set[str]:
        rows = self.connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        return {str(row[0]) for row in rows if row and row[0]}

    def _db_is_empty(self) -> bool:
        tables = self._db_table_names() - {"schema_migrations"}
        return not tables

    def _db_looks_like_ontology_db(self) -> bool:
        # Canonical tables created by our ontology migration track.
        tables = self._db_table_names()
        return bool(
            {
                "legal_systems",
                "norm_source_categories",
                "legal_sources",
                "actors",
                "concepts",
            }
            & tables
        )

    def _bootstrap_existing_untracked_db(self) -> None:
        """Mark all current migration files as applied for an existing ontology DB.

        This is only used when a DB already has ontology tables but predates the
        `schema_migrations` tracking table. We assume it is already migrated and
        avoid re-executing non-repeatable migrations.
        """

        for path in self.migration_paths:
            filename = path.name
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            self.connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (filename, checksum) VALUES (?, ?)",
                (filename, checksum),
            )
        self.connection.commit()

    def _apply_migration(self, path: Path) -> None:
        sql = path.read_text()
        self.connection.executescript(sql)

    def apply_all(self) -> None:
        """Execute all configured migrations in order.

        Migrations are tracked in `schema_migrations` (filename + checksum) so
        this method is safe to call repeatedly.
        """

        self._ensure_migrations_table()
        applied = self._applied_migrations()

        # If this DB predates migration tracking, avoid re-running non-repeatable
        # migrations by bootstrapping the tracker when the schema already exists.
        if not applied and not self._db_is_empty():
            if not self._db_looks_like_ontology_db():
                raise ValueError(
                    "SQLite DB does not look like a SensibLaw ontology DB (managed by "
                    "database/migrations). Refusing to run ontology migrations against "
                    "a different schema family."
                )
            self._bootstrap_existing_untracked_db()
            return

        for path in self.migration_paths:
            filename = path.name
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if filename in applied:
                if applied[filename] != checksum:
                    raise ValueError(
                        f"Applied migration checksum mismatch for {filename}. "
                        "Do not edit existing migration files; create a new migration."
                    )
                continue

            self._apply_migration(path)
            self.connection.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES (?, ?)",
                (filename, checksum),
            )
            self.connection.commit()
