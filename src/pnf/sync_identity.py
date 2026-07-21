"""Canonical artifact identity shared with bounded ZOS reconciliation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.ontology.external_enrichment import canonical_sha256


ZOS_SYNC_IDENTITY_CONTRACT = "canonical_sync_identity_v1"


@dataclass(frozen=True)
class CanonicalSyncIdentity:
    kind: str
    object_id: str
    content_digest: str
    producer_contract: str
    producer_locator_set: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"artifact", "receipt"}:
            raise ValueError("sync identity kind must be artifact or receipt")
        if not self.object_id or not self.content_digest.startswith("sha256:"):
            raise ValueError("sync identity requires object id and sha256 digest")
        if not self.producer_contract or not self.producer_locator_set:
            raise ValueError("sync identity requires producer contract and locators")

    @property
    def identity_ref(self) -> str:
        return "sync-identity:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "identity_ref": self.identity_ref,
            "identity_contract": ZOS_SYNC_IDENTITY_CONTRACT,
            "semantic_authority": False,
        }


__all__ = ["CanonicalSyncIdentity", "ZOS_SYNC_IDENTITY_CONTRACT"]
