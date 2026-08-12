from __future__ import annotations

from dataclasses import dataclass, field

from src.policy.external_demand import ExternalValueKind
from src.policy.wikidata_late_provider import (
    WikidataPropertyBatch,
    WikidataPropertyFact,
    WikidataSearchBatch,
    WikidataSearchCandidate,
)
from src.policy.wikidata_tiered_transport import (
    TieredWikidataTransport,
    WikidataTierPolicy,
    ZelphHFWikidataTransport,
    ZelphSnapshotPropertyResult,
    ZelphSnapshotSearchResult,
)


@dataclass
class FakeZelphBackend:
    labels: dict[str, tuple[int, ...]] = field(default_factory=dict)
    facts: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = field(default_factory=dict)
    search_acquisition_calls: int = 1
    property_acquisition_calls: int = 1
    search_calls: list[tuple[str, ...]] = field(default_factory=list)
    property_calls: list[tuple[tuple[int, int], ...]] = field(default_factory=list)

    def search_wikidata_entities(self, labels, *, limit_per_label):
        self.search_calls.append(tuple(labels))
        return ZelphSnapshotSearchResult(
            {label: self.labels.get(label, ())[:limit_per_label] for label in labels},
            self.search_acquisition_calls,
        )

    def fetch_wikidata_properties(self, keys):
        self.property_calls.append(tuple(keys))
        return ZelphSnapshotPropertyResult(
            {key: self.facts.get(key, ()) for key in keys},
            self.property_acquisition_calls,
        )


@dataclass
class FakeLiveTransport:
    candidates: dict[str, tuple[WikidataSearchCandidate, ...]] = field(default_factory=dict)
    facts: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = field(default_factory=dict)
    search_calls: list[tuple[str, ...]] = field(default_factory=list)
    property_calls: list[tuple[tuple[int, int], ...]] = field(default_factory=list)

    def search_entities(self, labels, *, limit_per_label):
        self.search_calls.append(tuple(labels))
        return WikidataSearchBatch(
            {label: self.candidates.get(label, ())[:limit_per_label] for label in labels},
            1,
        )

    def fetch_properties(self, keys):
        self.property_calls.append(tuple(keys))
        return WikidataPropertyBatch({key: self.facts.get(key, ()) for key in keys}, 1)


def _snapshot(backend: FakeZelphBackend) -> ZelphHFWikidataTransport:
    return ZelphHFWikidataTransport(
        backend,
        snapshot_ref="acrion/zelph:wikidata-20260309-all-pruned",
        snapshot_revision=20260309,
    )


def test_snapshot_candidate_hit_does_not_touch_live_transport() -> None:
    backend = FakeZelphBackend(labels={"Springfield": (180672, 28515)})
    live = FakeLiveTransport()
    transport = TieredWikidataTransport(_snapshot(backend), live)

    result = transport.search_entities(("Springfield",), limit_per_label=8)

    assert [row.qid for row in result.candidates_by_label["Springfield"]] == [180672, 28515]
    assert backend.search_calls == [("Springfield",)]
    assert live.search_calls == []
    assert result.provider_call_count == 1


def test_resident_snapshot_can_report_zero_external_acquisition_calls() -> None:
    backend = FakeZelphBackend(
        labels={"Springfield": (180672,)},
        search_acquisition_calls=0,
    )
    result = _snapshot(backend).search_entities(("Springfield",), limit_per_label=8)
    assert result.provider_call_count == 0
    assert [row.qid for row in result.candidates_by_label["Springfield"]] == [180672]


def test_hf_snapshot_can_report_multiple_object_reads() -> None:
    key = (180672, 17)
    backend = FakeZelphBackend(
        facts={
            key: (
                WikidataPropertyFact(
                    subject_qid=180672,
                    property_pid=17,
                    value_kind=ExternalValueKind.WORLD_ENTITY,
                    value_qid=408,
                ),
            )
        },
        property_acquisition_calls=3,
    )
    result = _snapshot(backend).fetch_properties((key,))
    assert result.provider_call_count == 3


def test_only_snapshot_property_misses_fall_through_to_live() -> None:
    australia_key = (180672, 17)
    missing_key = (42, 17)
    snapshot_fact = WikidataPropertyFact(
        subject_qid=180672,
        property_pid=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_qid=408,
    )
    live_fact = WikidataPropertyFact(
        subject_qid=42,
        property_pid=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_qid=145,
        source_ref="wikidata-live:test",
    )
    backend = FakeZelphBackend(facts={australia_key: (snapshot_fact,)})
    live = FakeLiveTransport(facts={missing_key: (live_fact,)})
    transport = TieredWikidataTransport(_snapshot(backend), live)

    result = transport.fetch_properties((australia_key, missing_key))

    assert backend.property_calls == [tuple(sorted((australia_key, missing_key)))]
    assert live.property_calls == [(missing_key,)]
    snapshot_row = result.facts_by_key[australia_key][0]
    assert snapshot_row.value_qid == 408
    assert snapshot_row.entity_revision == 20260309
    assert snapshot_row.source_ref == "zelph-hf:acrion/zelph:wikidata-20260309-all-pruned"
    assert result.facts_by_key[missing_key] == (live_fact,)
    assert result.provider_call_count == 2


def test_freshness_sensitive_property_forces_live_recheck_on_snapshot_hit() -> None:
    key = (180672, 17)
    snapshot_fact = WikidataPropertyFact(
        subject_qid=180672,
        property_pid=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_qid=408,
    )
    live_fact = WikidataPropertyFact(
        subject_qid=180672,
        property_pid=17,
        value_kind=ExternalValueKind.WORLD_ENTITY,
        value_qid=408,
        entity_revision=20260812,
        source_ref="wikidata-live:2026-08-12",
    )
    backend = FakeZelphBackend(facts={key: (snapshot_fact,)})
    live = FakeLiveTransport(facts={key: (live_fact,)})
    transport = TieredWikidataTransport(
        _snapshot(backend),
        live,
        policy=WikidataTierPolicy(require_live_properties=True),
    )

    result = transport.fetch_properties((key,))

    assert live.property_calls == [(key,)]
    # Live evidence leads because the consumer explicitly required freshness;
    # the older snapshot remains available as a separate provenance witness.
    assert result.facts_by_key[key][0].source_ref == "wikidata-live:2026-08-12"
    assert len(result.facts_by_key[key]) == 2


def test_same_qid_from_snapshot_and_live_is_one_candidate() -> None:
    backend = FakeZelphBackend(labels={"Springfield": (180672, 180672)})
    live = FakeLiveTransport(
        candidates={
            "Springfield": (
                WikidataSearchCandidate(180672, 0),
                WikidataSearchCandidate(28515, 1),
            )
        }
    )
    transport = TieredWikidataTransport(
        _snapshot(backend),
        live,
        policy=WikidataTierPolicy(require_live_discovery=True),
    )

    result = transport.search_entities(("Springfield",), limit_per_label=8)

    assert [row.qid for row in result.candidates_by_label["Springfield"]] == [180672, 28515]
    assert [row.rank for row in result.candidates_by_label["Springfield"]] == [0, 1]


def test_snapshot_backend_rejects_wrong_subject_property_fact() -> None:
    key = (180672, 17)
    backend = FakeZelphBackend(
        facts={
            key: (
                WikidataPropertyFact(
                    subject_qid=999,
                    property_pid=17,
                    value_kind=ExternalValueKind.WORLD_ENTITY,
                    value_qid=408,
                ),
            )
        }
    )
    transport = _snapshot(backend)

    try:
        transport.fetch_properties((key,))
    except ValueError as exc:
        assert "unrequested Wikidata fact" in str(exc)
    else:
        raise AssertionError("wrong-subject Zelph fact must be rejected")


def test_negative_acquisition_count_is_rejected() -> None:
    try:
        ZelphSnapshotSearchResult({}, -1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative acquisition count must be rejected")
