"""Immutable compiler-stage cache contracts.

The cache stores content-addressed stage outputs. Reuse is an execution optimisation only:
it cannot promote semantic state, change canonical identities, or hide unresolved residuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from src.policy.carriers.canonical import canonical_sha256


STAGE_CACHE_ENTRY_SCHEMA_VERSION = "sl.pnf.stage_cache_entry.v0_1"
STAGE_REUSE_RECEIPT_SCHEMA_VERSION = "sl.pnf.stage_reuse_receipt.v0_1"


@dataclass(frozen=True)
class StageCacheEntry:
    stage_build_key: str
    document_ref: str
    stage: str
    contract_ref: str
    input_refs: tuple[str, ...]
    declaration_refs: tuple[str, ...]
    output_ref: str
    output_payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STAGE_CACHE_ENTRY_SCHEMA_VERSION,
            "stage_build_key": self.stage_build_key,
            "document_ref": self.document_ref,
            "stage": self.stage,
            "contract_ref": self.contract_ref,
            "input_refs": list(sorted(set(self.input_refs))),
            "declaration_refs": list(sorted(set(self.declaration_refs))),
            "output_ref": self.output_ref,
            "output_payload": dict(self.output_payload),
            "authority": "execution_cache_only",
        }


@dataclass(frozen=True)
class StageReuseReceipt:
    document_ref: str
    stage: str
    stage_build_key: str
    reused: bool
    source_output_ref: str

    @property
    def receipt_ref(self) -> str:
        return "stage-reuse:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STAGE_REUSE_RECEIPT_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "stage": self.stage,
            "stage_build_key": self.stage_build_key,
            "reused": self.reused,
            "source_output_ref": self.source_output_ref,
            "semantic_state_promoted": False,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


class StageCache(Protocol):
    def load(self, stage_build_key: str) -> StageCacheEntry | None: ...

    def persist(self, entry: StageCacheEntry) -> None: ...


class MemoryStageCache:
    """Deterministic test/local cache with content-addressed replacement rules."""

    def __init__(self) -> None:
        self._entries: dict[str, StageCacheEntry] = {}

    def load(self, stage_build_key: str) -> StageCacheEntry | None:
        return self._entries.get(stage_build_key)

    def persist(self, entry: StageCacheEntry) -> None:
        prior = self._entries.get(entry.stage_build_key)
        if prior is not None and prior.to_dict() != entry.to_dict():
            raise ValueError("stage build key collision with different payload")
        self._entries[entry.stage_build_key] = entry


__all__ = [
    "MemoryStageCache",
    "StageCache",
    "StageCacheEntry",
    "StageReuseReceipt",
]
