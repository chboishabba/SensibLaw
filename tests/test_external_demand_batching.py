from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.policy.external_demand import (
    DiscoveredWorldCandidate,
    ExternalBatchResult,
    ExternalEvidence,
    ExternalRequest,
    ExternalRequestKind,
    ExternalRequestResult,
    ExternalValueKind,
    execute_external_provider_batch,
)


@dataclass
class FakeStore:
    requests: tuple[ExternalRequest, ...]
    discoveries: list[int] = field(default_factory=list)
    evidence: list[int] = field(default_factory=list)
    completed: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    receipts: list[object] = field(default_factory=list)

    def claim_external_provider_batch(self, **_: object) -> tuple[ExternalRequest, ...]:
        return self.requests

    def record_external_discovery_candidates(self, *, request, candidates) -> None:
        self.discoveries.append(request.request_id)
        assert candidates

    def record_external_evidence(self, *, request_id, evidence) -> int:
        self.evidence.append(request_id)
        assert evidence.evidence_digest
        return len(self.evidence)

    def complete_external_request(self, request_id: int) -> bool:
        self.completed.append(request_id)
        return True

    def fail_external_request(self, request_id: int, error_ref: str) -> bool:
        assert error_ref
        self.failed.append(request_id)
        return True

    def record_external_batch_receipt(self, **kwargs: object) -> int:
        self.receipts.append(kwargs)
        return len(self.receipts)


class FakeProvider:
    provider_id = 1

    def __init__(self, result: ExternalBatchResult) -> None:
        self.result = result
        self.calls = 0

    def fetch_batch(self, requests):
        self.calls += 1
        assert requests
        return self.result


def test_zero_provider_calls_when_cache_probe_leases_no_requests() -> None:
    store = FakeStore(())
    provider = FakeProvider(ExternalBatchResult((), 0))
    receipt = execute_external_provider_batch(store, provider, worker_ref="worker")
    assert provider.calls == 0
    assert receipt.provider_call_count == 0
    assert store.receipts == []


def test_one_provider_call_can_serve_multiple_deduplicated_requests() -> None:
    requests = (
        ExternalRequest(1, ExternalRequestKind.CANDIDATE_DISCOVERY, 100, None, None, None, 1),
        ExternalRequest(2, ExternalRequestKind.PROPERTY_ENRICHMENT, 100, 200, 17, 1, 1),
        ExternalRequest(3, ExternalRequestKind.PROPERTY_ENRICHMENT, 100, 201, 17, 1, 1),
    )
    evidence = ExternalEvidence(
        evidence_digest=b"e" * 32,
        subject_world_entity_id=200,
        provider_property_numeric_id=17,
        axis_kind=1,
        value_kind=ExternalValueKind.SYMBOL,
        value_symbol_id=300,
    )
    provider = FakeProvider(
        ExternalBatchResult(
            (
                ExternalRequestResult(
                    1,
                    discovered_candidates=(DiscoveredWorldCandidate(42, 0),),
                ),
                ExternalRequestResult(2, evidence=(evidence,)),
                ExternalRequestResult(3, error_ref="provider:not-found"),
            ),
            provider_call_count=1,
        )
    )
    store = FakeStore(requests)
    receipt = execute_external_provider_batch(store, provider, worker_ref="worker")
    assert provider.calls == 1
    assert receipt.leased_request_count == 3
    assert receipt.completed_request_count == 2
    assert receipt.failed_request_count == 1
    assert receipt.requests_per_provider_call == 3.0
    assert store.discoveries == [1]
    assert store.evidence == [2]
    assert store.completed == [1, 2]
    assert store.failed == [3]
    assert len(store.receipts) == 1


def test_provider_must_return_exactly_one_result_per_lease() -> None:
    request = ExternalRequest(
        1,
        ExternalRequestKind.CANDIDATE_DISCOVERY,
        100,
        None,
        None,
        None,
        1,
    )
    store = FakeStore((request,))
    provider = FakeProvider(ExternalBatchResult((ExternalRequestResult(99),), 1))
    with pytest.raises(ValueError, match="exactly one result"):
        execute_external_provider_batch(store, provider, worker_ref="worker")


def test_external_evidence_requires_exactly_one_typed_value() -> None:
    with pytest.raises(ValueError, match="exactly one typed value"):
        ExternalEvidence(
            evidence_digest=b"x" * 32,
            subject_world_entity_id=1,
            provider_property_numeric_id=17,
            axis_kind=1,
            value_kind=ExternalValueKind.SYMBOL,
            value_symbol_id=2,
            value_numeric=3,
        )
