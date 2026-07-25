"""Bounded import/replay bridge for historical SQLite fact-review fixtures.

This module is the only supported SQLite boundary.  It reads a historical fixture,
projects declared rows into PostgreSQL through caller-supplied import handlers, emits
a receipt, closes SQLite, and never participates in normal runtime queries.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable, Mapping

LEGACY_SQLITE_IMPORT_CONTRACT = "sl.fact_review.legacy_sqlite_import.v0_1"


@dataclass(frozen=True)
class LegacySQLiteImportReceipt:
    source_path: str
    source_sha256: str
    importer_contract: str
    imported_row_counts: Mapping[str, int]
    rejected_row_counts: Mapping[str, int]
    resulting_revision_refs: tuple[str, ...]
    discrepancy_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "importer_contract": self.importer_contract,
            "imported_row_counts": dict(sorted(self.imported_row_counts.items())),
            "rejected_row_counts": dict(sorted(self.rejected_row_counts.items())),
            "resulting_revision_refs": list(sorted(set(self.resulting_revision_refs))),
            "discrepancy_refs": list(sorted(set(self.discrepancy_refs))),
            "sqlite_runtime_authority": False,
            "postgresql_runtime_required_after_import": True,
            "bounded_legacy_fixture_import": True,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_legacy_sqlite_fixture(
    *,
    sqlite_path: str | Path,
    postgres_connection: Any,
    table_importers: Mapping[
        str,
        Callable[[Any, Iterable[Mapping[str, Any]]], tuple[int, int, tuple[str, ...], tuple[str, ...]]],
    ],
) -> LegacySQLiteImportReceipt:
    path = Path(sqlite_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    imported: dict[str, int] = {}
    rejected: dict[str, int] = {}
    revisions: list[str] = []
    discrepancies: list[str] = []

    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        for table_name, importer in sorted(table_importers.items()):
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            if not exists:
                imported[table_name] = 0
                rejected[table_name] = 0
                discrepancies.append(f"missing-table:{table_name}")
                continue
            rows = tuple(dict(row) for row in source.execute(f'SELECT * FROM "{table_name}"'))
            count, rejected_count, revision_refs, discrepancy_refs = importer(
                postgres_connection, rows
            )
            imported[table_name] = int(count)
            rejected[table_name] = int(rejected_count)
            revisions.extend(str(value) for value in revision_refs)
            discrepancies.extend(str(value) for value in discrepancy_refs)
        postgres_connection.commit()
    except Exception:
        postgres_connection.rollback()
        raise
    finally:
        source.close()

    return LegacySQLiteImportReceipt(
        source_path=str(path),
        source_sha256=_sha256_file(path),
        importer_contract=LEGACY_SQLITE_IMPORT_CONTRACT,
        imported_row_counts=imported,
        rejected_row_counts=rejected,
        resulting_revision_refs=tuple(revisions),
        discrepancy_refs=tuple(discrepancies),
    )


__all__ = [
    "LEGACY_SQLITE_IMPORT_CONTRACT",
    "LegacySQLiteImportReceipt",
    "import_legacy_sqlite_fixture",
]
