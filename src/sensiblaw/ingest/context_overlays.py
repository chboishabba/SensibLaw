from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping

from sensiblaw.db import ContextFieldDAO

Overlay = Mapping[str, Any]


def ingest_context_fields(connection: sqlite3.Connection, overlays: Iterable[Overlay]) -> None:
    """Upsert context_field overlays into the DB (non-authoritative).

    Each overlay dict should provide:
    - context_id (str)
    - context_type (str)
    Optional: source, retrieved_at, location, time_start, time_end, payload, provenance, symbolic.
    """

    dao = ContextFieldDAO(connection)
    for overlay in overlays:
        dao.upsert_context_field(
            context_id=str(overlay["context_id"]),
            context_type=str(overlay["context_type"]),
            source=overlay.get("source"),
            retrieved_at=overlay.get("retrieved_at"),
            location=overlay.get("location"),
            time_start=overlay.get("time_start"),
            time_end=overlay.get("time_end"),
            payload=overlay.get("payload"),
            provenance=overlay.get("provenance"),
            symbolic=bool(overlay.get("symbolic", False)),
        )
