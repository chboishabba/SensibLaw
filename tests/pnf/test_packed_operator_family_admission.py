from __future__ import annotations

from src.pnf.fibre_local_numeric import (
    SentenceFibreObservation,
    TokenObservation,
    pack_sentence_fibre,
)
from src.pnf.numeric_operator_composition import NumericToken, compose_numeric_sentence
from src.pnf.packed_numeric_composition import materialize_normative_delta
from src.pnf.packed_operator_family_admission import (
    CONDITION,
    EXCEPTION,
    NORMATIVE,
    TRANSITION,
    build_operator_family_admission_plan,
    compose_sparse_packed_operator_families,
)
from tests.pnf.test_packed_numeric_composition import _lexicon


def _fibre_and_reference():
    lexicon = _lexicon()
    lemma, dependency, pos = lexicon.lemma_ids, lexicon.dependency_ids, lexicon.pos_ids
    rows = (
        (101, 0, 4001, dependency["advmod"], pos["VERB"]),
        (102, 2, lemma["if"], dependency["mark"], pos["AUX"]),
        (103, 0, 4002, dependency["advmod"], pos["VERB"]),
        (104, 0, lemma["commence"], dependency["advmod"], pos["VERB"]),
        (105, 3, 4003, dependency["nsubj"], pos["VERB"]),
        (106, 2, lemma["unless"], dependency["prep"], pos["AUX"]),
        (107, 3, lemma["must"], dependency["aux"], pos["AUX"]),
    )
    token_ids = tuple(row[0] for row in rows)
    observations = tuple(
        TokenObservation(
            start_char=ordinal * 2,
            end_char=ordinal * 2 + 1,
            head_ordinal=head,
            orth_id=lemma_id,
            lemma_id=lemma_id,
            pos_id=pos_id,
            tag_id=1,
            dependency_id=dependency_id,
            morph_id=0,
        )
        for ordinal, (_token, head, lemma_id, dependency_id, pos_id) in enumerate(rows)
    )
    reference = tuple(
        NumericToken(
            token_id=token_id,
            orth_id=lemma_id,
            lemma_id=lemma_id,
            pos_id=pos_id,
            tag_id=1,
            dependency_id=dependency_id,
            head_token_id=token_ids[head],
            morph_set_id=None,
            start_char=ordinal * 2,
            end_char=ordinal * 2 + 1,
        )
        for ordinal, (token_id, head, lemma_id, dependency_id, pos_id) in enumerate(rows)
    )
    fibre = pack_sentence_fibre(
        SentenceFibreObservation(
            fibre_key=b"family-admission",
            sentence_ordinal=0,
            start_char=0,
            end_char=len(rows) * 2,
            tokens=observations,
        )
    )
    return fibre, reference, token_ids, lexicon


def _projection(closure, factor_type_id):
    factors = tuple(row for row in closure.factors if row.factor_type_symbol_id == factor_type_id)
    token_ids = {slot.source_token_id for row in factors for slot in row.slots}
    objects = tuple(row for row in closure.objects if row.source_token_id in token_ids)
    demands = tuple(row for row in closure.demands if row.expected_factor_type_symbol_id == factor_type_id)
    return objects, factors, demands


def test_fused_family_admission_solves_only_exposed_families_with_exact_parity() -> None:
    fibre, reference_tokens, token_ids, lexicon = _fibre_and_reference()
    result = compose_sparse_packed_operator_families(
        fibre,
        lexicon,
        plan=build_operator_family_admission_plan(lexicon),
    )
    reference = compose_numeric_sentence(region_id=41, tokens=reference_tokens, lexicon=lexicon)
    family_types = {
        NORMATIVE: "semantic.normative_relation",
        CONDITION: "semantic.legal_condition",
        EXCEPTION: "semantic.legal_exception",
        TRANSITION: "semantic.legal_transition",
    }

    assert result.admission.admitted_families == (NORMATIVE, CONDITION, EXCEPTION, TRANSITION)
    assert result.work.admission_checks == 1
    assert result.work.topology_build_count == 1
    assert result.work.admitted_fibre_count == 1
    assert result.work.family_solve_counts == {
        NORMATIVE: 1, CONDITION: 1, EXCEPTION: 1, TRANSITION: 1,
    }
    for family, factor_type_name in family_types.items():
        materialized = materialize_normative_delta(
            result.deltas[family], region_id=41, token_ids_by_ordinal=token_ids
        )
        expected = _projection(reference, lexicon.factor_type_ids[factor_type_name])
        assert (materialized.objects, materialized.factors, materialized.demands) == expected


def test_fused_admission_does_not_build_topology_for_unexposed_fibre() -> None:
    fibre, _reference, _token_ids, lexicon = _fibre_and_reference()
    # Replace all semantic lemma ids with an ordinary non-operator id while
    # retaining valid local topology and packed column widths.
    ordinary = tuple(
        TokenObservation(
            start_char=index * 2,
            end_char=index * 2 + 1,
            head_ordinal=0,
            orth_id=4000,
            lemma_id=4000,
            pos_id=lexicon.pos_ids["AUX"],
            tag_id=1,
            dependency_id=lexicon.dependency_ids["advmod"],
            morph_id=0,
        )
        for index in range(fibre.token_count)
    )
    rejected = pack_sentence_fibre(
        SentenceFibreObservation(b"ordinary", 0, 0, fibre.token_count * 2, ordinary)
    )
    result = compose_sparse_packed_operator_families(rejected, lexicon)
    assert result.admission.admitted_families == ()
    assert result.work.topology_build_count == 0
    assert all(not delta.factors for delta in result.deltas.values())
