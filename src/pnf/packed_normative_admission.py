"""Sparse admission gate for packed normative sentence composition.

This module instantiates DASHI's existing sparse-fibred work principle at the
sentence-local normative projection:

    all packed fibres -> cheap modal admission -> admitted fibres -> topology/solve

A rejected fibre is not semantically empty in general.  It is empty only for
this normative/modal projection; the packed parser evidence remains available
to every other consumer.

The gate never queries PostgreSQL and never requires durable/global token ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.pnf.fibre_local_numeric import PackedSentenceFibre
from src.pnf.numeric_operator_composition import OperatorLexicon
from src.pnf.packed_numeric_composition import (
    PackedNormativeDelta,
    compose_packed_normative_delta,
)

_MODAL_NAMES = ("must", "shall", "may")
_AUX_DEPENDENCIES = ("aux", "auxpass")


@dataclass(frozen=True, slots=True)
class PackedNormativeAdmissionPlan:
    """Lexicon-derived constants compiled once for an execution tranche."""

    modal_lemma_ids: frozenset[int]
    auxiliary_dependency_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class PackedNormativeAdmission:
    """Cheap sentence-local proof witness that normative work may be relevant."""

    candidate_mask: int
    token_count: int

    @property
    def admitted(self) -> bool:
        return self.candidate_mask != 0

    @property
    def candidate_count(self) -> int:
        return self.candidate_mask.bit_count()


@dataclass(frozen=True, slots=True)
class PackedNormativeAdmissionWork:
    """Structural work receipt for one fibre.

    ``admission_checks`` is always one.  ``topology_builds`` is exactly zero for
    rejected fibres and one for admitted fibres.  ``factor_builds`` records the
    semantic factors actually emitted after admission.
    """

    admission_checks: int
    admitted_fibres: int
    topology_builds: int
    factor_builds: int


@dataclass(frozen=True, slots=True)
class PackedNormativeAdmissionResult:
    admission: PackedNormativeAdmission
    delta: PackedNormativeDelta
    work: PackedNormativeAdmissionWork


def build_normative_admission_plan(
    lexicon: OperatorLexicon,
) -> PackedNormativeAdmissionPlan:
    """Compile stable accepted ids once instead of rebuilding sets per fibre."""

    return PackedNormativeAdmissionPlan(
        modal_lemma_ids=frozenset(int(lexicon.lemma_ids[name]) for name in _MODAL_NAMES),
        auxiliary_dependency_ids=frozenset(
            int(lexicon.dependency_ids[name]) for name in _AUX_DEPENDENCIES
        ),
    )


def normative_admission(
    fibre: PackedSentenceFibre,
    plan: PackedNormativeAdmissionPlan,
) -> PackedNormativeAdmission:
    """Return the modal+aux candidate mask without building dependency topology."""

    lemmas = fibre.columns["lemma_id"].values
    dependencies = fibre.columns["dependency_id"].values
    mask = 0
    for ordinal, (lemma_id, dependency_id) in enumerate(zip(lemmas, dependencies)):
        if (
            int(lemma_id) in plan.modal_lemma_ids
            and int(dependency_id) in plan.auxiliary_dependency_ids
        ):
            mask |= 1 << ordinal
    return PackedNormativeAdmission(candidate_mask=mask, token_count=fibre.token_count)


def compose_sparse_packed_normative_delta(
    fibre: PackedSentenceFibre,
    lexicon: OperatorLexicon,
    *,
    plan: PackedNormativeAdmissionPlan | None = None,
) -> PackedNormativeAdmissionResult:
    """Solve the normative projection only after cheap admission succeeds.

    Rejection returns the canonical empty normative delta without constructing
    topology, operator masks, objects, slots, residual sets, or factors.
    Admission delegates to the already parity-tested packed normative composer.
    """

    resolved_plan = plan or build_normative_admission_plan(lexicon)
    admission = normative_admission(fibre, resolved_plan)
    if not admission.admitted:
        delta = PackedNormativeDelta(
            token_count=fibre.token_count,
            objects=(),
            factors=(),
        )
        return PackedNormativeAdmissionResult(
            admission=admission,
            delta=delta,
            work=PackedNormativeAdmissionWork(
                admission_checks=1,
                admitted_fibres=0,
                topology_builds=0,
                factor_builds=0,
            ),
        )

    delta = compose_packed_normative_delta(fibre, lexicon)
    return PackedNormativeAdmissionResult(
        admission=admission,
        delta=delta,
        work=PackedNormativeAdmissionWork(
            admission_checks=1,
            admitted_fibres=1,
            topology_builds=1,
            factor_builds=len(delta.factors),
        ),
    )


__all__ = [
    "PackedNormativeAdmission",
    "PackedNormativeAdmissionPlan",
    "PackedNormativeAdmissionResult",
    "PackedNormativeAdmissionWork",
    "build_normative_admission_plan",
    "compose_sparse_packed_normative_delta",
    "normative_admission",
]
