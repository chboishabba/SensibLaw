from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.runtime.distributed_semantic_worker import (
    DistributedSemanticWorker,
    SemanticJobResult,
)
from src.storage.postgres.distributed_semantic_execution_store import (
    SemanticDeltaAdmission,
    SemanticJobLease,
)


class FakeCursor:
    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def execute(self, query: str, parameters: Any = None) -> None:
        return None


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor()


@dataclass
class FakeStore:
    lease: SemanticJobLease
    admitted_delta_ref: str | None = None
    recovered: int = 0
    awakened: int = 0

    def recover_expired_leases(self, cursor: Any, *, document_ref: str) -> int:
        self.recovered += 1
        return 0

    def awaken_ready_jobs(self, cursor: Any, *, document_ref: str) -> int:
        self.awakened += 1
        return 0

    def lease_jobs(self, cursor: Any, **kwargs: Any) -> tuple[SemanticJobLease, ...]:
        return (self.lease,)

    def renew_lease(self, cursor: Any, **kwargs: Any) -> None:
        return None

    def admit_delta(self, cursor: Any, **kwargs: Any) -> SemanticDeltaAdmission:
        self.admitted_delta_ref = str(kwargs["delta_ref"])
        lease = kwargs["lease"]
        return SemanticDeltaAdmission(
            delta_ref=self.admitted_delta_ref,
            job_ref=lease.job_ref,
            owner_ref=lease.owner_ref,
            lease_epoch=lease.lease_epoch,
            prior_owner_revision=lease.expected_owner_revision,
            resulting_owner_revision=lease.expected_owner_revision + 1,
            state="accepted",
        )


def _lease() -> SemanticJobLease:
    return SemanticJobLease(
        job_ref="job:1",
        document_ref="document:1",
        owner_ref="owner:1",
        operation_contract_ref="operation:v1",
        input_manifest_ref="manifest:input",
        expected_owner_revision=3,
        canonical_ordinal=0,
        priority=1,
        lease_owner="worker:alpha",
        lease_epoch=4,
        payload={"bounded": True},
    )


def test_worker_computes_immutable_delta_and_admits_through_store() -> None:
    store = FakeStore(_lease())
    observed: list[SemanticJobLease] = []

    def execute(lease: SemanticJobLease) -> SemanticJobResult:
        observed.append(lease)
        return SemanticJobResult(
            output_manifest_ref="manifest:output",
            output_manifest_sha256="00" * 32,
            payload={"delta": "immutable"},
            resource_receipt={"rss_bytes": 123},
        )

    worker = DistributedSemanticWorker(
        connection_factory=FakeConnection,
        executor=execute,
        worker_ref="worker:alpha",
        store=store,  # type: ignore[arg-type]
        lease_seconds=300,
        heartbeat_seconds=100,
    )

    receipt = worker.run_once(document_ref="document:1")

    assert observed == [store.lease]
    assert receipt.leased_count == 1
    assert receipt.accepted_count == 1
    assert receipt.failed_count == 0
    assert store.recovered == 1
    assert store.awakened == 1
    assert store.admitted_delta_ref is not None
    assert store.admitted_delta_ref.startswith("semantic-delta:")
