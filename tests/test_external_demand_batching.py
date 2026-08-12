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
        ExternalRequest(1, ExternalRequestKind.CANDIDATE_DISCOVERY, "Springfield", None, None, None, 1),
        ExternalRequest(2, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 1001, 17, 1, 1),
        ExternalRequest(3, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 1002, 17, 1, 1),
    )
    evidence = ExternalEvidence(
        evidence_digest=b"e" * 32,
        provider_subject_numeric_id=1001,
        provider_property_numeric_id=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_provider_numeric_id=408,
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


def test_provider_request_contains_no_database_local_surrogate_ids() -> None:
    request = ExternalRequest(
        1,
        ExternalRequestKind.PROPERTY_ENRICHMENT,
        None,
        408,
        17,
        1,
        1,
    )
    assert request.provider_subject_numeric_id == 408
    assert not hasattr(request, "world_entity_id")
    assert not hasattr(request, "label_symbol_id")


def test_provider_must_return_exactly_one_result_per_lease() -> None:
    request = ExternalRequest(
        1,
        ExternalRequestKind.CANDIDATE_DISCOVERY,
        "Springfield",
        None,
        None,
        None,
        1,
    )
    store = FakeStore((request,))
    provider = FakeProvider(ExternalBatchResult((ExternalRequestResult(99),), 1))
    with pytest.raises(ValueError, match="exactly one result"):
        execute_external_provider_batch(store, provider, worker_ref="worker")


def test_wrong_provider_subject_is_rejected_before_persistence() -> None:
    request = ExternalRequest(
        1,
        ExternalRequestKind.PROPERTY_ENRICHMENT,
        None,
        1001,
        17,
        1,
        1,
    )
    evidence = ExternalEvidence(
        evidence_digest=b"q" * 32,
        provider_subject_numeric_id=9999,
        provider_property_numeric_id=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_provider_numeric_id=408,
    )
    store = FakeStore((request,))
    provider = FakeProvider(
        ExternalBatchResult((ExternalRequestResult(1, evidence=(evidence,)),), 1)
    )
    with pytest.raises(ValueError, match="unrequested subject"):
        execute_external_provider_batch(store, provider, worker_ref="worker")
    assert store.evidence == []


def test_external_evidence_requires_exactly_one_provider_native_value() -> None:
    with pytest.raises(ValueError, match="exactly one typed value"):
        ExternalEvidence(
            evidence_digest=b"x" * 32,
            provider_subject_numeric_id=1,
            provider_property_numeric_id=17,
            value_kind=ExternalValueKind.SYMBOL,
            value_text="Australia",
            value_symbol_kind=2,
            value_numeric=3,
        )


def test_symbol_evidence_crosses_explicit_text_boundary() -> None:
    evidence = ExternalEvidence(
        evidence_digest=b"s" * 32,
        provider_subject_numeric_id=1,
        provider_property_numeric_id=17,
        value_kind=ExternalValueKind.SYMBOL,
        value_text="Australia",
        value_symbol_kind=2,
    )
    assert evidence.value_text == "Australia"
    assert not hasattr(evidence, "value_symbol_id")
