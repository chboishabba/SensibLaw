"""Generic immutable snapshot envelope with backend-specific typed payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Mapping, TypeVar

from src.policy.carriers.canonical import (
    canonical_mapping,
    canonical_refs,
    canonical_sha256,
    require_text,
)

T = TypeVar("T")


@dataclass(frozen=True)
class ExternalSnapshotEnvelope(Generic[T]):
    snapshot_ref: str
    backend_ref: str
    external_ref: str
    version_ref: str
    formal_role: str
    payload: T
    fetched_at: str | None = None
    provenance_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        provenance = canonical_refs(self.provenance_refs)
        if not provenance:
            raise ValueError("external snapshots require provenance")
        row: dict[str, Any] = {
            "schema_version": "sl.external_snapshot_envelope.v0_1",
            "snapshot_ref": require_text(self.snapshot_ref, "snapshot_ref"),
            "backend_ref": require_text(self.backend_ref, "backend_ref"),
            "external_ref": require_text(self.external_ref, "external_ref"),
            "version_ref": require_text(self.version_ref, "version_ref"),
            "formal_role": require_text(self.formal_role, "formal_role"),
            "payload": self.payload,
            "provenance_refs": list(provenance),
            "metadata": canonical_mapping(self.metadata),
            "authority": "evidence_only",
        }
        if self.fetched_at:
            row["fetched_at"] = require_text(self.fetched_at, "fetched_at")
        row["payload_sha256"] = canonical_sha256(self.payload)
        row["snapshot_sha256"] = canonical_sha256(row)
        return row
