"""Sentence->paragraph semantic-delta transport and associative fusion.

B1 deliberately operates only on semantic deltas already emitted by the fused
A2 sentence solver.  It never revisits packed sentence token columns and never
requires durable/global token ids.  Sentence-local token ordinals are lifted
into a paragraph-local address `(child_ordinal, token_ordinal)` and the
transported objects/factors/residual demands are fused by canonical set union.

This is the runtime instance of DASHI.Cognition.PNF.FibreNaturalDeltaTransportExact:
higher fibres consume transported deltas rather than reconstructing lower
carriers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from src.pnf.packed_operator_family_admission import FAMILY_NAMES, PackedOperatorFamilyResult


@dataclass(frozen=True, order=True, slots=True)
class SentenceTokenAddress:
    sentence_ordinal: int
    token_ordinal: int


@dataclass(frozen=True, order=True, slots=True)
class ParagraphTokenAddress:
    child_ordinal: int
    token_ordinal: int


@dataclass(frozen=True, order=True, slots=True)
class SentenceDeltaObject:
    address: SentenceTokenAddress
    object_kind_symbol_id: int
    head_symbol_id: int


@dataclass(frozen=True, order=True, slots=True)
class SentenceDeltaSlot:
    role_symbol_id: int
    address: SentenceTokenAddress
    resolution_state: int
    required: bool


@dataclass(frozen=True, order=True, slots=True)
class SentenceDeltaFactor:
    family: str
    factor_type_symbol_id: int
    predicate_symbol_id: int
    modal_state: int
    temporal_state: int
    slots: tuple[SentenceDeltaSlot, ...]
    support: tuple[SentenceTokenAddress, ...]
    residual_symbol_ids: tuple[int, ...]
    head_lemma_id: int


@dataclass(frozen=True, order=True, slots=True)
class SentenceResidualDemand:
    family: str
    factor: SentenceDeltaFactor
    residual_type_symbol_id: int


@dataclass(frozen=True, slots=True)
class SentenceSemanticDelta:
    sentence_ordinal: int
    objects: tuple[SentenceDeltaObject, ...]
    factors: tuple[SentenceDeltaFactor, ...]
    residuals: tuple[SentenceResidualDemand, ...]


@dataclass(frozen=True, order=True, slots=True)
class ParagraphDeltaObject:
    source_sentence_ordinal: int
    address: ParagraphTokenAddress
    object_kind_symbol_id: int
    head_symbol_id: int


@dataclass(frozen=True, order=True, slots=True)
class ParagraphDeltaSlot:
    role_symbol_id: int
    address: ParagraphTokenAddress
    resolution_state: int
    required: bool


@dataclass(frozen=True, order=True, slots=True)
class ParagraphDeltaFactor:
    source_sentence_ordinal: int
    family: str
    factor_type_symbol_id: int
    predicate_symbol_id: int
    modal_state: int
    temporal_state: int
    slots: tuple[ParagraphDeltaSlot, ...]
    support: tuple[ParagraphTokenAddress, ...]
    residual_symbol_ids: tuple[int, ...]
    head_lemma_id: int


@dataclass(frozen=True, order=True, slots=True)
class ParagraphResidualDemand:
    source_sentence_ordinal: int
    family: str
    factor: ParagraphDeltaFactor
    residual_type_symbol_id: int


@dataclass(frozen=True, slots=True)
class ParagraphSemanticDelta:
    source_sentence_ordinals: tuple[int, ...]
    objects: tuple[ParagraphDeltaObject, ...]
    factors: tuple[ParagraphDeltaFactor, ...]
    residuals: tuple[ParagraphResidualDemand, ...]


@dataclass(frozen=True, slots=True)
class ParagraphTransportWork:
    sentence_delta_count: int
    transported_object_count: int
    transported_factor_count: int
    transported_residual_count: int
    source_token_rescan_count: int = 0


@dataclass(frozen=True, slots=True)
class ParagraphFusionWork:
    input_delta_count: int
    object_inputs: int
    factor_inputs: int
    residual_inputs: int
    source_token_rescan_count: int = 0


@dataclass(frozen=True, slots=True)
class TransportedParagraphDelta:
    delta: ParagraphSemanticDelta
    work: ParagraphTransportWork


@dataclass(frozen=True, slots=True)
class FusedParagraphDelta:
    delta: ParagraphSemanticDelta
    work: ParagraphFusionWork


def sentence_semantic_delta_from_operator_families(
    sentence_ordinal: int,
    result: PackedOperatorFamilyResult,
) -> SentenceSemanticDelta:
    """Flatten one fused A2 result without reading the sentence carrier again."""

    objects: set[SentenceDeltaObject] = set()
    factors: set[SentenceDeltaFactor] = set()
    residuals: set[SentenceResidualDemand] = set()

    for family in FAMILY_NAMES:
        local = result.deltas[family]
        for obj in local.objects:
            objects.add(
                SentenceDeltaObject(
                    SentenceTokenAddress(sentence_ordinal, obj.token_ordinal),
                    int(obj.object_kind_symbol_id),
                    int(obj.head_symbol_id),
                )
            )
        for factor in local.factors:
            sentence_factor = SentenceDeltaFactor(
                family=family,
                factor_type_symbol_id=int(factor.factor_type_symbol_id),
                predicate_symbol_id=int(factor.predicate_symbol_id),
                modal_state=int(factor.modal_state),
                temporal_state=int(factor.temporal_state),
                slots=tuple(
                    sorted(
                        SentenceDeltaSlot(
                            role_symbol_id=int(slot.role_symbol_id),
                            address=SentenceTokenAddress(
                                sentence_ordinal, int(slot.source_ordinal)
                            ),
                            resolution_state=int(slot.resolution_state),
                            required=bool(slot.required),
                        )
                        for slot in factor.slots
                    )
                ),
                support=tuple(
                    sorted(
                        SentenceTokenAddress(sentence_ordinal, int(ordinal))
                        for ordinal in factor.support_ordinals
                    )
                ),
                residual_symbol_ids=tuple(
                    sorted({int(value) for value in factor.residual_symbol_ids})
                ),
                head_lemma_id=int(factor.head_lemma_id),
            )
            factors.add(sentence_factor)
            for residual_id in sentence_factor.residual_symbol_ids:
                residuals.add(
                    SentenceResidualDemand(family, sentence_factor, residual_id)
                )

    return SentenceSemanticDelta(
        sentence_ordinal=int(sentence_ordinal),
        objects=tuple(sorted(objects)),
        factors=tuple(sorted(factors)),
        residuals=tuple(sorted(residuals)),
    )


def transport_sentence_delta_to_paragraph(
    delta: SentenceSemanticDelta,
    *,
    child_ordinal: int,
) -> TransportedParagraphDelta:
    """Lift one sentence delta into paragraph-local coordinates.

    Work is proportional only to already-emitted delta members.  No source token
    array, dependency topology, or durable identity is consulted.
    """

    if child_ordinal < 0:
        raise ValueError("child_ordinal must be non-negative")

    def address(token: SentenceTokenAddress) -> ParagraphTokenAddress:
        return ParagraphTokenAddress(child_ordinal, token.token_ordinal)

    objects = tuple(
        sorted(
            ParagraphDeltaObject(
                source_sentence_ordinal=delta.sentence_ordinal,
                address=address(obj.address),
                object_kind_symbol_id=obj.object_kind_symbol_id,
                head_symbol_id=obj.head_symbol_id,
            )
            for obj in delta.objects
        )
    )
    factors: list[ParagraphDeltaFactor] = []
    residuals: list[ParagraphResidualDemand] = []
    for factor in delta.factors:
        transported = ParagraphDeltaFactor(
            source_sentence_ordinal=delta.sentence_ordinal,
            family=factor.family,
            factor_type_symbol_id=factor.factor_type_symbol_id,
            predicate_symbol_id=factor.predicate_symbol_id,
            modal_state=factor.modal_state,
            temporal_state=factor.temporal_state,
            slots=tuple(
                sorted(
                    ParagraphDeltaSlot(
                        role_symbol_id=slot.role_symbol_id,
                        address=address(slot.address),
                        resolution_state=slot.resolution_state,
                        required=slot.required,
                    )
                    for slot in factor.slots
                )
            ),
            support=tuple(sorted(address(item) for item in factor.support)),
            residual_symbol_ids=factor.residual_symbol_ids,
            head_lemma_id=factor.head_lemma_id,
        )
        factors.append(transported)
        residuals.extend(
            ParagraphResidualDemand(
                source_sentence_ordinal=delta.sentence_ordinal,
                family=factor.family,
                factor=transported,
                residual_type_symbol_id=residual_id,
            )
            for residual_id in transported.residual_symbol_ids
        )

    paragraph = ParagraphSemanticDelta(
        source_sentence_ordinals=(delta.sentence_ordinal,),
        objects=tuple(sorted(set(objects))),
        factors=tuple(sorted(set(factors))),
        residuals=tuple(sorted(set(residuals))),
    )
    return TransportedParagraphDelta(
        paragraph,
        ParagraphTransportWork(
            sentence_delta_count=1,
            transported_object_count=len(paragraph.objects),
            transported_factor_count=len(paragraph.factors),
            transported_residual_count=len(paragraph.residuals),
            source_token_rescan_count=0,
        ),
    )


def fuse_paragraph_deltas(
    left: ParagraphSemanticDelta,
    right: ParagraphSemanticDelta,
) -> FusedParagraphDelta:
    """Canonical associative union of transported paragraph-local deltas."""

    fused = ParagraphSemanticDelta(
        source_sentence_ordinals=tuple(
            sorted(set(left.source_sentence_ordinals) | set(right.source_sentence_ordinals))
        ),
        objects=tuple(sorted(set(left.objects) | set(right.objects))),
        factors=tuple(sorted(set(left.factors) | set(right.factors))),
        residuals=tuple(sorted(set(left.residuals) | set(right.residuals))),
    )
    return FusedParagraphDelta(
        fused,
        ParagraphFusionWork(
            input_delta_count=2,
            object_inputs=len(left.objects) + len(right.objects),
            factor_inputs=len(left.factors) + len(right.factors),
            residual_inputs=len(left.residuals) + len(right.residuals),
            source_token_rescan_count=0,
        ),
    )


def fuse_paragraph_sequence(
    deltas: Iterable[ParagraphSemanticDelta],
) -> ParagraphSemanticDelta:
    """Fuse a sequence using the same associative canonical union."""

    current = ParagraphSemanticDelta((), (), (), ())
    for delta in deltas:
        current = fuse_paragraph_deltas(current, delta).delta
    return current


def paragraph_interface_keys(
    delta: ParagraphSemanticDelta,
) -> Mapping[str, frozenset[tuple[int, int]]]:
    """Project the fused delta to reductive object/factor/demand key families.

    These keys match the *shape* consumed by paragraph interface sketches; this
    function does not allocate or claim a PostgreSQL interface id.
    """

    return {
        "object": frozenset(
            (obj.object_kind_symbol_id, obj.head_symbol_id) for obj in delta.objects
        ),
        "factor": frozenset(
            (factor.factor_type_symbol_id, factor.predicate_symbol_id)
            for factor in delta.factors
        ),
        "demand": frozenset(
            (residual.factor.factor_type_symbol_id, residual.residual_type_symbol_id)
            for residual in delta.residuals
        ),
    }


__all__ = [
    "FusedParagraphDelta",
    "ParagraphDeltaFactor",
    "ParagraphDeltaObject",
    "ParagraphDeltaSlot",
    "ParagraphFusionWork",
    "ParagraphResidualDemand",
    "ParagraphSemanticDelta",
    "ParagraphTokenAddress",
    "ParagraphTransportWork",
    "SentenceDeltaFactor",
    "SentenceDeltaObject",
    "SentenceDeltaSlot",
    "SentenceResidualDemand",
    "SentenceSemanticDelta",
    "SentenceTokenAddress",
    "TransportedParagraphDelta",
    "fuse_paragraph_deltas",
    "fuse_paragraph_sequence",
    "paragraph_interface_keys",
    "sentence_semantic_delta_from_operator_families",
    "transport_sentence_delta_to_paragraph",
]
