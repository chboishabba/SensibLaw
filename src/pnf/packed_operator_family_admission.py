"""Fused cheap admission for sparse packed operator-family execution.

The admission pass is deliberately generic: one N-wide scan produces family
candidate masks, and only families with a non-empty mask receive topology and
factor work.  Family builders emit the existing local delta carrier, so this
module adds an execution strategy rather than a second semantic authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.pnf.fibre_local_numeric import PackedSentenceFibre
from src.pnf.numeric_operator_composition import OperatorLexicon
from src.pnf.packed_numeric_composition import (
    PackedLocalFactor,
    PackedLocalObject,
    PackedLocalSlot,
    PackedNormativeDelta,
    compose_packed_normative_delta,
)
from src.pnf.packed_operator_kernel import (
    PackedSentenceOperatorKernel,
    solve_packed_operator_kernel,
)
from src.pnf.numeric_hyperfabric import PromotionEvidence

NORMATIVE = "normative"
CONDITION = "condition"
EXCEPTION = "exception"
TRANSITION = "transition"
FAMILY_NAMES = (NORMATIVE, CONDITION, EXCEPTION, TRANSITION)


@dataclass(frozen=True, slots=True)
class PackedOperatorFamilyAdmissionPlan:
    """Tranche-compiled ids used by the single cheap admission scan."""

    modal_lemma_ids: frozenset[int]
    condition_lemma_ids: frozenset[int]
    exception_lemma_ids: frozenset[int]
    transition_lemma_ids: frozenset[int]
    auxiliary_dependency_ids: frozenset[int]
    marker_dependency_ids: frozenset[int]
    verb_pos_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class PackedOperatorFamilyAdmission:
    candidate_masks: Mapping[str, int]
    token_count: int

    def mask(self, family: str) -> int:
        if family not in FAMILY_NAMES:
            raise KeyError(family)
        return int(self.candidate_masks[family])

    def admitted(self, family: str) -> bool:
        return self.mask(family) != 0

    @property
    def admitted_families(self) -> tuple[str, ...]:
        return tuple(family for family in FAMILY_NAMES if self.admitted(family))


@dataclass(frozen=True, slots=True)
class PackedOperatorFamilyWork:
    admission_checks: int
    admitted_fibre_count: int
    topology_build_count: int
    family_solve_counts: Mapping[str, int]
    factor_build_counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class PackedOperatorFamilyResult:
    admission: PackedOperatorFamilyAdmission
    deltas: Mapping[str, PackedNormativeDelta]
    work: PackedOperatorFamilyWork


def build_operator_family_admission_plan(
    lexicon: OperatorLexicon,
) -> PackedOperatorFamilyAdmissionPlan:
    lemma = lexicon.lemma_ids
    dependency = lexicon.dependency_ids
    pos = lexicon.pos_ids
    return PackedOperatorFamilyAdmissionPlan(
        modal_lemma_ids=frozenset(int(lemma[name]) for name in ("must", "shall", "may")),
        condition_lemma_ids=frozenset(
            int(lemma[name]) for name in ("if", "when", "provided", "providing")
        ),
        exception_lemma_ids=frozenset(
            int(lemma[name]) for name in ("unless", "except", "excluding")
        ),
        transition_lemma_ids=frozenset(
            int(lemma[name])
            for name in ("commence", "begin", "repeal", "amend", "cease")
        ),
        auxiliary_dependency_ids=frozenset(
            int(dependency[name]) for name in ("aux", "auxpass")
        ),
        marker_dependency_ids=frozenset(
            int(dependency[name]) for name in ("mark", "prep", "advmod")
        ),
        verb_pos_ids=frozenset(int(pos[name]) for name in ("VERB", "AUX")),
    )


def operator_family_admission(
    fibre: PackedSentenceFibre,
    plan: PackedOperatorFamilyAdmissionPlan,
) -> PackedOperatorFamilyAdmission:
    """Perform one packed-column scan and return independent family masks."""

    lemmas = fibre.columns["lemma_id"].values
    dependencies = fibre.columns["dependency_id"].values
    positions = fibre.columns["pos_id"].values
    masks = {family: 0 for family in FAMILY_NAMES}
    for ordinal, (lemma, dependency, position) in enumerate(
        zip(lemmas, dependencies, positions)
    ):
        lemma_id = int(lemma)
        dependency_id = int(dependency)
        position_id = int(position)
        bit = 1 << ordinal
        if lemma_id in plan.modal_lemma_ids and dependency_id in plan.auxiliary_dependency_ids:
            masks[NORMATIVE] |= bit
        if lemma_id in plan.condition_lemma_ids and dependency_id in plan.marker_dependency_ids:
            masks[CONDITION] |= bit
        if lemma_id in plan.exception_lemma_ids and dependency_id in plan.marker_dependency_ids:
            masks[EXCEPTION] |= bit
        if lemma_id in plan.transition_lemma_ids and position_id in plan.verb_pos_ids:
            masks[TRANSITION] |= bit
    return PackedOperatorFamilyAdmission(masks, fibre.token_count)


def _evidence() -> PromotionEvidence:
    return PromotionEvidence(
        information_gain=2.0,
        representation_cost=1.0,
        ambiguity_cost=0.5,
        factor_participation=1,
    )


def _object(ordinal: int, lemma_id: int, kind_id: int) -> PackedLocalObject:
    return PackedLocalObject(ordinal, kind_id, lemma_id, _evidence())


def _empty_delta(fibre: PackedSentenceFibre) -> PackedNormativeDelta:
    return PackedNormativeDelta(fibre.token_count, (), ())


def _family_delta(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    kernel: PackedSentenceOperatorKernel,
    family: str,
    mask: int,
) -> PackedNormativeDelta:
    """Build exact local condition/exception/transition factors."""

    if family == NORMATIVE:
        return compose_packed_normative_delta(fibre, lexicon, kernel=kernel)
    lemmas = fibre.columns["lemma_id"].values
    positions = fibre.columns["pos_id"].values
    topology = kernel.topology
    kind_id = int(lexicon.object_kind_ids["parser.role_participant"])
    objects: dict[int, PackedLocalObject] = {}
    factors: list[PackedLocalFactor] = []

    if family in (CONDITION, EXCEPTION):
        is_exception = family == EXCEPTION
        role_id = int(lexicon.role_ids["exception" if is_exception else "condition"])
        factor_type_id = int(
            lexicon.factor_type_ids[
                "semantic.legal_exception" if is_exception else "semantic.legal_condition"
            ]
        )
        predicate_id = int(
            lexicon.predicate_ids[
                "legal.exception_candidate"
                if is_exception
                else "legal.activation_condition_candidate"
            ]
        )
        residual_names = (
            ("exception_attachment_unresolved", "exception_burden_unresolved")
            if is_exception
            else ("condition_attachment_unresolved",)
        )
        for ordinal in range(fibre.token_count):
            if not mask & (1 << ordinal):
                continue
            clause_head = topology.head_ordinals[ordinal]
            host = topology.head_ordinals[clause_head]
            objects.setdefault(clause_head, _object(clause_head, int(lemmas[clause_head]), kind_id))
            slots = [PackedLocalSlot(role_id, clause_head)]
            objects.setdefault(host, _object(host, int(lemmas[host]), kind_id))
            slots.append(PackedLocalSlot(int(lexicon.role_ids["host"]), host))
            factors.append(
                PackedLocalFactor(
                    int(factor_type_id), predicate_id, 0, 0, tuple(slots),
                    (ordinal, clause_head),
                    tuple(sorted(int(lexicon.residual_ids[name]) for name in residual_names)),
                    int(lemmas[clause_head]),
                )
            )
    elif family == TRANSITION:
        transition = {
            int(lexicon.lemma_ids[name]): (prior, nxt, predicate)
            for name, (prior, nxt, predicate) in {
                "commence": (1, 2, "legal.commencement"),
                "begin": (1, 2, "legal.commencement_candidate"),
                "repeal": (2, 3, "legal.repeal"),
                "amend": (4, 5, "legal.amendment"),
                "cease": (2, 1, "legal.cessation"),
            }.items()
        }
        subject_deps = {int(lexicon.dependency_ids[name]) for name in ("nsubj", "nsubjpass", "csubj")}
        object_deps = {int(lexicon.dependency_ids[name]) for name in ("obj", "dobj", "pobj", "attr", "oprd")}
        for ordinal in range(fibre.token_count):
            if not mask & (1 << ordinal):
                continue
            prior, nxt, predicate_name = transition[int(lemmas[ordinal])]
            subject = object_token = None
            for child in topology.children(ordinal):
                dependency = int(fibre.columns["dependency_id"].values[child])
                if subject is None and dependency in subject_deps:
                    subject = child
                if object_token is None and dependency in object_deps:
                    object_token = child
            legal_object = subject if subject is not None else object_token
            objects.setdefault(ordinal, _object(ordinal, int(lemmas[ordinal]), kind_id))
            slots = [PackedLocalSlot(int(lexicon.role_ids["transition"]), ordinal)]
            if legal_object is not None:
                objects.setdefault(legal_object, _object(legal_object, int(lemmas[legal_object]), kind_id))
                slots.append(PackedLocalSlot(int(lexicon.role_ids["legal_object"]), legal_object))
            factors.append(
                PackedLocalFactor(
                    int(lexicon.factor_type_ids["semantic.legal_transition"]),
                    int(lexicon.predicate_ids[predicate_name]), 0, (prior << 8) | nxt,
                    tuple(slots), (ordinal,),
                    tuple(sorted(int(lexicon.residual_ids[name]) for name in (
                        "legal_object_identity_unresolved", "effective_time_unresolved", "jurisdiction_unresolved"
                    ))), int(lemmas[ordinal]),
                )
            )
    else:
        raise KeyError(family)
    return PackedNormativeDelta(
        fibre.token_count,
        tuple(objects[ordinal] for ordinal in sorted(objects)),
        tuple(factors),
    )


def compose_sparse_packed_operator_families(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    *,
    plan: PackedOperatorFamilyAdmissionPlan | None = None,
) -> PackedOperatorFamilyResult:
    """Fuse admission, then solve only the exposed operator families."""

    resolved_plan = plan or build_operator_family_admission_plan(lexicon)
    admission = operator_family_admission(fibre, resolved_plan)
    admitted = admission.admitted_families
    if not admitted:
        empty = {family: _empty_delta(fibre) for family in FAMILY_NAMES}
        return PackedOperatorFamilyResult(
            admission, empty,
            PackedOperatorFamilyWork(1, 0, 0, {family: 0 for family in FAMILY_NAMES}, {family: 0 for family in FAMILY_NAMES}),
        )
    kernel = solve_packed_operator_kernel(fibre, lexicon)
    deltas = {
        family: (_family_delta(fibre, lexicon, kernel, family, admission.mask(family)) if family in admitted else _empty_delta(fibre))
        for family in FAMILY_NAMES
    }
    return PackedOperatorFamilyResult(
        admission,
        deltas,
        PackedOperatorFamilyWork(
            1, 1, 1,
            {family: int(family in admitted) for family in FAMILY_NAMES},
            {family: len(deltas[family].factors) for family in FAMILY_NAMES},
        ),
    )


__all__ = [
    "CONDITION", "EXCEPTION", "FAMILY_NAMES", "NORMATIVE", "TRANSITION",
    "PackedOperatorFamilyAdmission", "PackedOperatorFamilyAdmissionPlan",
    "PackedOperatorFamilyResult", "PackedOperatorFamilyWork",
    "build_operator_family_admission_plan", "compose_sparse_packed_operator_families",
    "operator_family_admission",
]
