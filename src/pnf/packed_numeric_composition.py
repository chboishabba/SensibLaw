"""Normative PNF factor construction directly over packed sentence fibres.

The hot path stays fibre-local: it consumes ``PackedSentenceFibre`` plus the
scalar packed operator kernel and emits a semantic delta addressed only by
local token ordinals.  Durable numeric identity is materialized separately at
the publication boundary, where the existing authoritative ordinal->token-id
mapping is already available.

This separation is deliberate:

    packed local solve
      -> local semantic delta
      -> authority-id materialization
      -> existing Numeric* durable records

The local solver performs no SQL, does not unpack token objects, and does not
require corpus-global token ids.  The materializer preserves the current
``numeric_operator_composition`` digest contract exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.pnf.fibre_local_numeric import FibreLayoutError, PackedSentenceFibre
from src.pnf.numeric_hyperfabric import (
    PromotionEvidence,
    RecencyClass,
    ResolutionState,
    TargetKind,
    numeric_digest,
)
from src.pnf.numeric_operator_composition import (
    NumericDemandSpec,
    NumericFactorSpec,
    NumericObjectSpec,
    NumericSlotSpec,
    OperatorLexicon,
)
from src.pnf.packed_operator_kernel import (
    PackedSentenceOperatorKernel,
    solve_packed_operator_kernel,
)

_MODAL = {
    "must": (1, "normative.obligation"),
    "shall": (1, "normative.obligation"),
    "may": (2, "normative.permission_candidate"),
}


@dataclass(frozen=True, slots=True)
class PackedLocalObject:
    token_ordinal: int
    object_kind_symbol_id: int
    head_symbol_id: int
    promotion_evidence: PromotionEvidence


@dataclass(frozen=True, slots=True)
class PackedLocalSlot:
    role_symbol_id: int
    source_ordinal: int
    resolution_state: ResolutionState = ResolutionState.CANDIDATE
    required: bool = True


@dataclass(frozen=True, slots=True)
class PackedLocalFactor:
    factor_type_symbol_id: int
    predicate_symbol_id: int
    modal_state: int
    temporal_state: int
    slots: tuple[PackedLocalSlot, ...]
    support_ordinals: tuple[int, ...]
    residual_symbol_ids: tuple[int, ...]
    head_lemma_id: int
    support_score: float = 1.0


@dataclass(frozen=True, slots=True)
class PackedNormativeDelta:
    """Sentence-local semantic delta before durable authority ids are applied."""

    token_count: int
    objects: tuple[PackedLocalObject, ...]
    factors: tuple[PackedLocalFactor, ...]


@dataclass(frozen=True, slots=True)
class MaterializedNormativeDelta:
    """Current durable Numeric* representation of one packed normative delta."""

    objects: tuple[NumericObjectSpec, ...]
    factors: tuple[NumericFactorSpec, ...]
    demands: tuple[NumericDemandSpec, ...]


def _first_masked_child(
    children: Sequence[int],
    mask: int,
) -> int | None:
    return next((ordinal for ordinal in children if mask & (1 << ordinal)), None)


def compose_packed_normative_delta(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    *,
    kernel: PackedSentenceOperatorKernel | None = None,
) -> PackedNormativeDelta:
    """Construct normative factors directly from packed local columns.

    This corresponds to the normative/modal branch of
    ``compose_numeric_sentence``.  Factor/object identity is not hashed here
    because the current durable digest contract intentionally includes global
    database token ids; hashing belongs to ``materialize_normative_delta``.
    """

    resolved_kernel = kernel or solve_packed_operator_kernel(fibre, lexicon)
    masks = resolved_kernel.masks
    topology = resolved_kernel.topology
    if masks.token_count != fibre.token_count:
        raise FibreLayoutError("packed operator kernel token count mismatch")
    if len(topology.head_ordinals) != fibre.token_count:
        raise FibreLayoutError("packed operator topology token count mismatch")

    lemmas = fibre.columns["lemma_id"].values
    modal_by_lemma_id = {
        int(lexicon.lemma_ids[name]): (
            modal_state,
            int(lexicon.predicate_ids[predicate]),
        )
        for name, (modal_state, predicate) in _MODAL.items()
    }

    object_kind_id = int(lexicon.object_kind_ids["parser.role_participant"])
    factor_type_id = int(lexicon.factor_type_ids["semantic.normative_relation"])
    conduct_role_id = int(lexicon.role_ids["conduct"])
    bearer_role_id = int(lexicon.role_ids["bearer"])
    object_role_id = int(lexicon.role_ids["object"])
    prohibition_id = int(lexicon.predicate_ids["normative.prohibition"])

    common_residual_names = {
        "jurisdiction_unresolved",
        "legal_time_unresolved",
        "normative_scope_unresolved",
    }

    objects: dict[int, PackedLocalObject] = {}
    factors: list[PackedLocalFactor] = []

    for modal_ordinal in masks.ordinals("modal_aux"):
        modal_contract = modal_by_lemma_id.get(int(lemmas[modal_ordinal]))
        if modal_contract is None:
            # The mask is derived from the same lexicon, so this is a fail-closed
            # consistency guard rather than an expected branch.
            raise FibreLayoutError("modal mask contains an unknown modal lemma")

        head_ordinal = topology.head_ordinals[modal_ordinal]
        head_children = topology.children(head_ordinal)
        subject_ordinal = _first_masked_child(
            head_children,
            masks.subject_dependency,
        )
        object_ordinal = _first_masked_child(
            head_children,
            masks.object_dependency,
        )

        negation_ordinal = None
        for candidate_head in (head_ordinal, modal_ordinal):
            negation_ordinal = _first_masked_child(
                topology.children(candidate_head),
                masks.negation,
            )
            if negation_ordinal is not None:
                break

        modality, predicate_id = modal_contract
        modal_state = modality
        if modality == 1 and negation_ordinal is not None:
            modal_state = 3
            predicate_id = prohibition_id

        evidence = PromotionEvidence(
            information_gain=2.0,
            representation_cost=1.0,
            ambiguity_cost=0.5,
            factor_participation=1,
        )
        for ordinal in (head_ordinal, subject_ordinal, object_ordinal):
            if ordinal is None:
                continue
            objects.setdefault(
                ordinal,
                PackedLocalObject(
                    token_ordinal=ordinal,
                    object_kind_symbol_id=object_kind_id,
                    head_symbol_id=int(lemmas[ordinal]),
                    promotion_evidence=evidence,
                ),
            )

        slots = [PackedLocalSlot(conduct_role_id, head_ordinal)]
        if subject_ordinal is not None:
            slots.append(PackedLocalSlot(bearer_role_id, subject_ordinal))
        if object_ordinal is not None:
            slots.append(PackedLocalSlot(object_role_id, object_ordinal))

        residual_names = set(common_residual_names)
        if modality == 2:
            residual_names.add("modal_sense_unresolved")
        if subject_ordinal is None:
            residual_names.add("norm_bearer_unresolved")

        support = {modal_ordinal, head_ordinal}
        if negation_ordinal is not None:
            support.add(negation_ordinal)

        factors.append(
            PackedLocalFactor(
                factor_type_symbol_id=factor_type_id,
                predicate_symbol_id=predicate_id,
                modal_state=modal_state,
                temporal_state=0,
                slots=tuple(slots),
                support_ordinals=tuple(sorted(support)),
                residual_symbol_ids=tuple(
                    sorted(int(lexicon.residual_ids[name]) for name in residual_names)
                ),
                head_lemma_id=int(lemmas[head_ordinal]),
            )
        )

    return PackedNormativeDelta(
        token_count=fibre.token_count,
        objects=tuple(objects[ordinal] for ordinal in sorted(objects)),
        factors=tuple(factors),
    )


def materialize_normative_delta(
    delta: PackedNormativeDelta,
    *,
    region_id: int,
    token_ids_by_ordinal: Sequence[int],
) -> MaterializedNormativeDelta:
    """Apply durable token ids at the authority/publication boundary.

    The resulting objects/factors/demands use the exact digest construction of
    ``numeric_operator_composition``.  The ordinal map is authority input; this
    function never guesses or allocates token identity.
    """

    if len(token_ids_by_ordinal) != delta.token_count:
        raise FibreLayoutError("authority token-id map does not cover the packed fibre")
    token_ids = tuple(int(value) for value in token_ids_by_ordinal)
    if any(value <= 0 for value in token_ids):
        raise FibreLayoutError("authority token ids must be positive")
    if len(set(token_ids)) != len(token_ids):
        raise FibreLayoutError("authority token ids must be unique within the fibre")

    materialized_objects: list[NumericObjectSpec] = []
    for local in delta.objects:
        token_id = token_ids[local.token_ordinal]
        evidence = local.promotion_evidence
        materialized_objects.append(
            NumericObjectSpec(
                object_digest=numeric_digest(
                    region_id,
                    token_id,
                    local.object_kind_symbol_id,
                ),
                source_token_id=token_id,
                object_kind_symbol_id=local.object_kind_symbol_id,
                head_symbol_id=local.head_symbol_id,
                information_gain=evidence.information_gain,
                representation_cost=evidence.representation_cost,
                ambiguity_cost=evidence.ambiguity_cost,
                promotion_evidence=evidence,
            )
        )

    materialized_factors: list[NumericFactorSpec] = []
    materialized_demands: list[NumericDemandSpec] = []
    for local in delta.factors:
        slots = tuple(
            sorted(
                (
                    NumericSlotSpec(
                        role_symbol_id=slot.role_symbol_id,
                        source_token_id=token_ids[slot.source_ordinal],
                        resolution_state=slot.resolution_state,
                        required=slot.required,
                    )
                    for slot in local.slots
                ),
                key=lambda row: (row.role_symbol_id, row.source_token_id),
            )
        )
        support = tuple(
            sorted({token_ids[ordinal] for ordinal in local.support_ordinals})
        )
        residuals = tuple(sorted(set(local.residual_symbol_ids)))
        factor_digest = numeric_digest(
            region_id,
            local.factor_type_symbol_id,
            local.predicate_symbol_id,
            local.modal_state,
            local.temporal_state,
            tuple(
                (
                    slot.role_symbol_id,
                    slot.source_token_id,
                    int(slot.resolution_state),
                    slot.required,
                )
                for slot in slots
            ),
            support,
            residuals,
        )
        factor = NumericFactorSpec(
            factor_digest=factor_digest,
            factor_type_symbol_id=local.factor_type_symbol_id,
            predicate_symbol_id=local.predicate_symbol_id,
            modal_state=local.modal_state,
            temporal_state=local.temporal_state,
            slots=slots,
            support_token_ids=support,
            residual_symbol_ids=residuals,
            support_score=local.support_score,
        )
        materialized_factors.append(factor)
        materialized_demands.extend(
            NumericDemandSpec(
                demand_digest=numeric_digest(
                    region_id,
                    factor.factor_digest,
                    residual_id,
                    local.head_lemma_id or 0,
                ),
                expected_target_kind=TargetKind.FACTOR,
                expected_factor_type_symbol_id=factor.factor_type_symbol_id,
                expected_object_kind_symbol_id=None,
                lexical_symbol_id=local.head_lemma_id,
                role_symbol_id=None,
                residual_type_symbol_id=residual_id,
                recency_class=RecencyClass.NEAREST_VISIBLE,
            )
            for residual_id in factor.residual_symbol_ids
        )

    unique_factors = {factor.factor_digest: factor for factor in materialized_factors}
    unique_demands = {demand.demand_digest: demand for demand in materialized_demands}
    return MaterializedNormativeDelta(
        objects=tuple(sorted(materialized_objects, key=lambda row: row.object_digest)),
        factors=tuple(sorted(unique_factors.values(), key=lambda row: row.factor_digest)),
        demands=tuple(sorted(unique_demands.values(), key=lambda row: row.demand_digest)),
    )


__all__ = [
    "MaterializedNormativeDelta",
    "PackedLocalFactor",
    "PackedLocalObject",
    "PackedLocalSlot",
    "PackedNormativeDelta",
    "compose_packed_normative_delta",
    "materialize_normative_delta",
]
