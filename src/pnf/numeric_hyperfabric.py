"""Numeric multiscale PNF hyperfabric algebra.

The immutable evidence ledger may grow, but every promoted interface is a
smaller, denser numeric carrier. Strings are interned exactly once at the
parser/database boundary; graph identity, promotion, segmentation, lookup,
and provenance operate on integers and fixed-width digests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
from math import isfinite
from struct import pack
from typing import Callable, Iterable, Sequence


class SymbolKind(IntEnum):
    ORTH = 1
    LEMMA = 2
    POS = 3
    TAG = 4
    DEPENDENCY = 5
    MORPH_FEATURE = 6
    MORPH_VALUE = 7
    ENTITY_TYPE = 8
    PIPELINE_COMPONENT = 9
    FACTOR_TYPE = 10
    PREDICATE = 11
    ROLE = 12
    RESIDUAL_TYPE = 13
    OBJECT_KIND = 14
    DEFINITION = 15
    SCOPE = 16
    TEMPORAL = 17
    MODAL = 18
    GRAMMATICAL = 19


class RegionKind(IntEnum):
    SENTENCE = 1
    ADJACENT_SENTENCE = 2
    PARAGRAPH = 3
    ADJACENT_PARAGRAPH = 4
    ADAPTIVE_BLOCK = 5
    PROVISION = 6
    SECTION = 7
    CHAPTER = 8
    EXECUTION_WINDOW = 9
    DOCUMENT = 10
    TRANCHE = 11


class RegionEdgeKind(IntEnum):
    CONTAINS = 1
    ADJACENT = 2
    EXPORTS = 3
    RESOLVES = 4
    SUPPORTS = 5
    CONTINUES = 6
    EXECUTION_CONTAINS = 7


class ClosureState(IntEnum):
    OPEN = 1
    LOCALLY_CLOSED = 2
    CLOSED = 3
    FAILED = 4


class ExportKind(IntEnum):
    OBJECT = 1
    FACTOR = 2
    DEFINITION = 3
    SCOPE = 4
    DEMAND = 5
    SYMBOL_BINDING = 6
    TEMPORAL_STATE = 7
    MODAL_STATE = 8


class TargetKind(IntEnum):
    OBJECT = 1
    FACTOR = 2
    DEMAND = 3
    DEFINITION = 4
    SCOPE = 5
    TOKEN = 6
    SENTENCE = 7
    REGION = 8


class DemandState(IntEnum):
    OPEN = 1
    RESOLVED = 2
    DEFERRED_WORLD = 3
    FAILED = 4


class RecencyClass(IntEnum):
    SAME_REGION = 1
    PREVIOUS_SIBLING = 2
    NEAREST_VISIBLE = 3
    ENCLOSING_STRUCTURE = 4
    DOCUMENT = 5


class ResolutionState(IntEnum):
    UNRESOLVED = 1
    CANDIDATE = 2
    RESOLVED = 3
    INAPPLICABLE = 4


class WorkOperation(IntEnum):
    SENTENCE_CLOSE = 1
    ADJACENT_RECONCILE = 2
    REGION_CLOSE = 3
    HIERARCHY_PLAN = 4
    DOCUMENT_CLOSE = 5
    VISIBLE_INDEX_REFRESH = 6


class WorkState(IntEnum):
    READY = 1
    LEASED = 2
    COMPLETED = 3
    FAILED = 4


class KeyKind(IntEnum):
    FACTOR_TYPE = 1
    OBJECT_KIND = 2
    NORMALIZED_SYMBOL = 3
    ROLE = 4
    RESIDUAL_TYPE = 5
    DEFINITION = 6
    SCOPE = 7


def _encode_numeric(value: object) -> bytes:
    """Canonical binary encoding for numeric graph identity.

    Text is deliberately rejected. Lexical text must first be interned into a
    corpus-wide symbol id; only the resulting integer belongs in graph identity.
    """

    if value is None:
        return b"\x00"
    if value is False:
        return b"\x01"
    if value is True:
        return b"\x02"
    if isinstance(value, IntEnum):
        value = int(value)
    if isinstance(value, int):
        if not -(1 << 127) <= value < (1 << 127):
            raise OverflowError("numeric identity integer exceeds signed 128-bit range")
        return b"\x03" + int(value).to_bytes(16, "big", signed=True)
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("numeric identity does not admit NaN or infinity")
        return b"\x04" + pack(">d", value)
    if isinstance(value, bytes):
        return b"\x05" + len(value).to_bytes(8, "big") + value
    if isinstance(value, (tuple, list)):
        encoded = tuple(_encode_numeric(item) for item in value)
        return (
            b"\x06"
            + len(encoded).to_bytes(8, "big")
            + b"".join(len(item).to_bytes(8, "big") + item for item in encoded)
        )
    raise TypeError(
        "numeric graph identity accepts only integers, enums, finite floats, "
        "bytes, booleans, null, and numeric sequences"
    )


def numeric_digest(*values: object) -> bytes:
    payload = _encode_numeric(tuple(values))
    return sha256(payload).digest()


def symbol_digest(kind: SymbolKind | int, normalized_text: str) -> bytes:
    """Digest the one permitted lexical boundary before numeric interning."""

    encoded = normalized_text.encode("utf-8")
    return sha256(
        b"symbol:v1"
        + int(kind).to_bytes(2, "big", signed=False)
        + len(encoded).to_bytes(8, "big")
        + encoded
    ).digest()


@dataclass(frozen=True, slots=True)
class MdlProfile:
    node_weight: float = 1.0
    edge_weight: float = 0.75
    alternative_weight: float = 2.0
    unresolved_weight: float = 3.0
    boundary_weight: float = 4.0
    encoded_byte_weight: float = 1.0 / 1024.0
    rule_weight: float = 0.5
    closure_round_weight: float = 1.0
    query_ns_weight: float = 1.0 / 1_000_000.0
    promoted_object_weight: float = 0.25
    interface_member_weight: float = 0.5
    hierarchy_weight: float = 0.25
    promotion_alpha: float = 1.0
    promotion_beta: float = 1.0
    promotion_threshold: float = 0.0
    merge_threshold: float = 0.0
    max_window: int = 16
    beam_width: int = 4

    def __post_init__(self) -> None:
        numeric = (
            self.node_weight,
            self.edge_weight,
            self.alternative_weight,
            self.unresolved_weight,
            self.boundary_weight,
            self.encoded_byte_weight,
            self.rule_weight,
            self.closure_round_weight,
            self.query_ns_weight,
            self.promoted_object_weight,
            self.interface_member_weight,
            self.hierarchy_weight,
            self.promotion_alpha,
            self.promotion_beta,
            self.promotion_threshold,
            self.merge_threshold,
        )
        if any(not isfinite(value) or value < 0 for value in numeric[:14]):
            raise ValueError("MDL weights must be finite and non-negative")
        if not isfinite(self.promotion_threshold) or not isfinite(self.merge_threshold):
            raise ValueError("MDL thresholds must be finite")
        if self.max_window < 1 or self.beam_width < 1:
            raise ValueError("bounded segmentation requires positive limits")


@dataclass(frozen=True, slots=True)
class RegionMeasure:
    node_count: int
    edge_count: int
    alternative_count: int = 0
    unresolved_count: int = 0
    boundary_demand_weight: float = 0.0
    encoded_byte_count: int = 0
    rule_count: int = 0
    closure_rounds: int = 0
    query_cost_ns: int = 0
    promoted_object_count: int = 0
    interface_cardinality: int = 0
    hierarchy_cost: float = 0.0

    def __post_init__(self) -> None:
        integers = (
            self.node_count,
            self.edge_count,
            self.alternative_count,
            self.unresolved_count,
            self.encoded_byte_count,
            self.rule_count,
            self.closure_rounds,
            self.query_cost_ns,
            self.promoted_object_count,
            self.interface_cardinality,
        )
        if any(value < 0 for value in integers):
            raise ValueError("region measures must be non-negative")
        if (
            not isfinite(self.boundary_demand_weight)
            or self.boundary_demand_weight < 0
            or not isfinite(self.hierarchy_cost)
            or self.hierarchy_cost < 0
        ):
            raise ValueError("region costs must be finite and non-negative")

    def join(self, other: "RegionMeasure") -> "RegionMeasure":
        return RegionMeasure(
            node_count=self.node_count + other.node_count,
            edge_count=self.edge_count + other.edge_count,
            alternative_count=self.alternative_count + other.alternative_count,
            unresolved_count=self.unresolved_count + other.unresolved_count,
            boundary_demand_weight=(
                self.boundary_demand_weight + other.boundary_demand_weight
            ),
            encoded_byte_count=self.encoded_byte_count + other.encoded_byte_count,
            rule_count=self.rule_count + other.rule_count,
            closure_rounds=max(self.closure_rounds, other.closure_rounds),
            query_cost_ns=self.query_cost_ns + other.query_cost_ns,
            promoted_object_count=(
                self.promoted_object_count + other.promoted_object_count
            ),
            interface_cardinality=(
                self.interface_cardinality + other.interface_cardinality
            ),
            hierarchy_cost=self.hierarchy_cost + other.hierarchy_cost,
        )


def description_length(measure: RegionMeasure, profile: MdlProfile) -> float:
    return (
        profile.node_weight * measure.node_count
        + profile.edge_weight * measure.edge_count
        + profile.alternative_weight * measure.alternative_count
        + profile.unresolved_weight * measure.unresolved_count
        + profile.boundary_weight * measure.boundary_demand_weight
        + profile.encoded_byte_weight * measure.encoded_byte_count
        + profile.rule_weight * measure.rule_count
        + profile.closure_round_weight * measure.closure_rounds
        + profile.query_ns_weight * measure.query_cost_ns
        + profile.promoted_object_weight * measure.promoted_object_count
        + profile.interface_member_weight * measure.interface_cardinality
        + profile.hierarchy_weight * measure.hierarchy_cost
    )


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    information_gain: float
    representation_cost: float
    ambiguity_cost: float
    factor_participation: int = 0
    outward_demand_count: int = 0
    definition_count: int = 0
    recurrence_count: int = 0

    def __post_init__(self) -> None:
        floats = (
            self.information_gain,
            self.representation_cost,
            self.ambiguity_cost,
        )
        if any(not isfinite(value) or value < 0 for value in floats):
            raise ValueError("promotion evidence must be finite and non-negative")
        if min(
            self.factor_participation,
            self.outward_demand_count,
            self.definition_count,
            self.recurrence_count,
        ) < 0:
            raise ValueError("promotion counts must be non-negative")


def promotion_score(evidence: PromotionEvidence, profile: MdlProfile) -> float:
    structural_gain = (
        evidence.factor_participation
        + 2.0 * evidence.outward_demand_count
        + 2.0 * evidence.definition_count
        + 0.5 * evidence.recurrence_count
    )
    return (
        evidence.information_gain
        + structural_gain
        - profile.promotion_alpha * evidence.representation_cost
        - profile.promotion_beta * evidence.ambiguity_cost
    )


def should_promote(evidence: PromotionEvidence, profile: MdlProfile) -> bool:
    return promotion_score(evidence, profile) > profile.promotion_threshold


def compression_gain(
    left: RegionMeasure,
    right: RegionMeasure,
    merged: RegionMeasure,
    boundary_cost: float,
    profile: MdlProfile,
) -> float:
    if not isfinite(boundary_cost) or boundary_cost < 0:
        raise ValueError("boundary cost must be finite and non-negative")
    return (
        description_length(left, profile)
        + description_length(right, profile)
        + profile.boundary_weight * boundary_cost
        - description_length(merged, profile)
    )


@dataclass(frozen=True, slots=True)
class Segment:
    start: int
    end: int
    measure: RegionMeasure
    cost: float

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("segments require a non-empty half-open interval")
        if not isfinite(self.cost):
            raise ValueError("segment cost must be finite")


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    segments: tuple[Segment, ...]
    total_cost: float
    evaluated_candidates: int
    asymptotic_bound: int


def _prefix_join(measures: Sequence[RegionMeasure], start: int, end: int) -> RegionMeasure:
    aggregate = measures[start]
    for index in range(start + 1, end):
        aggregate = aggregate.join(measures[index])
    return aggregate


def bounded_segmentation(
    measures: Sequence[RegionMeasure],
    *,
    profile: MdlProfile,
    reconcile_cost: Callable[[int, int, RegionMeasure], float] | None = None,
    authored_boundary_penalty: Callable[[int, int], float] | None = None,
) -> SegmentationResult:
    """Windowed beam dynamic programming.

    Runtime is O(N * W * B) and therefore O(N) for fixed window ``W`` and beam
    width ``B``. It never considers arbitrary book-wide interval pairs.
    """

    if not measures:
        return SegmentationResult((), 0.0, 0, 0)
    n = len(measures)
    window = min(profile.max_window, n)
    beam = profile.beam_width
    paths: list[list[tuple[float, tuple[Segment, ...]]]] = [[] for _ in range(n + 1)]
    paths[0] = [(0.0, ())]
    evaluations = 0

    for end in range(1, n + 1):
        candidates: list[tuple[float, tuple[Segment, ...]]] = []
        for start in range(max(0, end - window), end):
            aggregate = _prefix_join(measures, start, end)
            local_cost = description_length(aggregate, profile)
            if reconcile_cost is not None:
                extra = reconcile_cost(start, end, aggregate)
                if not isfinite(extra) or extra < 0:
                    raise ValueError("reconciliation cost must be finite and non-negative")
                local_cost += extra
            if authored_boundary_penalty is not None:
                penalty = authored_boundary_penalty(start, end)
                if not isfinite(penalty) or penalty < 0:
                    raise ValueError("authored-boundary penalty must be non-negative")
                local_cost += penalty
            segment = Segment(start=start, end=end, measure=aggregate, cost=local_cost)
            for prior_cost, prior_segments in paths[start][:beam]:
                candidates.append((prior_cost + local_cost, (*prior_segments, segment)))
                evaluations += 1
        candidates.sort(
            key=lambda item: (
                item[0],
                len(item[1]),
                tuple((segment.start, segment.end) for segment in item[1]),
            )
        )
        paths[end] = candidates[:beam]

    total_cost, segments = paths[n][0]
    return SegmentationResult(
        segments=segments,
        total_cost=total_cost,
        evaluated_candidates=evaluations,
        asymptotic_bound=n * window * beam,
    )


def ancestor_powers(distance: int) -> tuple[int, ...]:
    """Return binary-lifting powers needed to traverse ``distance`` ancestors."""

    if distance < 0:
        raise ValueError("ancestor distance must be non-negative")
    powers: list[int] = []
    bit = 0
    remaining = distance
    while remaining:
        if remaining & 1:
            powers.append(bit)
        remaining >>= 1
        bit += 1
    return tuple(reversed(powers))


def active_cardinality_decreases(levels: Iterable[int]) -> bool:
    values = tuple(int(value) for value in levels)
    return all(next_value <= value for value, next_value in zip(values, values[1:]))


__all__ = [
    "ClosureState",
    "DemandState",
    "ExportKind",
    "KeyKind",
    "MdlProfile",
    "PromotionEvidence",
    "RecencyClass",
    "RegionEdgeKind",
    "RegionKind",
    "RegionMeasure",
    "ResolutionState",
    "Segment",
    "SegmentationResult",
    "SymbolKind",
    "TargetKind",
    "WorkOperation",
    "WorkState",
    "active_cardinality_decreases",
    "ancestor_powers",
    "bounded_segmentation",
    "compression_gain",
    "description_length",
    "numeric_digest",
    "promotion_score",
    "should_promote",
    "symbol_digest",
]
