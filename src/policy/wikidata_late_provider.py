"""Wikidata adapter for late H9 cache misses.

Network mechanics are injected through ``WikidataTransport`` so this layer can
optimize semantic request fan-in independently of HTTP/SPARQL details.  The
adapter deduplicates labels and (Q,P) facts before transport and reports the
transport's actual network-call count.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Protocol, Sequence

from src.policy.external_demand import (
    DiscoveredWorldCandidate,
    ExternalBatchResult,
    ExternalEvidence,
    ExternalRequest,
    ExternalRequestKind,
    ExternalRequestResult,
    ExternalValueKind,
)


WIKIDATA_PROVIDER_ID = 1


@dataclass(frozen=True, slots=True)
class WikidataSearchCandidate:
    qid: int
    rank: int


@dataclass(frozen=True, slots=True)
class WikidataSearchBatch:
    candidates_by_label: Mapping[str, tuple[WikidataSearchCandidate, ...]]
    provider_call_count: int


@dataclass(frozen=True, slots=True)
class WikidataPropertyFact:
    subject_qid: int
    property_pid: int
    value_kind: ExternalValueKind
    value_qid: int | None = None
    value_text: str | None = None
    value_symbol_kind: int | None = None
    value_numeric: int | None = None
    entity_revision: int | None = None


@dataclass(frozen=True, slots=True)
class WikidataPropertyBatch:
    facts_by_key: Mapping[tuple[int, int], tuple[WikidataPropertyFact, ...]]
    provider_call_count: int


class WikidataTransport(Protocol):
    """Network-facing transport with explicit batching and call receipts."""

    def search_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> WikidataSearchBatch: ...

    def fetch_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> WikidataPropertyBatch: ...


class WikidataLateProvider:
    provider_id = WIKIDATA_PROVIDER_ID

    def __init__(
        self,
        transport: WikidataTransport,
        *,
        candidate_limit: int = 8,
    ) -> None:
        if candidate_limit < 1 or candidate_limit > 64:
            raise ValueError("candidate_limit must be in 1..64")
        self.transport = transport
        self.candidate_limit = candidate_limit

    def fetch_batch(self, requests: Sequence[ExternalRequest]) -> ExternalBatchResult:
        request_tuple = tuple(requests)
        discovery = tuple(
            request
            for request in request_tuple
            if request.request_kind is ExternalRequestKind.CANDIDATE_DISCOVERY
        )
        enrichment = tuple(
            request
            for request in request_tuple
            if request.request_kind is ExternalRequestKind.PROPERTY_ENRICHMENT
        )
        identity = tuple(
            request
            for request in request_tuple
            if request.request_kind is ExternalRequestKind.IDENTITY_ALIGNMENT
        )

        results: dict[int, ExternalRequestResult] = {}
        provider_calls = 0

        if discovery:
            labels = tuple(sorted({request.label_text for request in discovery if request.label_text}))
            search_batch = self.transport.search_entities(
                labels,
                limit_per_label=self.candidate_limit,
            )
            provider_calls += search_batch.provider_call_count
            for request in discovery:
                if not request.label_text:
                    results[request.request_id] = ExternalRequestResult(
                        request.request_id,
                        error_ref="wikidata:missing-search-label",
                    )
                    continue
                candidates = search_batch.candidates_by_label.get(request.label_text, ())
                results[request.request_id] = ExternalRequestResult(
                    request.request_id,
                    discovered_candidates=tuple(
                        DiscoveredWorldCandidate(
                            provider_numeric_id=int(candidate.qid),
                            candidate_ordinal=int(candidate.rank),
                        )
                        for candidate in candidates[: self.candidate_limit]
                    ),
                )

        if enrichment:
            keys = tuple(
                sorted(
                    {
                        (int(request.provider_subject_numeric_id), int(request.provider_property_numeric_id))
                        for request in enrichment
                        if request.provider_subject_numeric_id is not None
                        and request.provider_property_numeric_id is not None
                    }
                )
            )
            property_batch = self.transport.fetch_properties(keys)
            provider_calls += property_batch.provider_call_count
            for request in enrichment:
                if (
                    request.provider_subject_numeric_id is None
                    or request.provider_property_numeric_id is None
                ):
                    results[request.request_id] = ExternalRequestResult(
                        request.request_id,
                        error_ref="wikidata:missing-Q-or-P-coordinate",
                    )
                    continue
                key = (
                    request.provider_subject_numeric_id,
                    request.provider_property_numeric_id,
                )
                facts = property_batch.facts_by_key.get(key, ())
                results[request.request_id] = ExternalRequestResult(
                    request.request_id,
                    evidence=tuple(self._external_evidence(fact) for fact in facts),
                )

        # A normal entity/property lookup is not an identity proof.  This lane
        # stays explicitly blocked until a proof-producing alignment adapter is
        # supplied by the caller/runtime.
        for request in identity:
            results[request.request_id] = ExternalRequestResult(
                request.request_id,
                error_ref="wikidata:identity-proof-adapter-required",
            )

        # Identity-only batches perform no network call by construction.  The
        # generic executor requires a non-empty batch to account for a provider
        # call, so treat these as one logical provider-boundary evaluation without
        # claiming network I/O only when no discovery/property transport ran.
        if request_tuple and provider_calls == 0 and not identity:
            raise ValueError("Wikidata transport returned results without accounting for calls")
        if request_tuple and provider_calls == 0 and identity:
            # The generic receipt tracks provider boundary invocations; this value
            # is deliberately not used as the network-call metric for identity-only
            # blocked requests. Callers should not lease identity requests until a
            # proof adapter exists.
            provider_calls = 1

        ordered = tuple(results[request.request_id] for request in request_tuple)
        return ExternalBatchResult(ordered, provider_calls)

    @staticmethod
    def _external_evidence(fact: WikidataPropertyFact) -> ExternalEvidence:
        canonical = [
            b"wikidata-fact-v1",
            str(fact.subject_qid).encode("ascii"),
            str(fact.property_pid).encode("ascii"),
            str(int(fact.value_kind)).encode("ascii"),
            str(fact.value_qid if fact.value_qid is not None else "").encode("utf-8"),
            str(fact.value_text if fact.value_text is not None else "").encode("utf-8"),
            str(fact.value_numeric if fact.value_numeric is not None else "").encode("utf-8"),
            str(fact.entity_revision if fact.entity_revision is not None else "").encode("ascii"),
        ]
        digest = sha256(b"\x00".join(canonical)).digest()
        if fact.value_kind is ExternalValueKind.WORLD_ENTITY:
            return ExternalEvidence(
                evidence_digest=digest,
                provider_property_numeric_id=fact.property_pid,
                value_kind=fact.value_kind,
                value_provider_numeric_id=fact.value_qid,
                provider_revision=fact.entity_revision,
                source_ref="wikidata:property-batch",
            )
        if fact.value_kind is ExternalValueKind.SYMBOL:
            return ExternalEvidence(
                evidence_digest=digest,
                provider_property_numeric_id=fact.property_pid,
                value_kind=fact.value_kind,
                value_text=fact.value_text,
                value_symbol_kind=fact.value_symbol_kind,
                provider_revision=fact.entity_revision,
                source_ref="wikidata:property-batch",
            )
        return ExternalEvidence(
            evidence_digest=digest,
            provider_property_numeric_id=fact.property_pid,
            value_kind=fact.value_kind,
            value_numeric=fact.value_numeric,
            provider_revision=fact.entity_revision,
            source_ref="wikidata:property-batch",
        )
