from __future__ import annotations

from src.pnf.fibre_local_numeric import (
    SentenceFibreObservation,
    TokenObservation,
    pack_sentence_fibre,
)
from src.pnf.numeric_operator_composition import (
    NumericToken,
    OperatorLexicon,
    compose_numeric_sentence,
)
from src.pnf.packed_normative_admission import (
    build_normative_admission_plan,
    compose_sparse_packed_normative_delta,
    normative_admission,
)
from src.pnf.packed_numeric_composition import materialize_normative_delta


def _numbered(names: tuple[str, ...], start: int) -> dict[str, int]:
    return {name: start + index for index, name in enumerate(names)}


def _lexicon() -> OperatorLexicon:
    return OperatorLexicon(
        lemma_ids=_numbered(
            (
                "must", "shall", "may", "if", "when", "provided", "providing",
                "unless", "except", "excluding", "commence", "begin", "repeal",
                "amend", "cease", "not", "never",
            ),
            100,
        ),
        dependency_ids=_numbered(
            (
                "aux", "auxpass", "nsubj", "nsubjpass", "csubj", "obj", "dobj",
                "pobj", "attr", "oprd", "mark", "prep", "advmod",
            ),
            300,
        ),
        pos_ids=_numbered(("VERB", "AUX"), 500),
        factor_type_ids=_numbered(
            (
                "semantic.normative_relation", "semantic.legal_condition",
                "semantic.legal_exception", "semantic.legal_transition",
            ),
            700,
        ),
        predicate_ids=_numbered(
            (
                "normative.obligation", "normative.permission_candidate",
                "normative.prohibition", "legal.activation_condition_candidate",
                "legal.exception_candidate", "legal.commencement",
                "legal.commencement_candidate", "legal.repeal", "legal.amendment",
                "legal.cessation",
            ),
            900,
        ),
        role_ids=_numbered(
            (
                "conduct", "bearer", "object", "condition", "exception", "host",
                "transition", "legal_object",
            ),
            1200,
        ),
        residual_ids=_numbered(
            (
                "jurisdiction_unresolved", "legal_time_unresolved",
                "normative_scope_unresolved", "modal_sense_unresolved",
                "norm_bearer_unresolved", "exception_attachment_unresolved",
                "exception_burden_unresolved", "condition_attachment_unresolved",
                "legal_object_identity_unresolved", "effective_time_unresolved",
            ),
            1500,
        ),
        object_kind_ids={"parser.role_participant": 1800},
    )


def _packed(rows: tuple[tuple[int, int, int, int, int], ...]):
    lexicon = _lexicon()
    token_ids = tuple(row[0] for row in rows)
    observations = []
    reference_tokens = []
    for ordinal, (token_id, head_ordinal, lemma_id, dependency_id, pos_id) in enumerate(rows):
        start = ordinal * 2
        observations.append(
            TokenObservation(
                start_char=start,
                end_char=start + 1,
                head_ordinal=head_ordinal,
                orth_id=lemma_id,
                lemma_id=lemma_id,
                pos_id=pos_id,
                tag_id=1,
                dependency_id=dependency_id,
                morph_id=0,
            )
        )
        reference_tokens.append(
            NumericToken(
                token_id=token_id,
                orth_id=lemma_id,
                lemma_id=lemma_id,
                pos_id=pos_id,
                tag_id=1,
                dependency_id=dependency_id,
                head_token_id=token_ids[head_ordinal],
                morph_set_id=None,
                start_char=start,
                end_char=start + 1,
            )
        )
    fibre = pack_sentence_fibre(
        SentenceFibreObservation(
            fibre_key=b"sparse-normative",
            sentence_ordinal=0,
            start_char=0,
            end_char=len(rows) * 2,
            tokens=tuple(observations),
        )
    )
    return fibre, tuple(reference_tokens), token_ids, lexicon


def _reference_normative(reference, factor_type_id: int):
    factors = tuple(
        factor for factor in reference.factors
        if factor.factor_type_symbol_id == factor_type_id
    )
    participating = {slot.source_token_id for factor in factors for slot in factor.slots}
    objects = tuple(obj for obj in reference.objects if obj.source_token_id in participating)
    demands = tuple(
        demand for demand in reference.demands
        if demand.expected_factor_type_symbol_id == factor_type_id
    )
    return objects, factors, demands


def test_rejected_fibre_skips_topology_and_has_empty_normative_projection() -> None:
    lexicon = _lexicon()
    dep = lexicon.dependency_ids
    pos = lexicon.pos_ids
    fibre, reference_tokens, token_ids, lexicon = _packed(
        (
            (900, 1, 4001, dep["nsubj"], pos["AUX"]),
            (300, 1, 4002, dep["advmod"], pos["VERB"]),
        )
    )
    plan = build_normative_admission_plan(lexicon)

    admission = normative_admission(fibre, plan)
    result = compose_sparse_packed_normative_delta(fibre, lexicon, plan=plan)
    materialized = materialize_normative_delta(
        result.delta,
        region_id=17,
        token_ids_by_ordinal=token_ids,
    )
    reference = compose_numeric_sentence(
        region_id=17,
        tokens=reference_tokens,
        lexicon=lexicon,
    )
    expected = _reference_normative(
        reference,
        lexicon.factor_type_ids["semantic.normative_relation"],
    )

    assert not admission.admitted
    assert result.delta.factors == ()
    assert result.work.admission_checks == 1
    assert result.work.admitted_fibres == 0
    assert result.work.topology_builds == 0
    assert result.work.factor_builds == 0
    assert (materialized.objects, materialized.factors, materialized.demands) == expected


def test_admitted_fibre_builds_topology_once_and_preserves_reference() -> None:
    lexicon = _lexicon()
    lemma = lexicon.lemma_ids
    dep = lexicon.dependency_ids
    pos = lexicon.pos_ids
    fibre, reference_tokens, token_ids, lexicon = _packed(
        (
            (700, 2, 4001, dep["nsubj"], pos["AUX"]),
            (900, 2, lemma["must"], dep["aux"], pos["AUX"]),
            (300, 2, 4002, dep["advmod"], pos["VERB"]),
        )
    )
    plan = build_normative_admission_plan(lexicon)

    result = compose_sparse_packed_normative_delta(fibre, lexicon, plan=plan)
    materialized = materialize_normative_delta(
        result.delta,
        region_id=23,
        token_ids_by_ordinal=token_ids,
    )
    reference = compose_numeric_sentence(
        region_id=23,
        tokens=reference_tokens,
        lexicon=lexicon,
    )
    expected = _reference_normative(
        reference,
        lexicon.factor_type_ids["semantic.normative_relation"],
    )

    assert result.admission.admitted
    assert result.admission.candidate_count == 1
    assert result.work.admission_checks == 1
    assert result.work.admitted_fibres == 1
    assert result.work.topology_builds == 1
    assert result.work.factor_builds == 1
    assert (materialized.objects, materialized.factors, materialized.demands) == expected


def test_modal_lemma_without_aux_dependency_is_rejected() -> None:
    lexicon = _lexicon()
    lemma = lexicon.lemma_ids
    dep = lexicon.dependency_ids
    pos = lexicon.pos_ids
    fibre, _reference_tokens, _token_ids, lexicon = _packed(
        ((900, 0, lemma["must"], dep["advmod"], pos["AUX"]),)
    )

    result = compose_sparse_packed_normative_delta(
        fibre,
        lexicon,
        plan=build_normative_admission_plan(lexicon),
    )

    assert not result.admission.admitted
    assert result.work.topology_builds == 0
