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
import re
import subprocess
from typing import Mapping, Protocol, Sequence

from src.policy.external_demand import ExternalValueKind
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


class ZelphCliSnapshotQueryBackend:
    """Query a local or HF-routed Zelph artifact through its CLI.

    A manifest source uses Zelph's routed ``.load-partial`` path and therefore
    fetches only the route-selected HF shards.  A local ``.bin`` source uses a
    normal full load; callers should reserve that mode for a machine with
    enough memory.  This adapter deliberately exposes acquisition subprocess
    count as its literal I/O metric; the Zelph process also emits transfer
    diagnostics when ``ZELPH_HF_TRANSFER_LOG`` is configured.
    """

    _QID_RE = re.compile(r"https://www\.wikidata\.org/wiki/(Q([1-9][0-9]*))")
    _QID_VALUE_RE = re.compile(r"^Q([1-9][0-9]*)(?:\s+\(.*\))?$")

    def __init__(
        self,
        executable: str,
        source: str,
        *,
        source_ref: str | None = None,
        language: str = "en",
        timeout_seconds: float = 300.0,
    ) -> None:
        if not executable.strip():
            raise ValueError("Zelph executable must be non-empty")
        if not source.strip():
            raise ValueError("Zelph source must be non-empty")
        if not language.strip():
            raise ValueError("Zelph language must be non-empty")
        if timeout_seconds <= 0:
            raise ValueError("Zelph timeout must be positive")
        self.executable = executable
        self.source = source
        self.source_ref = source_ref or f"zelph:{source}"
        self.language = language
        self.timeout_seconds = timeout_seconds

    @property
    def _is_manifest(self) -> bool:
        return self.source.endswith(".json") or self.source.startswith("hf://")

    @staticmethod
    def _quote_command_text(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _load_command(
        self, *, route_name: str | None = None, name_only: bool = False
    ) -> str:
        source = self._quote_command_text(self.source)
        if self._is_manifest and route_name is not None:
            return (
                f".load-partial {source} "
                f"route-name={self._quote_command_text(route_name)} "
                f"route-lang={self.language}"
            )
        if self._is_manifest:
            if name_only:
                return (
                    f".load-partial {source} left=none right=none "
                    "nameOfNode=none"
                )
            return f".load-partial {source} nameOfNode=none nodeOfName=none"
        return f".load {source}"

    def _run(self, commands: Sequence[str], *, allow_missing_node: bool = False) -> str:
        script = "\n".join((*commands, ".quit", ""))
        try:
            completed = subprocess.run(
                [self.executable],
                input=script,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Zelph executable unavailable: {self.executable}") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Zelph query timed out after {self.timeout_seconds}s") from exc
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        missing_node_only = allow_missing_node and "No node found with name" in output
        if completed.returncode != 0 or ("Error in line" in output and not missing_node_only):
            raise RuntimeError(f"Zelph query failed ({completed.returncode}): {output[-4000:]}")
        return output

    @classmethod
    def _candidate_from_node_output(
        cls, output: str, *, source_ref: str
    ) -> WikidataSearchCandidate | None:
        match = cls._QID_RE.search(output)
        if match is None:
            return None
        return WikidataSearchCandidate(
            qid=int(match.group(2)), rank=0, source_ref=source_ref
        )

    def search_wikidata_entities(
        self, labels: Sequence[str], *, limit_per_label: int
    ) -> ZelphSnapshotSearchResult:
        if limit_per_label < 1:
            raise ValueError("limit_per_label must be positive")
        candidates: dict[str, tuple[int, ...]] = {}
        unique_labels = tuple(dict.fromkeys(label for label in labels if label.strip()))
        if not unique_labels:
            return ZelphSnapshotSearchResult({}, 0)
        commands = [
            f".lang {self.language}",
            self._load_command(name_only=self._is_manifest),
        ]
        for index, label in enumerate(unique_labels):
            commands.extend(
                (
                    f'%(print "__SL_LOOKUP_{index}__")',
                    f".node {self._quote_command_text(label)}",
                )
            )
        output = self._run(commands, allow_missing_node=True)
        sections = output.split("__SL_LOOKUP_")[1:]
        for index, label in enumerate(unique_labels):
            section = next(
                (part for part in sections if part.startswith(f"{index}__")), ""
            )
            candidate = self._candidate_from_node_output(section, source_ref=self.source_ref)
            candidates[label] = (candidate.qid,) if candidate is not None else ()
        acquisitions = 1
        return ZelphSnapshotSearchResult(candidates, acquisitions)

    @staticmethod
    def _property_query(subject_qid: int, property_pid: int) -> str:
        return (
            "sparql\n"
            "SELECT ?value WHERE { "
            f"wd:Q{subject_qid} wdt:P{property_pid} ?value . "
            "}"
        )

    @staticmethod
    def _result_values(output: str) -> tuple[str, ...]:
        values: list[str] = []
        in_results = False
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line == "?value":
                in_results = True
                continue
            if not in_results or line.startswith("--") or not line:
                continue
            values.append(line.split("\t", 1)[0].strip())
        return tuple(dict.fromkeys(values))

    @classmethod
    def _fact_for_value(
        cls,
        subject_qid: int,
        property_pid: int,
        value: str,
        *,
        source_ref: str,
    ) -> WikidataPropertyFact | None:
        qid_match = cls._QID_VALUE_RE.fullmatch(value)
        if qid_match is not None:
            return WikidataPropertyFact(
                subject_qid=subject_qid,
                property_pid=property_pid,
                value_kind=ExternalValueKind.WORLD_ENTITY,
                value_qid=int(qid_match.group(1)),
                source_ref=source_ref,
            )
        if value.isdigit():
            return WikidataPropertyFact(
                subject_qid=subject_qid,
                property_pid=property_pid,
                value_kind=ExternalValueKind.NUMERIC,
                value_numeric=int(value),
                source_ref=source_ref,
            )
        return None

    def fetch_wikidata_properties(
        self, keys: Sequence[tuple[int, int]]
    ) -> ZelphSnapshotPropertyResult:
        unique_keys = tuple(sorted(set((int(q), int(p)) for q, p in keys)))
        if not unique_keys:
            return ZelphSnapshotPropertyResult({}, 0)
        commands = [self._load_command(), ".import sparql"]
        facts: dict[tuple[int, int], tuple[WikidataPropertyFact, ...]] = {}
        for subject_qid, property_pid in unique_keys:
            commands.extend((self._property_query(subject_qid, property_pid), ""))
        output = self._run(commands)
        # Each repeated query has its own ?value header; preserve query order
        # while parsing the corresponding result section.
        sections = output.split("?value\n")[1:]
        for key, section in zip(unique_keys, sections, strict=False):
            section = section.split("--", 1)[0]
            rows = tuple(
                fact
                for value in self._result_values("?value\n" + section)
                if (fact := self._fact_for_value(*key, value, source_ref=self.source_ref))
                is not None
            )
            facts[key] = rows
        return ZelphSnapshotPropertyResult(facts, 1)


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
    "ZelphCliSnapshotQueryBackend",
    "ZelphSnapshotPropertyResult",
    "ZelphSnapshotQueryBackend",
    "ZelphSnapshotSearchResult",
]
