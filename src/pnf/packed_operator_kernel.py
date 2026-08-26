"""Sentence-local PNF operator recognition over packed fibre memory.

This is the first A2 semantic displacement kernel.  It reads
``PackedSentenceFibre`` columns directly: no unpack to token objects, no SQL,
and no corpus-global token id is required.  The output is deliberately small:
operator candidate masks plus exact fibre-local dependency topology.  Existing
factor/residual construction remains the authority consumer until a later
tranche moves that layer as well.

The scalar mask evaluator is the reference physical implementation.  The
``GuardedSwarColumn`` implementation is an experimental SWAR candidate for
fixed-width equality/set-membership masks.  It uses one guard bit per lane so
subtraction cannot borrow across neighbouring lanes.  Technology earns no
semantic privilege: callers can compare the SWAR masks against the scalar
masks and discard the candidate if it is not faster end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns, process_time_ns
from typing import Iterable, Mapping, Sequence

from src.pnf.fibre_local_numeric import (
    FibreLayoutError,
    NarrowIntColumn,
    PackedSentenceFibre,
)
from src.pnf.numeric_operator_composition import OperatorLexicon

_MODAL_NAMES = ("must", "shall", "may")
_NEGATION_NAMES = ("not", "never")
_CONDITION_NAMES = ("if", "when", "provided", "providing")
_EXCEPTION_NAMES = ("unless", "except", "excluding")
_TRANSITION_NAMES = ("commence", "begin", "repeal", "amend", "cease")
_AUX_DEPENDENCIES = ("aux", "auxpass")
_MARKER_DEPENDENCIES = ("mark", "prep", "advmod")
_SUBJECT_DEPENDENCIES = ("nsubj", "nsubjpass", "csubj")
_OBJECT_DEPENDENCIES = ("obj", "dobj", "pobj", "attr", "oprd")
_VERB_POS = ("VERB", "AUX")


def _ids(mapping: Mapping[str, int], names: Iterable[str]) -> frozenset[int]:
    return frozenset(int(mapping[name]) for name in names)


def _scalar_membership_mask(values: Sequence[int], accepted: frozenset[int]) -> int:
    mask = 0
    for ordinal, value in enumerate(values):
        if int(value) in accepted:
            mask |= 1 << ordinal
    return mask


def mask_ordinals(mask: int, token_count: int) -> tuple[int, ...]:
    if mask < 0:
        raise ValueError("mask must be non-negative")
    return tuple(ordinal for ordinal in range(token_count) if mask & (1 << ordinal))


@dataclass(frozen=True, slots=True)
class PackedLocalTopology:
    """Dependency topology expressed only in sentence-local ordinals."""

    head_ordinals: tuple[int, ...]
    children_by_head: tuple[tuple[int, ...], ...]

    def children(self, head_ordinal: int) -> tuple[int, ...]:
        if not 0 <= head_ordinal < len(self.children_by_head):
            raise FibreLayoutError("head ordinal is outside the packed fibre")
        return self.children_by_head[head_ordinal]


@dataclass(frozen=True, slots=True)
class PackedOperatorMasks:
    token_count: int
    modal_aux: int
    negation: int
    condition_marker: int
    exception_marker: int
    transition_predicate: int
    subject_dependency: int
    object_dependency: int

    def ordinals(self, name: str) -> tuple[int, ...]:
        if name not in {
            "modal_aux",
            "negation",
            "condition_marker",
            "exception_marker",
            "transition_predicate",
            "subject_dependency",
            "object_dependency",
        }:
            raise KeyError(name)
        return mask_ordinals(int(getattr(self, name)), self.token_count)


@dataclass(frozen=True, slots=True)
class PackedSentenceOperatorKernel:
    masks: PackedOperatorMasks
    topology: PackedLocalTopology


@dataclass(frozen=True, slots=True)
class GuardedSwarColumn:
    """Guard-separated fixed-width lanes packed into Python integer words.

    Each data lane has one extra high guard bit.  Equality uses guarded
    subtraction; the guard prevents a borrow from crossing into the next lane.
    This is a genuine lane-wise SWAR realization, but not a performance claim.
    Packing and mask extraction costs are included in end-to-end benchmarks.
    """

    width_bits: int
    stride_bits: int
    lanes_per_word: int
    token_count: int
    words: tuple[tuple[int, int], ...]

    @classmethod
    def from_column(cls, column: NarrowIntColumn) -> "GuardedSwarColumn":
        if column.signed:
            raise FibreLayoutError("SWAR membership currently requires unsigned columns")
        width_bits = column.itemsize * 8
        stride_bits = width_bits + 1
        lanes_per_word = max(1, 64 // stride_bits)
        words: list[tuple[int, int]] = []
        values = column.values
        limit = 1 << width_bits
        for start in range(0, len(values), lanes_per_word):
            chunk = values[start : start + lanes_per_word]
            word = 0
            for lane, raw in enumerate(chunk):
                value = int(raw)
                if not 0 <= value < limit:
                    raise FibreLayoutError("column value exceeds declared SWAR lane width")
                word |= value << (lane * stride_bits)
            words.append((word, len(chunk)))
        return cls(
            width_bits=width_bits,
            stride_bits=stride_bits,
            lanes_per_word=lanes_per_word,
            token_count=len(values),
            words=tuple(words),
        )

    def membership_mask(self, accepted: Iterable[int]) -> int:
        targets = tuple(sorted({int(value) for value in accepted}))
        if not targets or self.token_count == 0:
            return 0
        lane_limit = 1 << self.width_bits
        if any(value < 0 or value >= lane_limit for value in targets):
            raise FibreLayoutError("SWAR target exceeds declared lane width")

        result = 0
        base_ordinal = 0
        for word, lane_count in self.words:
            ones = 0
            guards = 0
            patterns: list[int] = []
            for lane in range(lane_count):
                shift = lane * self.stride_bits
                ones |= 1 << shift
                guards |= 1 << (shift + self.width_bits)
            for target in targets:
                pattern = 0
                for lane in range(lane_count):
                    pattern |= target << (lane * self.stride_bits)
                patterns.append(pattern)

            zero_guards = 0
            for pattern in patterns:
                xor_word = word ^ pattern
                guarded = xor_word | guards
                after_subtract = guarded - ones
                zero_guards |= (~after_subtract) & guards

            for lane in range(lane_count):
                guard = 1 << (lane * self.stride_bits + self.width_bits)
                if zero_guards & guard:
                    result |= 1 << (base_ordinal + lane)
            base_ordinal += lane_count
        return result


def build_local_topology(fibre: PackedSentenceFibre) -> PackedLocalTopology:
    deltas = fibre.columns["head_delta"].values
    count = fibre.token_count
    children: list[list[int]] = [[] for _ in range(count)]
    heads: list[int] = []
    for ordinal, raw_delta in enumerate(deltas):
        head = ordinal + int(raw_delta)
        if not 0 <= head < count:
            raise FibreLayoutError("packed dependency head escapes sentence fibre")
        heads.append(head)
        children[head].append(ordinal)
    return PackedLocalTopology(
        head_ordinals=tuple(heads),
        children_by_head=tuple(tuple(group) for group in children),
    )


def scalar_operator_masks(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
) -> PackedOperatorMasks:
    lemma = fibre.columns["lemma_id"].values
    dependency = fibre.columns["dependency_id"].values
    pos = fibre.columns["pos_id"].values

    modal = _scalar_membership_mask(lemma, _ids(lexicon.lemma_ids, _MODAL_NAMES))
    auxiliary = _scalar_membership_mask(
        dependency, _ids(lexicon.dependency_ids, _AUX_DEPENDENCIES)
    )
    condition = _scalar_membership_mask(
        lemma, _ids(lexicon.lemma_ids, _CONDITION_NAMES)
    )
    exception = _scalar_membership_mask(
        lemma, _ids(lexicon.lemma_ids, _EXCEPTION_NAMES)
    )
    marker = _scalar_membership_mask(
        dependency, _ids(lexicon.dependency_ids, _MARKER_DEPENDENCIES)
    )
    transition = _scalar_membership_mask(
        lemma, _ids(lexicon.lemma_ids, _TRANSITION_NAMES)
    )
    verb = _scalar_membership_mask(pos, _ids(lexicon.pos_ids, _VERB_POS))

    return PackedOperatorMasks(
        token_count=fibre.token_count,
        modal_aux=modal & auxiliary,
        negation=_scalar_membership_mask(
            lemma, _ids(lexicon.lemma_ids, _NEGATION_NAMES)
        ),
        condition_marker=condition & marker,
        exception_marker=exception & marker,
        transition_predicate=transition & verb,
        subject_dependency=_scalar_membership_mask(
            dependency, _ids(lexicon.dependency_ids, _SUBJECT_DEPENDENCIES)
        ),
        object_dependency=_scalar_membership_mask(
            dependency, _ids(lexicon.dependency_ids, _OBJECT_DEPENDENCIES)
        ),
    )


def swar_operator_masks(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
) -> PackedOperatorMasks:
    lemma = GuardedSwarColumn.from_column(fibre.columns["lemma_id"])
    dependency = GuardedSwarColumn.from_column(fibre.columns["dependency_id"])
    pos = GuardedSwarColumn.from_column(fibre.columns["pos_id"])

    modal = lemma.membership_mask(_ids(lexicon.lemma_ids, _MODAL_NAMES))
    auxiliary = dependency.membership_mask(
        _ids(lexicon.dependency_ids, _AUX_DEPENDENCIES)
    )
    condition = lemma.membership_mask(_ids(lexicon.lemma_ids, _CONDITION_NAMES))
    exception = lemma.membership_mask(_ids(lexicon.lemma_ids, _EXCEPTION_NAMES))
    marker = dependency.membership_mask(
        _ids(lexicon.dependency_ids, _MARKER_DEPENDENCIES)
    )
    transition = lemma.membership_mask(_ids(lexicon.lemma_ids, _TRANSITION_NAMES))
    verb = pos.membership_mask(_ids(lexicon.pos_ids, _VERB_POS))

    return PackedOperatorMasks(
        token_count=fibre.token_count,
        modal_aux=modal & auxiliary,
        negation=lemma.membership_mask(_ids(lexicon.lemma_ids, _NEGATION_NAMES)),
        condition_marker=condition & marker,
        exception_marker=exception & marker,
        transition_predicate=transition & verb,
        subject_dependency=dependency.membership_mask(
            _ids(lexicon.dependency_ids, _SUBJECT_DEPENDENCIES)
        ),
        object_dependency=dependency.membership_mask(
            _ids(lexicon.dependency_ids, _OBJECT_DEPENDENCIES)
        ),
    )


def solve_packed_operator_kernel(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    *,
    use_swar: bool = False,
) -> PackedSentenceOperatorKernel:
    masks = (
        swar_operator_masks(fibre, lexicon)
        if use_swar
        else scalar_operator_masks(fibre, lexicon)
    )
    return PackedSentenceOperatorKernel(
        masks=masks,
        topology=build_local_topology(fibre),
    )


@dataclass(frozen=True, slots=True)
class OperatorKernelTiming:
    repeats: int
    scalar_wall_ns: int
    scalar_cpu_ns: int
    swar_wall_ns: int
    swar_cpu_ns: int
    authority_equal: bool

    @property
    def swar_wall_improvement(self) -> float | None:
        if self.scalar_wall_ns <= 0:
            return None
        return (self.scalar_wall_ns - self.swar_wall_ns) / self.scalar_wall_ns


def benchmark_operator_masks(
    fibres: Sequence[PackedSentenceFibre],
    lexicon: OperatorLexicon,
    *,
    repeats: int = 3,
) -> OperatorKernelTiming:
    """Compare scalar and SWAR mask paths on identical already-packed input."""

    if repeats <= 0:
        raise ValueError("repeats must be positive")

    scalar_wall: list[int] = []
    scalar_cpu: list[int] = []
    swar_wall: list[int] = []
    swar_cpu: list[int] = []
    authority_equal = True

    for _ in range(repeats):
        cpu_start = process_time_ns()
        wall_start = monotonic_ns()
        scalar = tuple(scalar_operator_masks(fibre, lexicon) for fibre in fibres)
        scalar_wall.append(monotonic_ns() - wall_start)
        scalar_cpu.append(process_time_ns() - cpu_start)

        cpu_start = process_time_ns()
        wall_start = monotonic_ns()
        swar = tuple(swar_operator_masks(fibre, lexicon) for fibre in fibres)
        swar_wall.append(monotonic_ns() - wall_start)
        swar_cpu.append(process_time_ns() - cpu_start)
        authority_equal = authority_equal and scalar == swar

    scalar_wall.sort()
    scalar_cpu.sort()
    swar_wall.sort()
    swar_cpu.sort()
    middle = repeats // 2
    return OperatorKernelTiming(
        repeats=repeats,
        scalar_wall_ns=scalar_wall[middle],
        scalar_cpu_ns=scalar_cpu[middle],
        swar_wall_ns=swar_wall[middle],
        swar_cpu_ns=swar_cpu[middle],
        authority_equal=authority_equal,
    )


__all__ = [
    "GuardedSwarColumn",
    "OperatorKernelTiming",
    "PackedLocalTopology",
    "PackedOperatorMasks",
    "PackedSentenceOperatorKernel",
    "benchmark_operator_masks",
    "build_local_topology",
    "mask_ordinals",
    "scalar_operator_masks",
    "solve_packed_operator_kernel",
    "swar_operator_masks",
]
