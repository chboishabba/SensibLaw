from __future__ import annotations

from dataclasses import dataclass, field

from src.policy.external_demand import (
    ExternalRequest,
    ExternalRequestKind,
    ExternalValueKind,
)
from src.policy.wikidata_late_provider import (
    WikidataLateProvider,
    WikidataPropertyBatch,
    WikidataPropertyFact,
    WikidataSearchBatch,
    WikidataSearchCandidate,
)


@dataclass
class FakeTransport:
    search_calls: list[tuple[tuple[str, ...], int | None]] = field(default_factory=list)
    property_calls: list[tuple[tuple[tuple[int, int], ...], int | None]] = field(
        default_factory=list
    )

    def search_entities(self, labels, *, limit_per_label, minimum_source_epoch=None):
        self.search_calls.append((tuple(labels), minimum_source_epoch))
        epoch = minimum_source_epoch or 100
        return WikidataSearchBatch(
            {
                label: (
                    WikidataSearchCandidate(
                        100 + index,
                        0,
                        source_ref="fake-wikidata",
                        source_epoch=epoch,
                    ),
                )
                for index, label in enumerate(labels)
            },
            provider_call_count=1,
        )

    def fetch_properties(self, keys, *, minimum_source_epoch=None):
        self.property_calls.append((tuple(keys), minimum_source_epoch))
        epoch = minimum_source_epoch or 100
        return WikidataPropertyBatch(
            {
                key: (
                    WikidataPropertyFact(
                        subject_qid=key[0],
                        property_pid=key[1],
                        value_kind=ExternalValueKind.WORLD_ENTITY,
                        value_qid=408,
                        entity_revision=123,
                        source_ref="fake-wikidata",
                        source_epoch=epoch,
                    ),
                )
                for key in keys
            },
            provider_call_count=1,
        )


def test_duplicate_discovery_labels_are_one_transport_search_batch() -> None:
    transport = FakeTransport()
    provider = WikidataLateProvider(transport)
    result = provider.fetch_batch(
        (
            ExternalRequest(
                1,
                ExternalRequestKind.CANDIDATE_DISCOVERY,
                "Springfield",
                None,
                None,
                None,
                1,
            ),
            ExternalRequest(
                2,
                ExternalRequestKind.CANDIDATE_DISCOVERY,
                "Springfield",
                None,
                None,
                None,
                1,
            ),
        )
    )
    assert transport.search_calls == [(("Springfield",), None)]
    assert result.provider_call_count == 1
    assert [
        item.discovered_candidates[0].provider_numeric_id for item in result.results
    ] == [100, 100]


def test_duplicate_qp_enrichment_keys_are_fetched_once() -> None:
    transport = FakeTransport()
    provider = WikidataLateProvider(transport)
    result = provider.fetch_batch(
        (
            ExternalRequest(
                1, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 123, 17, 1, 1
            ),
            ExternalRequest(
                2, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 123, 17, 2, 1
            ),
        )
    )
    assert transport.property_calls == [(((123, 17),), None)]
    assert result.provider_call_count == 1
    first = result.results[0].evidence[0]
    assert first.provider_property_numeric_id == 17
    assert first.value_provider_numeric_id == 408
    assert first.value_kind is ExternalValueKind.WORLD_ENTITY


def test_different_freshness_floors_form_separate_transport_microbatches() -> None:
    transport = FakeTransport()
    provider = WikidataLateProvider(transport)
    result = provider.fetch_batch(
        (
            ExternalRequest(
                1, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 123, 17, 1, 1, 1000
            ),
            ExternalRequest(
                2, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 123, 17, 1, 1, 2000
            ),
            ExternalRequest(
                3, ExternalRequestKind.PROPERTY_ENRICHMENT, None, 123, 17, 1, 1, 1000
            ),
        )
    )
    assert transport.property_calls == [(((123, 17),), 1000), (((123, 17),), 2000)]
    assert result.provider_call_count == 2
    assert result.results[0].evidence[0].source_epoch == 1000
    assert result.results[1].evidence[0].source_epoch == 2000


def test_identity_alignment_is_blocked_without_network_call() -> None:
    transport = FakeTransport()
    provider = WikidataLateProvider(transport)
    result = provider.fetch_batch(
        (
            ExternalRequest(
                1, ExternalRequestKind.IDENTITY_ALIGNMENT, None, 123, None, None, 1
            ),
        )
    )
    assert result.provider_call_count == 0
    assert result.results[0].error_ref == "wikidata:identity-proof-adapter-required"
    assert transport.search_calls == []
    assert transport.property_calls == []


def test_malformed_discovery_does_not_call_transport() -> None:
    transport = FakeTransport()
    provider = WikidataLateProvider(transport)
    result = provider.fetch_batch(
        (
            ExternalRequest(
                1, ExternalRequestKind.CANDIDATE_DISCOVERY, None, None, None, None, 1
            ),
        )
    )
    assert result.provider_call_count == 0
    assert result.results[0].error_ref == "wikidata:missing-search-label"
    assert transport.search_calls == []
