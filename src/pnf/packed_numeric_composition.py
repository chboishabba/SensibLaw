"""PNF factor construction directly over the packed sentence carrier.

The first displaced factor family is normative modal composition.  Operator
selection and dependency navigation are supplied by the packed operator
kernel; this module only performs the existing factor/residual construction.
Token addresses in this execution result are sentence-local ordinals.  A
publication adapter may translate them to durable identities later.
"""

from __future__ import annotations

from typing import Iterable

from src.pnf.fibre_local_numeric import PackedSentenceFibre
from src.pnf.numeric_hyperfabric import (
    PromotionEvidence,
    RegionMeasure,
    numeric_digest,
)
from src.pnf.numeric_operator_composition import (
    NumericDemandSpec,
    NumericFactorSpec,
    NumericObjectSpec,
    NumericSentenceClosure,
    NumericSlotSpec,
    OperatorLexicon,
    _MODAL,
    _demands,
    _factor,
)
from src.pnf.packed_operator_kernel import (
    PackedSentenceOperatorKernel,
    mask_ordinals,
    solve_packed_operator_kernel,
)


def _packed_object_spec(
    region_id: int,
    token_ordinal: int,
    lemma_id: int,
    lexicon: OperatorLexicon,
) -> NumericObjectSpec:
    kind_id = lexicon.object_kind_ids["parser.role_participant"]
    evidence = PromotionEvidence(
        information_gain=2.0,
        representation_cost=1.0,
        ambiguity_cost=0.5,
        factor_participation=1,
    )
    return NumericObjectSpec(
        object_digest=numeric_digest(region_id, token_ordinal, kind_id),
        source_token_id=token_ordinal,
        object_kind_symbol_id=kind_id,
        head_symbol_id=lemma_id,
        information_gain=evidence.information_gain,
        representation_cost=evidence.representation_cost,
        ambiguity_cost=evidence.ambiguity_cost,
        promotion_evidence=evidence,
    )


def _first_child(
    children: Iterable[int],
    dependencies: tuple[int, ...],
    accepted: frozenset[int],
) -> int | None:
    return next(
        (ordinal for ordinal in children if dependencies[ordinal] in accepted),
        None,
    )


def compose_packed_modal_sentence(
    *,
    region_id: int,
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    kernel: PackedSentenceOperatorKernel | None = None,
) -> NumericSentenceClosure:
    """Construct normative modal closure from packed columns and local edges.

    This is intentionally limited to the modal family.  Passing a kernel is
    useful for the scalar/SWAR tournament and makes the operator selection
    boundary explicit; when omitted, the scalar reference kernel is used.
    """

    resolved_kernel = kernel or solve_packed_operator_kernel(fibre, lexicon)
    columns = fibre.columns
    lemmas = columns["lemma_id"].as_tuple()
    dependencies = columns["dependency_id"].as_tuple()
    topology = resolved_kernel.topology
    modal_ordinals = mask_ordinals(resolved_kernel.masks.modal_aux, fibre.token_count)
    modal_by_id = {
        lexicon.lemma_ids[name]: (state, lexicon.predicate_ids[predicate])
        for name, (state, predicate) in _MODAL.items()
    }
    aux_dependencies = frozenset(
        lexicon.dependency_ids[name] for name in ("aux", "auxpass")
    )
    subject_dependencies = frozenset(
        lexicon.dependency_ids[name] for name in ("nsubj", "nsubjpass", "csubj")
    )
    object_dependencies = frozenset(
        lexicon.dependency_ids[name] for name in ("obj", "dobj", "pobj", "attr", "oprd")
    )
    negation_ids = frozenset(lexicon.lemma_ids[name] for name in ("not", "never"))

    objects: dict[int, NumericObjectSpec] = {}
    factors: list[NumericFactorSpec] = []
    demands: list[NumericDemandSpec] = []

    for modal_ordinal in modal_ordinals:
        modal_contract = modal_by_id.get(lemmas[modal_ordinal])
        if (
            modal_contract is None
            or dependencies[modal_ordinal] not in aux_dependencies
        ):
            continue
        head_ordinal = topology.head_ordinals[modal_ordinal]
        children = topology.children(head_ordinal)
        subject = _first_child(children, dependencies, subject_dependencies)
        object_token = _first_child(children, dependencies, object_dependencies)
        modality, predicate_id = modal_contract
        negation = next(
            (
                ordinal
                for parent in (head_ordinal, modal_ordinal)
                for ordinal in topology.children(parent)
                if lemmas[ordinal] in negation_ids
            ),
            None,
        )
        modal_state = modality
        if modality == 1 and negation is not None:
            modal_state = 3
            predicate_id = lexicon.predicate_ids["normative.prohibition"]

        slots = [
            NumericSlotSpec(lexicon.role_ids["conduct"], head_ordinal),
        ]
        for ordinal in (head_ordinal, subject, object_token):
            if ordinal is not None:
                objects.setdefault(
                    ordinal,
                    _packed_object_spec(region_id, ordinal, lemmas[ordinal], lexicon),
                )
        if subject is not None:
            slots.append(NumericSlotSpec(lexicon.role_ids["bearer"], subject))
        if object_token is not None:
            slots.append(NumericSlotSpec(lexicon.role_ids["object"], object_token))

        residual_names = {
            "jurisdiction_unresolved",
            "legal_time_unresolved",
            "normative_scope_unresolved",
        }
        if modality == 2:
            residual_names.add("modal_sense_unresolved")
        if subject is None:
            residual_names.add("norm_bearer_unresolved")
        support = {modal_ordinal, head_ordinal}
        if negation is not None:
            support.add(negation)
        factor = _factor(
            region_id=region_id,
            factor_type_id=lexicon.factor_type_ids["semantic.normative_relation"],
            predicate_id=predicate_id,
            modal_state=modal_state,
            temporal_state=0,
            slots=slots,
            support_token_ids=support,
            residual_ids=(lexicon.residual_ids[name] for name in residual_names),
        )
        factors.append(factor)
        demands.extend(
            _demands(
                region_id=region_id,
                factor=factor,
                head_lemma_id=lemmas[head_ordinal],
            )
        )

    unique_factors = {factor.factor_digest: factor for factor in factors}
    unique_demands = {demand.demand_digest: demand for demand in demands}
    edge_count = sum(len(factor.slots) for factor in unique_factors.values())
    return NumericSentenceClosure(
        objects=tuple(sorted(objects.values(), key=lambda row: row.object_digest)),
        factors=tuple(
            sorted(unique_factors.values(), key=lambda row: row.factor_digest)
        ),
        demands=tuple(
            sorted(unique_demands.values(), key=lambda row: row.demand_digest)
        ),
        measure=RegionMeasure(
            node_count=len(objects) + len(unique_factors),
            edge_count=edge_count,
            unresolved_count=len(unique_demands),
            boundary_demand_weight=float(len(unique_demands)),
            encoded_byte_count=(
                fibre.token_count * 8 * 10
                + len(unique_factors) * 32
                + len(unique_demands) * 32
            ),
            # Keep the existing closure measurement contract while this
            # tranche displaces only its first operator family.
            rule_count=3,
            closure_rounds=1,
            promoted_object_count=len(objects),
            interface_cardinality=(
                len(objects) + len(unique_factors) + len(unique_demands)
            ),
        ),
    )


__all__ = ["compose_packed_modal_sentence"]
