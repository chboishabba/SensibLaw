"""Snapshot-first Wikidata acquisition for late H9 residuals.

Zelph/Hugging Face is an acquisition source for the Wikidata namespace, not a
second world-entity namespace. Q/P identifiers therefore remain provider-native
Wikidata integers while this module records whether evidence came from a bounded
Zelph snapshot or a live Wikidata transport.

The transport is deliberately downstream of the PostgreSQL cache probe. Normal
execution is therefore:

    local DB cache -> Zelph/HF snapshot -> live Wikidata (only if required)

A stale snapshot is useful evidence but never gains truth/identity authority by
being cheap or local. Consumers that can observe freshness must request a live
read explicitly through ``WikidataTierPolicy``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from src.policy.wikidata_late_provider import (
    WikidataPropertyBatch,
    WikidataPropertyFact,
    WikidataSearchBatch,
    WikidataSearchCandidate,
    WikidataTransport,
)


class ZelphSnapshotQueryBackend(Protocol):
    """Minimal query surface expected from the existing Zelph/HF connector.

    The ITIR parent already owns manifest/shard routing and Zelph partial-load
    mechanics. SensibLaw consumes only typed Wikidata coordinates/results here
    rather than duplicating that transport implementation.
    """

    def search_wikidata_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> Mapping[str, Sequence[int]]: ...

    def fetch_wikidata_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> Mapping[tuple[int, int], Sequence[WikidataPropertyFact]]: ...


@dataclass(frozen=True, slots=True)
class WikidataTierPolicy:
    """Consumer-visible acquisition policy.

    ``fallback_on_snapshot_miss`` gives the normal cheap path. The two
    ``require_live_*`` flags are stronger freshness contracts: they force a live
    read even when the snapshot supplied a value. They are deliberately
    separate for name discovery and property evidence.
    """

    fallback_on_snapshot_miss: bool = True
    require_live_discovery: bool = False
    require_live_properties: bool = False


class ZelphHFWikidataTransport:
    """Adapt an existing Zelph/HF Wikidata query backend to WikidataTransport."""

    def __init__(
        self,
        backend: ZelphSnapshotQueryBackend,
        *,
        snapshot_ref: str,
        snapshot_revision: int | None = None,
    ) -> None:
        if not snapshot_ref.strip():
            raise ValueError("snapshot_ref must be non-empty")
        self.backend = backend
        self.snapshot_ref = snapshot_ref.strip()
        self.snapshot_revision = snapshot_revision

    def search_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> WikidataSearchBatch:
        unique_labels = tuple(dict.fromkeys(label for label in labels if label))
        if not unique_labels:
            return WikidataSearchBatch({}, 0)
        raw = self.backend.search_wikidata_entities(
            unique_labels, limit_per_label=limit_per_label
        )
        candidates: dict[str, tuple[WikidataSearchCandidate, ...]] = {}
        for label in unique_labels:
            seen: set[int] = set()
            rows: list[WikidataSearchCandidate] = []
            for raw_qid in raw.get(label, ()):
                qid = int(raw_qid)
                if qid <= 0 or qid in seen:
                    continue
                seen.add(qid)
                rows.append(WikidataSearchCandidate(qid=qid, rank=len(rows)))
                if len(rows) >= limit_per_label:
                    break
            candidates[label] = tuple(rows)
        return WikidataSearchBatch(candidates, 1)

    def fetch_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> WikidataPropertyBatch:
        unique_keys = tuple(sorted(set((int(q), int(p)) for q, p in keys)))
        if not unique_keys:
            return WikidataPropertyBatch({}, 0)
        raw = self.backend.fetch_wikidata_properties(unique_keys)
        facts: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = {}
        for key in unique_keys:
            rows: list[WikidataPropertyFact] = []
            for fact in raw.get(key, ()):
                if (int(fact.subject_qid), int(fact.property_pid)) != key:
                    raise ValueError("Zelph backend returned an unrequested Wikidata fact")
                rows.append(
                    WikidataPropertyFact(
                        subject_qid=fact.subject_qid,
                        property_pid=fact.property_pid,
                        value_kind=fact.value_kind,
                        value_qid=fact.value_qid,
                        value_text=fact.value_text,
                        value_symbol_kind=fact.value_symbol_kind,
                        value_numeric=fact.value_numeric,
                        entity_revision=(
                            fact.entity_revision
                            if fact.entity_revision is not None
                            else self.snapshot_revision
                        ),
                        source_ref=f"zelph-hf:{self.snapshot_ref}",
                    )
                )
            facts[key] = tuple(rows)
        return WikidataPropertyBatch(facts, 1)


class TieredWikidataTransport:
    """Use Zelph/HF first and live Wikidata only for required residual work."""

    def __init__(
        self,
        snapshot: WikidataTransport,
        live: WikidataTransport | None,
        *,
        policy: WikidataTierPolicy | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.live = live
        self.policy = policy or WikidataTierPolicy()

    def search_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> WikidataSearchBatch:
        unique_labels = tuple(dict.fromkeys(label for label in labels if label))
        if not unique_labels:
            return WikidataSearchBatch({}, 0)
        snapshot = self.snapshot.search_entities(
            unique_labels, limit_per_label=limit_per_label
        )
        live_labels: tuple[str, ...] = ()
        if self.live is not None:
            if self.policy.require_live_discovery:
                live_labels = unique_labels
            elif self.policy.fallback_on_snapshot_miss:
                live_labels = tuple(
                    label
                    for label in unique_labels
                    if not snapshot.candidates_by_label.get(label)
                )
        live = (
            self.live.search_entities(live_labels, limit_per_label=limit_per_label)
            if self.live is not None and live_labels
            else WikidataSearchBatch({}, 0)
        )

        merged: dict[str, tuple[WikidataSearchCandidate, ...]] = {}
        for label in unique_labels:
            sources = (
                (live.candidates_by_label.get(label, ()), snapshot.candidates_by_label.get(label, ()))
                if self.policy.require_live_discovery
                else (snapshot.candidates_by_label.get(label, ()), live.candidates_by_label.get(label, ()))
            )
            seen: set[int] = set()
            rows: list[WikidataSearchCandidate] = []
            for source_rows in sources:
                for candidate in source_rows:
                    qid = int(candidate.qid)
                    if qid in seen:
                        continue
                    seen.add(qid)
                    rows.append(WikidataSearchCandidate(qid=qid, rank=len(rows)))
                    if len(rows) >= limit_per_label:
                        break
                if len(rows) >= limit_per_label:
                    break
            merged[label] = tuple(rows)
        return WikidataSearchBatch(
            merged,
            snapshot.provider_call_count + live.provider_call_count,
        )

    def fetch_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> WikidataPropertyBatch:
        unique_keys = tuple(sorted(set((int(q), int(p)) for q, p in keys)))
        if not unique_keys:
            return WikidataPropertyBatch({}, 0)
        snapshot = self.snapshot.fetch_properties(unique_keys)
        live_keys: tuple[tuple[int, int], ...] = ()
        if self.live is not None:
            if self.policy.require_live_properties:
                live_keys = unique_keys
            elif self.policy.fallback_on_snapshot_miss:
                live_keys = tuple(
                    key for key in unique_keys if not snapshot.facts_by_key.get(key)
                )
        live = (
            self.live.fetch_properties(live_keys)
            if self.live is not None and live_keys
            else WikidataPropertyBatch({}, 0)
        )

        merged: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = {}
        for key in unique_keys:
            source_rows = (
                (live.facts_by_key.get(key, ()), snapshot.facts_by_key.get(key, ()))
                if self.policy.require_live_properties
                else (snapshot.facts_by_key.get(key, ()), live.facts_by_key.get(key, ()))
            )
            seen: set[tuple[object, ...]] = set()
            rows: list[WikidataPropertyFact] = []
            for facts in source_rows:
                for fact in facts:
                    # Semantic interpretation may later collapse agreeing values,
                    # but immutable evidence retains source/revision witnesses.
                    signature = (
                        int(fact.value_kind),
                        fact.value_qid,
                        fact.value_text,
                        fact.value_symbol_kind,
                        fact.value_numeric,
                        fact.entity_revision,
                        fact.source_ref,
                    )
                    if signature in seen:
                        continue
                    seen.add(signature)
                    rows.append(fact)
            merged[key] = tuple(rows)
        return WikidataPropertyBatch(
            merged,
            snapshot.provider_call_count + live.provider_call_count,
        )


__all__ = [
    "TieredWikidataTransport",
    "WikidataTierPolicy",
    "ZelphHFWikidataTransport",
    "ZelphSnapshotQueryBackend",
]
