"""Sentence-local operator composition over numeric parser observations.

All lexical strings are resolved once into ``OperatorLexicon`` ids. The hot
composition loop compares integers, follows numeric dependency edges, and emits
numeric hyperedge specifications plus outward demands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from src.pnf.numeric_hyperfabric import (
    PromotionEvidence,
    RecencyClass,
    RegionMeasure,
    ResolutionState,
    SymbolKind,
    TargetKind,
    numeric_digest,
)


@dataclass(frozen=True, slots=True)
class NumericToken:
    token_id: int
    orth_id: int
    lemma_id: int
    pos_id: int
    tag_id: int
    dependency_id: int
    head_token_id: int
    morph_set_id: int | None
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class OperatorLexicon:
    lemma_ids: Mapping[str, int]
    dependency_ids: Mapping[str, int]
    pos_ids: Mapping[str, int]
    factor_type_ids: Mapping[str, int]
    predicate_ids: Mapping[str, int]
    role_ids: Mapping[str, int]
    residual_ids: Mapping[str, int]
    object_kind_ids: Mapping[str, int]

    @property
    def required_symbol_values(self) -> tuple[tuple[SymbolKind, str], ...]:
        values: list[tuple[SymbolKind, str]] = []
        for name in self.lemma_ids:
            values.append((SymbolKind.LEMMA, name))
        for name in self.dependency_ids:
            values.append((SymbolKind.DEPENDENCY, name))
        for name in self.pos_ids:
            values.append((SymbolKind.POS, name))
        for name in self.factor_type_ids:
            values.append((SymbolKind.FACTOR_TYPE, name))
        for name in self.predicate_ids:
            values.append((SymbolKind.PREDICATE, name))
        for name in self.role_ids:
            values.append((SymbolKind.ROLE, name))
        for name in self.residual_ids:
            values.append((SymbolKind.RESIDUAL_TYPE, name))
        for name in self.object_kind_ids:
            values.append((SymbolKind.OBJECT_KIND, name))
        return tuple(values)


@dataclass(frozen=True, slots=True)
class NumericObjectSpec:
    object_digest: bytes
    source_token_id: int
    object_kind_symbol_id: int
    head_symbol_id: int
    information_gain: float
    representation_cost: float
    ambiguity_cost: float
    promotion_evidence: PromotionEvidence


@dataclass(frozen=True, slots=True)
class NumericSlotSpec:
    role_symbol_id: int
    source_token_id: int
    resolution_state: ResolutionState = ResolutionState.CANDIDATE
    required: bool = True


@dataclass(frozen=True, slots=True)
class NumericFactorSpec:
    factor_digest: bytes
    factor_type_symbol_id: int
    predicate_symbol_id: int
    modal_state: int
    temporal_state: int
    slots: tuple[NumericSlotSpec, ...]
    support_token_ids: tuple[int, ...]
    residual_symbol_ids: tuple[int, ...]
    support_score: float


@dataclass(frozen=True, slots=True)
class NumericDemandSpec:
    demand_digest: bytes
    expected_target_kind: TargetKind
    expected_factor_type_symbol_id: int | None
    expected_object_kind_symbol_id: int | None
    lexical_symbol_id: int | None
    role_symbol_id: int | None
    residual_type_symbol_id: int
    recency_class: RecencyClass
    max_candidates: int = 16


@dataclass(frozen=True, slots=True)
class NumericSentenceClosure:
    objects: tuple[NumericObjectSpec, ...]
    factors: tuple[NumericFactorSpec, ...]
    demands: tuple[NumericDemandSpec, ...]
    measure: RegionMeasure


_MODAL = {
    "must": (1, "normative.obligation"),
    "shall": (1, "normative.obligation"),
    "may": (2, "normative.permission_candidate"),
}
_CONDITIONS = {"if", "when", "provided", "providing"}
_EXCEPTIONS = {"unless", "except", "excluding"}
_TRANSITIONS = {
    "commence": (1, 2, "legal.commencement"),
    "begin": (1, 2, "legal.commencement_candidate"),
    "repeal": (2, 3, "legal.repeal"),
    "amend": (4, 5, "legal.amendment"),
    "cease": (2, 1, "legal.cessation"),
}


def operator_symbol_values() -> tuple[tuple[SymbolKind, str], ...]:
    values: set[tuple[SymbolKind, str]] = set()
    for lemma in (
        set(_MODAL)
        | _CONDITIONS
        | _EXCEPTIONS
        | set(_TRANSITIONS)
        | {"not", "never"}
    ):
        values.add((SymbolKind.LEMMA, lemma))
    for dependency in {
        "aux",
        "auxpass",
        "nsubj",
        "nsubjpass",
        "csubj",
        "obj",
        "dobj",
        "pobj",
        "attr",
        "oprd",
        "mark",
        "prep",
        "advmod",
    }:
        values.add((SymbolKind.DEPENDENCY, dependency))
    for pos in {"VERB", "AUX"}:
        values.add((SymbolKind.POS, pos))
    for factor_type in {
        "semantic.normative_relation",
        "semantic.legal_condition",
        "semantic.legal_exception",
        "semantic.legal_transition",
    }:
        values.add((SymbolKind.FACTOR_TYPE, factor_type))
    for predicate in {
        "normative.obligation",
        "normative.permission_candidate",
        "normative.prohibition",
        "legal.activation_condition_candidate",
        "legal.exception_candidate",
        *{row[2] for row in _TRANSITIONS.values()},
    }:
        values.add((SymbolKind.PREDICATE, predicate))
    for role in {
        "conduct",
        "bearer",
        "object",
        "condition",
        "exception",
        "host",
        "transition",
        "legal_object",
    }:
        values.add((SymbolKind.ROLE, role))
    for residual in {
        "jurisdiction_unresolved",
        "legal_time_unresolved",
        "normative_scope_unresolved",
        "modal_sense_unresolved",
        "norm_bearer_unresolved",
        "exception_attachment_unresolved",
        "exception_burden_unresolved",
        "condition_attachment_unresolved",
        "legal_object_identity_unresolved",
        "effective_time_unresolved",
    }:
        values.add((SymbolKind.RESIDUAL_TYPE, residual))
    values.add((SymbolKind.OBJECT_KIND, "parser.role_participant"))
    return tuple(sorted(values, key=lambda row: (int(row[0]), row[1])))


def build_operator_lexicon(
    symbols: Mapping[tuple[SymbolKind, str], int],
) -> OperatorLexicon:
    def group(kind: SymbolKind) -> dict[str, int]:
        return {
            text: int(symbol_id)
            for (symbol_kind, text), symbol_id in symbols.items()
            if symbol_kind == kind
        }

    lexicon = OperatorLexicon(
        lemma_ids=group(SymbolKind.LEMMA),
        dependency_ids=group(SymbolKind.DEPENDENCY),
        pos_ids=group(SymbolKind.POS),
        factor_type_ids=group(SymbolKind.FACTOR_TYPE),
        predicate_ids=group(SymbolKind.PREDICATE),
        role_ids=group(SymbolKind.ROLE),
        residual_ids=group(SymbolKind.RESIDUAL_TYPE),
        object_kind_ids=group(SymbolKind.OBJECT_KIND),
    )
    required = operator_symbol_values()
    missing = [value for value in required if value not in symbols]
    if missing:
        raise RuntimeError(f"numeric operator lexicon is incomplete: {missing!r}")
    return lexicon


def _subject_and_object(
    children: Sequence[NumericToken],
    lexicon: OperatorLexicon,
) -> tuple[NumericToken | None, NumericToken | None]:
    subject_dependencies = {
        lexicon.dependency_ids[name] for name in ("nsubj", "nsubjpass", "csubj")
    }
    object_dependencies = {
        lexicon.dependency_ids[name]
        for name in ("obj", "dobj", "pobj", "attr", "oprd")
    }
    subject = next(
        (token for token in children if token.dependency_id in subject_dependencies),
        None,
    )
    object_token = next(
        (token for token in children if token.dependency_id in object_dependencies),
        None,
    )
    return subject, object_token


def _object_spec(
    region_id: int,
    token: NumericToken,
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
        object_digest=numeric_digest(region_id, token.token_id, kind_id),
        source_token_id=token.token_id,
        object_kind_symbol_id=kind_id,
        head_symbol_id=token.lemma_id,
        information_gain=evidence.information_gain,
        representation_cost=evidence.representation_cost,
        ambiguity_cost=evidence.ambiguity_cost,
        promotion_evidence=evidence,
    )


def _factor(
    *,
    region_id: int,
    factor_type_id: int,
    predicate_id: int,
    modal_state: int,
    temporal_state: int,
    slots: Iterable[NumericSlotSpec],
    support_token_ids: Iterable[int],
    residual_ids: Iterable[int],
    support_score: float = 1.0,
) -> NumericFactorSpec:
    slot_tuple = tuple(
        sorted(slots, key=lambda row: (row.role_symbol_id, row.source_token_id))
    )
    support = tuple(sorted({int(value) for value in support_token_ids}))
    residuals = tuple(sorted({int(value) for value in residual_ids}))
    digest = numeric_digest(
        region_id,
        factor_type_id,
        predicate_id,
        modal_state,
        temporal_state,
        tuple(
            (
                slot.role_symbol_id,
                slot.source_token_id,
                int(slot.resolution_state),
                slot.required,
            )
            for slot in slot_tuple
        ),
        support,
        residuals,
    )
    return NumericFactorSpec(
        factor_digest=digest,
        factor_type_symbol_id=factor_type_id,
        predicate_symbol_id=predicate_id,
        modal_state=modal_state,
        temporal_state=temporal_state,
        slots=slot_tuple,
        support_token_ids=support,
        residual_symbol_ids=residuals,
        support_score=support_score,
    )


def _demands(
    *,
    region_id: int,
    factor: NumericFactorSpec,
    head_lemma_id: int | None,
) -> tuple[NumericDemandSpec, ...]:
    return tuple(
        NumericDemandSpec(
            demand_digest=numeric_digest(
                region_id,
                factor.factor_digest,
                residual_id,
                head_lemma_id or 0,
            ),
            expected_target_kind=TargetKind.FACTOR,
            expected_factor_type_symbol_id=factor.factor_type_symbol_id,
            expected_object_kind_symbol_id=None,
            lexical_symbol_id=head_lemma_id,
            role_symbol_id=None,
            residual_type_symbol_id=residual_id,
            recency_class=RecencyClass.NEAREST_VISIBLE,
        )
        for residual_id in factor.residual_symbol_ids
    )


def compose_numeric_sentence(
    *,
    region_id: int,
    tokens: Sequence[NumericToken],
    lexicon: OperatorLexicon,
) -> NumericSentenceClosure:
    token_by_id = {token.token_id: token for token in tokens}
    children_by_head: dict[int, list[NumericToken]] = {}
    for token in tokens:
        children_by_head.setdefault(token.head_token_id, []).append(token)
    objects: dict[int, NumericObjectSpec] = {}
    factors: list[NumericFactorSpec] = []
    demands: list[NumericDemandSpec] = []

    aux_dependencies = {
        lexicon.dependency_ids["aux"],
        lexicon.dependency_ids["auxpass"],
    }
    negation_lemmas = {
        lexicon.lemma_ids["not"],
        lexicon.lemma_ids["never"],
    }
    modal_by_lemma_id = {
        lexicon.lemma_ids[name]: (modal_state, lexicon.predicate_ids[predicate])
        for name, (modal_state, predicate) in _MODAL.items()
    }

    for modal in tokens:
        modal_contract = modal_by_lemma_id.get(modal.lemma_id)
        if modal_contract is None or modal.dependency_id not in aux_dependencies:
            continue
        head = token_by_id.get(modal.head_token_id)
        if head is None:
            continue
        subject, object_token = _subject_and_object(
            children_by_head.get(head.token_id, ()),
            lexicon,
        )
        modality, predicate_id = modal_contract
        negation = next(
            (
                token
                for head_id in (head.token_id, modal.token_id)
                for token in children_by_head.get(head_id, ())
                if token.lemma_id in negation_lemmas
            ),
            None,
        )
        modal_state = modality
        if modality == 1 and negation is not None:
            modal_state = 3
            predicate_id = lexicon.predicate_ids["normative.prohibition"]
        slots = [
            NumericSlotSpec(lexicon.role_ids["conduct"], head.token_id),
        ]
        for token in (head, subject, object_token):
            if token is not None:
                objects.setdefault(
                    token.token_id,
                    _object_spec(region_id, token, lexicon),
                )
        if subject is not None:
            slots.append(
                NumericSlotSpec(lexicon.role_ids["bearer"], subject.token_id)
            )
        if object_token is not None:
            slots.append(
                NumericSlotSpec(lexicon.role_ids["object"], object_token.token_id)
            )
        residual_names = {
            "jurisdiction_unresolved",
            "legal_time_unresolved",
            "normative_scope_unresolved",
        }
        if modality == 2:
            residual_names.add("modal_sense_unresolved")
        if subject is None:
            residual_names.add("norm_bearer_unresolved")
        support = {modal.token_id, head.token_id}
        if negation is not None:
            support.add(negation.token_id)
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
                head_lemma_id=head.lemma_id,
            )
        )

    marker_dependencies = {
        lexicon.dependency_ids[name] for name in ("mark", "prep", "advmod")
    }
    condition_ids = {lexicon.lemma_ids[name] for name in _CONDITIONS}
    exception_ids = {lexicon.lemma_ids[name] for name in _EXCEPTIONS}
    for marker in tokens:
        if marker.lemma_id not in condition_ids | exception_ids:
            continue
        if marker.dependency_id not in marker_dependencies:
            continue
        clause_head = token_by_id.get(marker.head_token_id)
        if clause_head is None:
            continue
        host = token_by_id.get(clause_head.head_token_id)
        is_exception = marker.lemma_id in exception_ids
        role_name = "exception" if is_exception else "condition"
        factor_type_name = (
            "semantic.legal_exception"
            if is_exception
            else "semantic.legal_condition"
        )
        predicate_name = (
            "legal.exception_candidate"
            if is_exception
            else "legal.activation_condition_candidate"
        )
        residual_names = (
            ("exception_attachment_unresolved", "exception_burden_unresolved")
            if is_exception
            else ("condition_attachment_unresolved",)
        )
        slots = [
            NumericSlotSpec(lexicon.role_ids[role_name], clause_head.token_id),
        ]
        objects.setdefault(
            clause_head.token_id,
            _object_spec(region_id, clause_head, lexicon),
        )
        if host is not None:
            objects.setdefault(
                host.token_id,
                _object_spec(region_id, host, lexicon),
            )
            slots.append(NumericSlotSpec(lexicon.role_ids["host"], host.token_id))
        factor = _factor(
            region_id=region_id,
            factor_type_id=lexicon.factor_type_ids[factor_type_name],
            predicate_id=lexicon.predicate_ids[predicate_name],
            modal_state=0,
            temporal_state=0,
            slots=slots,
            support_token_ids=(marker.token_id, clause_head.token_id),
            residual_ids=(lexicon.residual_ids[name] for name in residual_names),
        )
        factors.append(factor)
        demands.extend(
            _demands(
                region_id=region_id,
                factor=factor,
                head_lemma_id=clause_head.lemma_id,
            )
        )

    transition_lemma_ids = {
        lexicon.lemma_ids[name]: (prior, next_state, predicate)
        for name, (prior, next_state, predicate) in _TRANSITIONS.items()
    }
    verb_pos = {lexicon.pos_ids["VERB"], lexicon.pos_ids["AUX"]}
    for predicate in tokens:
        transition = transition_lemma_ids.get(predicate.lemma_id)
        if transition is None or predicate.pos_id not in verb_pos:
            continue
        prior_state, next_state, predicate_name = transition
        subject, object_token = _subject_and_object(
            children_by_head.get(predicate.token_id, ()),
            lexicon,
        )
        legal_object = subject or object_token
        slots = [
            NumericSlotSpec(lexicon.role_ids["transition"], predicate.token_id),
        ]
        objects.setdefault(
            predicate.token_id,
            _object_spec(region_id, predicate, lexicon),
        )
        if legal_object is not None:
            objects.setdefault(
                legal_object.token_id,
                _object_spec(region_id, legal_object, lexicon),
            )
            slots.append(
                NumericSlotSpec(
                    lexicon.role_ids["legal_object"],
                    legal_object.token_id,
                )
            )
        factor = _factor(
            region_id=region_id,
            factor_type_id=lexicon.factor_type_ids["semantic.legal_transition"],
            predicate_id=lexicon.predicate_ids[predicate_name],
            modal_state=0,
            temporal_state=(prior_state << 8) | next_state,
            slots=slots,
            support_token_ids=(predicate.token_id,),
            residual_ids=(
                lexicon.residual_ids["legal_object_identity_unresolved"],
                lexicon.residual_ids["effective_time_unresolved"],
                lexicon.residual_ids["jurisdiction_unresolved"],
            ),
        )
        factors.append(factor)
        demands.extend(
            _demands(
                region_id=region_id,
                factor=factor,
                head_lemma_id=predicate.lemma_id,
            )
        )

    unique_factors = {factor.factor_digest: factor for factor in factors}
    unique_demands = {demand.demand_digest: demand for demand in demands}
    edge_count = sum(len(factor.slots) for factor in unique_factors.values())
    measure = RegionMeasure(
        node_count=len(objects) + len(unique_factors),
        edge_count=edge_count,
        unresolved_count=len(unique_demands),
        boundary_demand_weight=float(len(unique_demands)),
        encoded_byte_count=(
            len(tokens) * 8 * 10
            + len(unique_factors) * 32
            + len(unique_demands) * 32
        ),
        rule_count=3,
        closure_rounds=1,
        promoted_object_count=len(objects),
        interface_cardinality=(
            len(objects) + len(unique_factors) + len(unique_demands)
        ),
    )
    return NumericSentenceClosure(
        objects=tuple(sorted(objects.values(), key=lambda row: row.object_digest)),
        factors=tuple(
            sorted(unique_factors.values(), key=lambda row: row.factor_digest)
        ),
        demands=tuple(
            sorted(unique_demands.values(), key=lambda row: row.demand_digest)
        ),
        measure=measure,
    )


__all__ = [
    "NumericDemandSpec",
    "NumericFactorSpec",
    "NumericObjectSpec",
    "NumericSentenceClosure",
    "NumericSlotSpec",
    "NumericToken",
    "OperatorLexicon",
    "build_operator_lexicon",
    "compose_numeric_sentence",
    "operator_symbol_values",
]
