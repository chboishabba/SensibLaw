"""Parser executors that emit immutable canonical observation deltas.

The conservative default parses the whole document and projects complete sentence deltas.
A region executor may parse regions concurrently only when canonical character and token
coordinates were fixed before parsing. Region completion order never changes delta identity
or final semantic order.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from src.pnf.streaming_fixed_point import ObservationDelta
from src.pnf.streaming_operator_executor import parser_sentence_deltas
from src.policy.carriers.canonical import canonical_sha256
from src.sensiblaw.interfaces import parse_canonical_text


PARSER_REGION_SCHEMA_VERSION = "sl.pnf.parser_region.v0_1"
PARSER_DELTA_EXECUTION_SCHEMA_VERSION = "sl.pnf.parser_delta_execution.v0_1"


@dataclass(frozen=True)
class CanonicalParserRegion:
    document_ref: str
    region_ref: str
    sequence_no: int
    canonical_text: str
    char_start: int
    char_end: int
    token_start: int
    token_count: int
    coverage_barrier: str = "section"

    def __post_init__(self) -> None:
        if self.sequence_no < 0:
            raise ValueError("parser region sequence_no must be non-negative")
        if self.char_start < 0 or self.char_end < self.char_start:
            raise ValueError("parser region character coordinates are invalid")
        if len(self.canonical_text) != self.char_end - self.char_start:
            raise ValueError("parser region text length disagrees with coordinates")
        if self.token_start < 0 or self.token_count < 0:
            raise ValueError("parser region token coordinates are invalid")

    @property
    def region_digest(self) -> str:
        return canonical_sha256(self.to_dict(include_digest=False))

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": PARSER_REGION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "region_ref": self.region_ref,
            "sequence_no": self.sequence_no,
            "canonical_text": self.canonical_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "token_start": self.token_start,
            "token_count": self.token_count,
            "coverage_barrier": self.coverage_barrier,
        }
        if include_digest:
            payload["region_digest"] = self.region_digest
        return payload


@dataclass(frozen=True)
class ParserDeltaExecution:
    document_ref: str
    executor_ref: str
    worker_count: int
    region_refs: tuple[str, ...]
    deltas: tuple[ObservationDelta, ...]

    @property
    def execution_ref(self) -> str:
        return "parser-delta-execution:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": PARSER_DELTA_EXECUTION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "executor_ref": self.executor_ref,
            "worker_count": self.worker_count,
            "region_refs": list(self.region_refs),
            "delta_refs": [row.delta_ref for row in self.deltas],
            "physical_completion_order_semantic_effect": "none",
        }
        if include_ref:
            payload["execution_ref"] = self.execution_ref
        return payload


class ParserDeltaExecutor(Protocol):
    executor_ref: str

    def execute(self, *, document_ref: str, canonical_text: str) -> ParserDeltaExecution: ...


class WholeDocumentSentenceParserExecutor:
    executor_ref = "parser-delta-executor:whole-document-sentences:v0_1"

    def execute(self, *, document_ref: str, canonical_text: str) -> ParserDeltaExecution:
        parsed = parse_canonical_text(canonical_text)
        deltas = parser_sentence_deltas(
            document_ref=document_ref,
            parsed_document=parsed,
        )
        return ParserDeltaExecution(
            document_ref=document_ref,
            executor_ref=self.executor_ref,
            worker_count=1,
            region_refs=("document-global",),
            deltas=deltas,
        )


def _parse_region(
    region: CanonicalParserRegion,
    parser: Callable[[str], Mapping[str, Any]],
) -> tuple[str, tuple[ObservationDelta, ...]]:
    parsed = parser(region.canonical_text)
    local = parser_sentence_deltas(
        document_ref=region.document_ref,
        parsed_document=parsed,
    )
    adjusted: list[ObservationDelta] = []
    for sentence_offset, delta in enumerate(local):
        observations = []
        refs = []
        for row in delta.observations:
            token = dict(row.get("token") or {})
            token["index"] = int(token.get("index", 0)) + region.token_start
            token["head_index"] = int(token.get("head_index", 0)) + region.token_start
            token["start"] = int(token.get("start", 0)) + region.char_start
            token["end"] = int(token.get("end", 0)) + region.char_start
            ref = "parser-observation:" + canonical_sha256(
                {
                    "document_ref": region.document_ref,
                    "region_ref": region.region_ref,
                    "sequence_no": region.sequence_no,
                    "sentence_offset": sentence_offset,
                    "token": token,
                }
            )
            refs.append(ref)
            observations.append(
                {
                    **dict(row),
                    "observation_ref": ref,
                    "token": token,
                    "region_ref": region.region_ref,
                }
            )
        adjusted.append(
            ObservationDelta(
                document_ref=region.document_ref,
                batch_ref="parser-region-batch:"
                + canonical_sha256(
                    {
                        "region_digest": region.region_digest,
                        "sentence_offset": sentence_offset,
                        "observation_refs": sorted(refs),
                    }
                ),
                scope_ref=f"{region.region_ref}:sentence:{sentence_offset}",
                sequence_no=region.sequence_no * 1_000_000 + sentence_offset,
                parser_contract=str(
                    (parsed.get("parser_receipt") or {}).get("contract_ref")
                    or "parser-region-adapter:v0_1"
                ),
                observation_refs=tuple(sorted(refs)),
                observations=tuple(observations),
                token_start=region.token_start + delta.token_start,
                token_end=region.token_start + delta.token_end,
                char_start=region.char_start + delta.char_start,
                char_end=region.char_start + delta.char_end,
                token_count=delta.token_count,
                coverage_barrier=region.coverage_barrier,
                coverage_complete=True,
            )
        )
    if sum(row.token_count for row in adjusted) != region.token_count:
        raise ValueError("parsed region token count disagrees with fixed region map")
    return region.region_ref, tuple(adjusted)


class PresegmentedRegionParserExecutor:
    executor_ref = "parser-delta-executor:presegmented-regions:v0_1"

    def __init__(
        self,
        *,
        regions: Sequence[CanonicalParserRegion],
        workers: int = 2,
        parser: Callable[[str], Mapping[str, Any]] = parse_canonical_text,
    ):
        if not 1 <= workers <= 32:
            raise ValueError("parser workers must be between 1 and 32")
        if not regions:
            raise ValueError("presegmented parser requires regions")
        self.regions = tuple(sorted(regions, key=lambda row: row.sequence_no))
        self.workers = workers
        self.parser = parser

    def execute(self, *, document_ref: str, canonical_text: str) -> ParserDeltaExecution:
        if any(row.document_ref != document_ref for row in self.regions):
            raise ValueError("parser regions cross document boundaries")
        ordered_text = "".join(row.canonical_text for row in self.regions)
        if ordered_text != canonical_text:
            raise ValueError("parser regions do not exactly cover canonical text")
        results: dict[str, tuple[ObservationDelta, ...]] = {}
        with ProcessPoolExecutor(max_workers=self.workers) as pool:
            futures: dict[Future[tuple[str, tuple[ObservationDelta, ...]]], str] = {
                pool.submit(_parse_region, region, self.parser): region.region_ref
                for region in self.regions
            }
            for future in as_completed(futures):
                region_ref, deltas = future.result()
                results[region_ref] = deltas
        deltas = tuple(
            sorted(
                (
                    delta
                    for region in self.regions
                    for delta in results[region.region_ref]
                ),
                key=lambda row: (row.sequence_no, row.delta_ref),
            )
        )
        return ParserDeltaExecution(
            document_ref=document_ref,
            executor_ref=self.executor_ref,
            worker_count=self.workers,
            region_refs=tuple(row.region_ref for row in self.regions),
            deltas=deltas,
        )


__all__ = [
    "CanonicalParserRegion",
    "ParserDeltaExecution",
    "ParserDeltaExecutor",
    "PresegmentedRegionParserExecutor",
    "WholeDocumentSentenceParserExecutor",
]
