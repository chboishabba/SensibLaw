"""Snapshot-first Wikidata acquisition for late H9 residuals.

Zelph/Hugging Face is an acquisition source for the Wikidata namespace, not a
second world-entity namespace. Q/P identifiers therefore remain provider-native
Wikidata integers while this module records whether evidence came from a bounded
Zelph snapshot or a live Wikidata transport.

Normal execution is:

    local DB cache -> Zelph/HF snapshot -> live Wikidata (only if required)

Freshness is consumer/request relative.  A snapshot with ``snapshot_epoch`` less
than a request's ``minimum_source_epoch`` is skipped without I/O rather than
queried and then rejected downstream.
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


@dataclass(frozen=True, slots=True)
class ZelphSnapshotSearchResult:
    candidates_by_label: Mapping[str, Sequence[int]]
    acquisition_call_count: int

    def __post_init__(self) -> None:
        if self.acquisition_call_count < 0:
            raise ValueError("acquisition_call_count must be non-negative")


@dataclass(frozen=True, slots=True)
class ZelphSnapshotPropertyResult:
    facts_by_key: Mapping[tuple[int, int], Sequence[WikidataPropertyFact]]
    acquisition_call_count: int

    def __post_init__(self) -> None:
        if self.acquisition_call_count < 0:
            raise ValueError("acquisition_call_count must be non-negative")


class ZelphSnapshotQueryBackend(Protocol):
    """Thin typed seam over the existing ITIR Zelph/HF transport/runtime.

    The backend reports literal acquisition I/O. A resident Zelph query may
    report zero; an HF partial load reports the object/shard reads it performed.
    """

    def search_wikidata_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> ZelphSnapshotSearchResult: ...

    def fetch_wikidata_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> ZelphSnapshotPropertyResult: ...


@dataclass(frozen=True, slots=True)
class WikidataTierPolicy:
    """Optional stronger acquisition policy layered over request freshness."""

    fallback_on_snapshot_miss: bool = True
    require_live_discovery: bool = False
    require_live_properties: bool = False


class ZelphHFWikidataTransport:
    """Adapt the existing Zelph/HF Wikidata query backend to WikidataTransport."""

    def __init__(
        self,
        backend: ZelphSnapshotQueryBackend,
        *,
        snapshot_ref: str,
        snapshot_epoch: int | None,
        snapshot_revision: int | None = None,
    ) -> None:
        if not snapshot_ref.strip():
            raise ValueError("snapshot_ref must be non-empty")
        if snapshot_epoch is not None and snapshot_epoch <= 0:
            raise ValueError("snapshot_epoch must be positive")
        self.backend = backend
        self.snapshot_ref = snapshot_ref.strip()
        self.snapshot_epoch = snapshot_epoch
        self.snapshot_revision = snapshot_revision

    def _satisfies_floor(self, minimum_source_epoch: int | None) -> bool:
        if minimum_source_epoch is None:
            return True
        return self.snapshot_epoch is not None and self.snapshot_epoch >= minimum_source_epoch

    def search_entities(
        self,
        labels: Sequence[str],
        *,
        limit_per_label: int,
        minimum_source_epoch: int | None = None,
    ) -> WikidataSearchBatch:
        unique_labels = tuple(dict.fromkeys(label for label in labels if label))
        if not unique_labels or not self._satisfies_floor(minimum_source_epoch):
            return WikidataSearchBatch({}, 0)
        result = self.backend.search_wikidata_entities(
            unique_labels, limit_per_label=limit_per_label
        )
        candidates: dict[str, tuple[WikidataSearchCandidate, ...]] = {}
        source_ref = f"zelph-hf:{self.snapshot_ref}"
        for label in unique_labels:
            seen: set[int] = set()
            rows: list[WikidataSearchCandidate] = []
            for raw_qid in result.candidates_by_label.get(label, ()):
                qid = int(raw_qid)
                if qid <= 0 or qid in seen:
                    continue
                seen.add(qid)
                rows.append(
                    WikidataSearchCandidate(
                        qid=qid,
                        rank=len(rows),
                        source_ref=source_ref,
                        source_epoch=self.snapshot_epoch,
                    )
                )
                if len(rows) >= limit_per_label:
                    break
            candidates[label] = tuple(rows)
        return WikidataSearchBatch(candidates, result.acquisition_call_count)

    def fetch_properties(
        self,
        keys: Sequence[tuple[int, int]],
        *,
        minimum_source_epoch: int | None = None,
    ) -> WikidataPropertyBatch:
        unique_keys = tuple(sorted(set((int(q), int(p)) for q, p in keys)))
        if not unique_keys or not self._satisfies_floor(minimum_source_epoch):
            return WikidataPropertyBatch({}, 0)
        result = self.backend.fetch_wikidata_properties(unique_keys)
        facts: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = {}
        for key in unique_keys:
            rows: list[WikidataPropertyFact] = []
            for fact in result.facts_by_key.get(key, ()):
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
                        entity_revision=(fact.entity_revision if fact.entity_revision is not None else self.snapshot_revision),
                        source_ref=f"zelph-hf:{self.snapshot_ref}",
                        source_epoch=self.snapshot_epoch,
                    )
                )
            facts[key] = tuple(rows)
        return WikidataPropertyBatch(facts, result.acquisition_call_count)


class TieredWikidataTransport:
    """Use Zelph/HF first and live Wikidata only for remaining required work."""

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
        self,
        labels: Sequence[str],
        *,
        limit_per_label: int,
        minimum_source_epoch: int | None = None,
    ) -> WikidataSearchBatch:
        unique_labels = tuple(dict.fromkeys(label for label in labels if label))
        if not unique_labels:
            return WikidataSearchBatch({}, 0)
        snapshot = self.snapshot.search_entities(
            unique_labels,
            limit_per_label=limit_per_label,
            minimum_source_epoch=minimum_source_epoch,
        )
        live_labels: tuple[str, ...] = ()
        if self.live is not None:
            if self.policy.require_live_discovery:
                live_labels = unique_labels
            elif self.policy.fallback_on_snapshot_miss:
                live_labels = tuple(label for label in unique_labels if not snapshot.candidates_by_label.get(label))
        live = (
            self.live.search_entities(
                live_labels,
                limit_per_label=limit_per_label,
                minimum_source_epoch=minimum_source_epoch,
            )
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
                    rows.append(
                        WikidataSearchCandidate(
                            qid=qid,
                            rank=len(rows),
                            source_ref=candidate.source_ref,
                            source_epoch=candidate.source_epoch,
                        )
                    )
                    if len(rows) >= limit_per_label:
                        break
                if len(rows) >= limit_per_label:
                    break
            merged[label] = tuple(rows)
        return WikidataSearchBatch(merged, snapshot.provider_call_count + live.provider_call_count)

    def fetch_properties(
        self,
        keys: Sequence[tuple[int, int]],
        *,
        minimum_source_epoch: int | None = None,
    ) -> WikidataPropertyBatch:
        unique_keys = tuple(sorted(set((int(q), int(p)) for q, p in keys)))
        if not unique_keys:
            return WikidataPropertyBatch({}, 0)
        snapshot = self.snapshot.fetch_properties(
            unique_keys,
            minimum_source_epoch=minimum_source_epoch,
        )
        live_keys: tuple[tuple[int, int], ...] = ()
        if self.live is not None:
            if self.policy.require_live_properties:
                live_keys = unique_keys
            elif self.policy.fallback_on_snapshot_miss:
                live_keys = tuple(key for key in unique_keys if not snapshot.facts_by_key.get(key))
        live = (
            self.live.fetch_properties(live_keys, minimum_source_epoch=minimum_source_epoch)
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
                    signature = (
                        int(fact.value_kind), fact.value_qid, fact.value_text,
                        fact.value_symbol_kind, fact.value_numeric,
                        fact.entity_revision, fact.source_ref, fact.source_epoch,
                    )
                    if signature in seen:
                        continue
                    seen.add(signature)
                    rows.append(fact)
            merged[key] = tuple(rows)
        return WikidataPropertyBatch(merged, snapshot.provider_call_count + live.provider_call_count)


__all__ = [
    "TieredWikidataTransport",
    "WikidataTierPolicy",
    "ZelphHFWikidataTransport",
    "ZelphSnapshotPropertyResult",
    "ZelphSnapshotQueryBackend",
    "ZelphSnapshotSearchResult",
]
