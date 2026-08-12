"""Late external-provider execution over deduplicated H9 cache misses.

The PostgreSQL planner has already reduced consumer-specific H9 residuals to
unique provider requests and probed local caches before requests reach this
boundary. Parsing and ordinary PNF construction never call providers here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, Sequence


class ExternalNeedKind(IntEnum):
    CANDIDATE_DISCOVERY = 1
    PROPERTY_ENRICHMENT = 2
    IDENTITY_ALIGNMENT = 3


class ExternalRequestKind(IntEnum):
    CANDIDATE_DISCOVERY = 1
    PROPERTY_ENRICHMENT = 2
    IDENTITY_ALIGNMENT = 3


class ExternalValueKind(IntEnum):
    WORLD_ENTITY = 1
    SYMBOL = 2
    NUMERIC = 3


@dataclass(frozen=True, slots=True)
class ExternalRequest:
    """Provider-facing request; PostgreSQL-local surrogate ids are absent."""

    request_id: int
    request_kind: ExternalRequestKind
    label_text: str | None
    provider_subject_numeric_id: int | None
    provider_property_numeric_id: int | None
    axis_kind: int | None
    request_revision: int


@dataclass(frozen=True, slots=True)
class DiscoveredWorldCandidate:
    provider_numeric_id: int
    candidate_ordinal: int

    def __post_init__(self) -> None:
        if self.provider_numeric_id <= 0:
            raise ValueError("provider entity id must be positive")
        if self.candidate_ordinal < 0:
            raise ValueError("candidate ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class ExternalEvidence:
    """Provider-native fact payload with explicit subject identity."""

    evidence_digest: bytes
    provider_subject_numeric_id: int
    provider_property_numeric_id: int
    value_kind: ExternalValueKind
    value_provider_numeric_id: int | None = None
    value_text: str | None = None
    value_symbol_kind: int | None = None
    value_numeric: int | None = None
    provider_revision: int | None = None
    source_ref: str = "external-provider"

    def __post_init__(self) -> None:
        if len(self.evidence_digest) != 32:
            raise ValueError("external evidence digest must be SHA-256 width")
        if self.provider_subject_numeric_id <= 0:
            raise ValueError("provider subject id must be positive")
        if self.provider_property_numeric_id <= 0:
            raise ValueError("provider property id must be positive")
        populated = sum(
            value is not None
            for value in (self.value_provider_numeric_id, self.value_text, self.value_numeric)
        )
        if populated != 1:
            raise ValueError("external evidence must contain exactly one typed value")
        if self.value_kind is ExternalValueKind.WORLD_ENTITY:
            if self.value_provider_numeric_id is None or self.value_provider_numeric_id <= 0:
                raise ValueError("world-entity evidence requires positive provider entity id")
            if self.value_symbol_kind is not None:
                raise ValueError("world-entity evidence cannot carry symbol kind")
        elif self.value_kind is ExternalValueKind.SYMBOL:
            if not self.value_text or self.value_symbol_kind is None:
                raise ValueError("symbol evidence requires text and SymbolKind id")
        elif self.value_kind is ExternalValueKind.NUMERIC:
            if self.value_numeric is None:
                raise ValueError("numeric evidence requires value_numeric")
            if self.value_symbol_kind is not None:
                raise ValueError("numeric evidence cannot carry symbol kind")


@dataclass(frozen=True, slots=True)
class ExternalRequestResult:
    request_id: int
    discovered_candidates: tuple[DiscoveredWorldCandidate, ...] = ()
    evidence: tuple[ExternalEvidence, ...] = ()
    error_ref: str | None = None

    def __post_init__(self) -> None:
        if self.error_ref is not None and (self.discovered_candidates or self.evidence):
            raise ValueError("failed external result cannot also carry successful payload")


@dataclass(frozen=True, slots=True)
class ExternalBatchResult:
    results: tuple[ExternalRequestResult, ...]
    provider_call_count: int

    def __post_init__(self) -> None:
        if self.provider_call_count < 0:
            raise ValueError("provider_call_count must be non-negative")


@dataclass(frozen=True, slots=True)
class ExternalBatchReceipt:
    leased_request_count: int
    completed_request_count: int
    failed_request_count: int
    provider_call_count: int

    @property
    def requests_per_provider_call(self) -> float | None:
        if self.provider_call_count == 0:
            return None
        return self.leased_request_count / self.provider_call_count


class ExternalProvider(Protocol):
    provider_id: int

    def fetch_batch(self, requests: Sequence[ExternalRequest]) -> ExternalBatchResult: ...


class ExternalDemandStore(Protocol):
    def claim_external_provider_batch(
        self, *, provider_id: int, worker_ref: str, limit: int, lease_seconds: int
    ) -> tuple[ExternalRequest, ...]: ...

    def record_external_discovery_candidates(
        self,
        *,
        request: ExternalRequest,
        candidates: Sequence[DiscoveredWorldCandidate],
    ) -> None: ...

    def record_external_evidence(self, *, request_id: int, evidence: ExternalEvidence) -> int: ...

    def complete_external_request(self, request_id: int) -> bool: ...

    def fail_external_request(self, request_id: int, error_ref: str) -> bool: ...

    def record_external_batch_receipt(
        self, *, provider_id: int, worker_ref: str, receipt: ExternalBatchReceipt
    ) -> int: ...


def execute_external_provider_batch(
    store: ExternalDemandStore,
    provider: ExternalProvider,
    *,
    worker_ref: str,
    limit: int = 32,
    lease_seconds: int = 300,
) -> ExternalBatchReceipt:
    requests = store.claim_external_provider_batch(
        provider_id=provider.provider_id,
        worker_ref=worker_ref,
        limit=limit,
        lease_seconds=lease_seconds,
    )
    if not requests:
        return ExternalBatchReceipt(0, 0, 0, 0)

    batch = provider.fetch_batch(requests)
    expected = {request.request_id for request in requests}
    returned = [result.request_id for result in batch.results]
    if len(returned) != len(set(returned)):
        raise ValueError("provider returned duplicate request results")
    if set(returned) != expected:
        raise ValueError("provider batch must return exactly one result for every leased request")

    request_by_id = {request.request_id: request for request in requests}
    completed = failed = 0
    for result in batch.results:
        if result.error_ref is not None:
            store.fail_external_request(result.request_id, result.error_ref)
            failed += 1
            continue

        request = request_by_id[result.request_id]
        if request.request_kind is ExternalRequestKind.CANDIDATE_DISCOVERY:
            if not request.label_text:
                raise ValueError("candidate-discovery request is missing boundary label text")
            store.record_external_discovery_candidates(
                request=request,
                candidates=result.discovered_candidates,
            )
        else:
            for evidence in result.evidence:
                if request.provider_subject_numeric_id != evidence.provider_subject_numeric_id:
                    raise ValueError("provider returned evidence for an unrequested subject")
                if (
                    request.provider_property_numeric_id is not None
                    and evidence.provider_property_numeric_id
                    != request.provider_property_numeric_id
                ):
                    raise ValueError("provider returned evidence for an unrequested property")
                store.record_external_evidence(request_id=result.request_id, evidence=evidence)
        store.complete_external_request(result.request_id)
        completed += 1

    receipt = ExternalBatchReceipt(
        leased_request_count=len(requests),
        completed_request_count=completed,
        failed_request_count=failed,
        provider_call_count=batch.provider_call_count,
    )
    store.record_external_batch_receipt(
        provider_id=provider.provider_id,
        worker_ref=worker_ref,
        receipt=receipt,
    )
    return receipt
