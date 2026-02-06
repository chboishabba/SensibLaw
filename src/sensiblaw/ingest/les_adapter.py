from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from sensiblaw.db import ContextFieldDAO, MigrationRunner


def import_les_snapshot(connection: sqlite3.Connection, snapshot: Mapping[str, Any]) -> None:
    """Store a LES environment snapshot as a context_field overlay."""

    snapshot_id = snapshot["snapshot_id"]
    context_id = f"les:{snapshot_id}"
    MigrationRunner(connection).apply_all()
    dao = ContextFieldDAO(connection)
    dao.upsert_context_field(
        context_id=context_id,
        context_type="les_environment",
        source=snapshot.get("source"),
        retrieved_at=snapshot.get("captured_at"),
        location=snapshot.get("location"),
        time_start=snapshot.get("captured_at"),
        time_end=snapshot.get("captured_at"),
        payload=snapshot.get("environment_state"),
        provenance={"models": snapshot.get("models")},
        symbolic=False,
    )


__all__ = ["import_les_snapshot"]
