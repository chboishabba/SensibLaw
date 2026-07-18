"""Minimal append-only SQLite store for resolution-loop artifacts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

_SCHEMA = """
CREATE TABLE IF NOT EXISTS resolution_artifact (
  artifact_ref TEXT PRIMARY KEY,
  artifact_kind TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_resolution_artifact_kind
ON resolution_artifact(artifact_kind);
"""


class ResolutionArtifactStore:
    """Append-only operational persistence for evidence-loop carriers."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(path))
        self.connection.executescript(_SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def append(
        self,
        artifact_kind: str,
        artifact_ref: str,
        payload: Mapping[str, Any],
    ) -> str:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        existing = self.connection.execute(
            "SELECT content_sha256 FROM resolution_artifact WHERE artifact_ref = ?",
            (artifact_ref,),
        ).fetchone()
        if existing:
            if existing[0] != digest:
                raise ValueError(
                    "append-only artifact reference already has different content"
                )
            return digest
        self.connection.execute(
            """
            INSERT INTO resolution_artifact(
              artifact_ref, artifact_kind, content_sha256, payload_json
            ) VALUES (?, ?, ?, ?)
            """,
            (artifact_ref, artifact_kind, digest, encoded),
        )
        self.connection.commit()
        return digest

    def get(self, artifact_ref: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT payload_json FROM resolution_artifact WHERE artifact_ref = ?",
            (artifact_ref,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def count(self, artifact_kind: str | None = None) -> int:
        if artifact_kind is None:
            row = self.connection.execute(
                "SELECT COUNT(*) FROM resolution_artifact"
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT COUNT(*) FROM resolution_artifact
                WHERE artifact_kind = ?
                """,
                (artifact_kind,),
            ).fetchone()
        return int(row[0])
