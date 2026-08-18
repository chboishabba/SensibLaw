"""Operational late-H9 Wikidata executor with Zelph/HF snapshot-first routing."""

from __future__ import annotations

from dataclasses import dataclass

from src.policy.external_demand import (
    ExternalBatchReceipt,
    execute_external_provider_batch,
)
from src.policy.wikidata_late_provider import WikidataLateProvider, WikidataTransport
from src.policy.wikidata_tiered_transport import (
    TieredWikidataTransport,
    WikidataTierPolicy,
    ZelphHFWikidataTransport,
    ZelphSnapshotQueryBackend,
)
from src.storage.postgres.external_demand_runtime_store import (
    ExternalDemandRuntimeStore,
)


@dataclass(frozen=True, slots=True)
class LateWikidataExecutionConfig:
    worker_ref: str
    batch_limit: int = 64
    lease_seconds: int = 300
    candidate_limit: int = 8

    def __post_init__(self) -> None:
        if not self.worker_ref.strip():
            raise ValueError("worker_ref must be non-empty")
        if self.batch_limit <= 0:
            raise ValueError("batch_limit must be positive")
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")


class LateWikidataExecutor:
    """Drain already-planned H9 cache misses through one Wikidata namespace."""

    def __init__(
        self,
        database_url: str,
        transport: WikidataTransport,
        *,
        candidate_limit: int = 8,
    ) -> None:
        self.store = ExternalDemandRuntimeStore(database_url)
        self.provider = WikidataLateProvider(transport, candidate_limit=candidate_limit)

    @classmethod
    def zelph_snapshot_first(
        cls,
        database_url: str,
        *,
        snapshot_backend: ZelphSnapshotQueryBackend,
        snapshot_ref: str,
        snapshot_epoch: int | None,
        snapshot_revision: int | None = None,
        live_transport: WikidataTransport | None = None,
        tier_policy: WikidataTierPolicy | None = None,
        candidate_limit: int = 8,
    ) -> "LateWikidataExecutor":
        """Build the normal DB-cache -> Zelph/HF -> live H9 execution path.

        ``snapshot_epoch`` should come from the actual HF artifact/manifest
        metadata, not from a code constant.  A missing epoch is usable for
        freshness-insensitive consumers but cannot satisfy a positive freshness
        floor.
        """
        snapshot = ZelphHFWikidataTransport(
            snapshot_backend,
            snapshot_ref=snapshot_ref,
            snapshot_epoch=snapshot_epoch,
            snapshot_revision=snapshot_revision,
        )
        transport = TieredWikidataTransport(
            snapshot, live_transport, policy=tier_policy
        )
        return cls(database_url, transport, candidate_limit=candidate_limit)

    def drain_once(self, config: LateWikidataExecutionConfig) -> ExternalBatchReceipt:
        return execute_external_provider_batch(
            self.store,
            self.provider,
            worker_ref=config.worker_ref,
            limit=config.batch_limit,
            lease_seconds=config.lease_seconds,
        )


__all__ = ["LateWikidataExecutionConfig", "LateWikidataExecutor"]
