from __future__ import annotations

import pytest

from src.pnf.fibre_local_numeric import (
    FibreLayoutError,
    SentenceFibreObservation,
    TokenObservation,
    pack_sentence_fibre,
)
from src.pnf.numeric_operator_composition import (
    NumericToken,
    OperatorLexicon,
    compose_numeric_sentence,
)
from src.pnf.packed_numeric_composition import (
    compose_packed_normative_delta,
    materialize_normative_delta,
)


def _numbered(names: tuple[str, ...], start: int) -> dict[str, int]:
    return {name: start + index for index, name in enumerate(names)}


def _lexicon() -> OperatorLexicon:
    lemma_ids = _numbered(
        (
            "must",
            "shall",
            "may",
            "if",
            "when",
            "provided",
            "providing",
            "unless",
            "except",
            "excluding",
            "commence",
            "begin",
            "repeal",
            "amend",
            "cease",
            "not",
            "never",
        ),
        100,
    )
    dependency_ids = _numbered(
        (
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
        ),
        300,
    )
    pos_ids = _numbered(("VERB", "AUX"), 500)
    factor_type_ids = _numbered(
        (
            "semantic.normative_relation",
            "semantic.legal_condition",
            "semantic.legal_exception",
            "semantic.legal_transition",
        ),
        700,
    )
    predicate_ids = _numbered(
        (
            "normative.obligation",
            "normative.permission_candidate",
            "normative.prohibition",
            "legal.activation_condition_candidate",
            "legal.exception_candidate",
            "legal.commencement",
            "legal.commencement_candidate",
            "legal.repeal",
            "legal.amendment",
            "legal.cessation",
        ),
        900,
    )
    role_ids = _numbered(
        (
            "conduct",
            "bearer",
            "object",
            "condition",
            "exception",
            "host",
            "transition",
            "legal_object",
        ),
        1200,
    )
    residual_ids = _numbered(
        (
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
        ),
        1500,
    )
    return OperatorLexicon(
        lemma_ids=lemma_ids,
        dependency_ids=dependency_ids,
        pos_ids=pos_ids,
        factor_type_ids=factor_type_ids,
        predicate_ids=predicate_ids,
        role_ids=role_ids,
        residual_ids=residual_ids,
        object_kind_ids={"parser.role_participant": 1800},
    )


def _packed_and_reference_tokens(
    *,
    modal_name: str = "must",
    include_negation: bool = True,
    include_subject: bool = True,
):
    lexicon = _lexicon()
    lemma = lexicon.lemma_ids
    dep = lexicon.dependency_ids
    pos = lexicon.pos_ids

    rows: list[tuple[int, int, int, int, int]] = []
    # (token_id, head_ordinal, lemma_id, dependency_id, pos_id)
    if include_subject:
        rows.append((700, 2, 4001, dep["nsubj"], pos["AUX"]))
    rows.extend(
        (
            (900, 2, lemma[modal_name], dep["aux"], pos["AUX"]),
            (300, 2, 4002, dep["advmod"], pos["VERB"]),
        )
    )
    if include_negation:
        rows.append((100, 2, lemma["not"], dep["advmod"], pos["AUX"]))
    rows.append((500, 2, 4003, dep["obj"], pos["AUX"]))

    # Without a subject, the modal/head ordinals shift left by one. Rewrite the
    # stored local heads explicitly rather than relying on database token-id order.
    if not include_subject:
        rewritten = []
        for token_id, _head, lemma_id, dependency_id, pos_id in rows:
            rewritten.append((token_id, 1, lemma_id, dependency_id, pos_id))
        rows = rewritten

    token_ids = tuple(row[0] for row in rows)
    observations: list[TokenObservation] = []
    numeric_tokens: list[NumericToken] = []
    for ordinal, (token_id, head_ordinal, lemma_id, dependency_id, pos_id) in enumerate(rows):
        start = 100 + ordinal * 2
        head_token_id = token_ids[head_ordinal]
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
        numeric_tokens.append(
            NumericToken(
                token_id=token_id,
                orth_id=lemma_id,
                lemma_id=lemma_id,
                pos_id=pos_id,
                tag_id=1,
                dependency_id=dependency_id,
                head_token_id=head_token_id,
                morph_set_id=None,
                start_char=start,
                end_char=start + 1,
            )
        )

    packed = pack_sentence_fibre(
        SentenceFibreObservation(
            fibre_key=b"normative-parity",
            sentence_ordinal=0,
            start_char=100,
            end_char=100 + len(rows) * 2,
            tokens=tuple(observations),
        )
    )
    return packed, tuple(numeric_tokens), token_ids, lexicon


def test_packed_normative_delta_materializes_exact_reference_prohibition() -> None:
    packed, reference_tokens, token_ids, lexicon = _packed_and_reference_tokens()
    region_id = 77

    local = compose_packed_normative_delta(packed, lexicon)
    materialized = materialize_normative_delta(
        local,
        region_id=region_id,
        token_ids_by_ordinal=token_ids,
    )
    reference = compose_numeric_sentence(
        region_id=region_id,
        tokens=reference_tokens,
        lexicon=lexicon,
    )

    assert materialized.objects == reference.objects
    assert materialized.factors == reference.factors
    assert materialized.demands == reference.demands
    assert len(local.factors) == 1
    assert local.factors[0].modal_state == 3
    assert local.factors[0].support_ordinals == (1, 2, 3)


def test_packed_normative_delta_preserves_permission_and_missing_bearer_residuals() -> None:
    packed, reference_tokens, token_ids, lexicon = _packed_and_reference_tokens(
        modal_name="may",
        include_negation=False,
        include_subject=False,
    )
    region_id = 91

    local = compose_packed_normative_delta(packed, lexicon)
    materialized = materialize_normative_delta(
        local,
        region_id=region_id,
        token_ids_by_ordinal=token_ids,
    )
    reference = compose_numeric_sentence(
        region_id=region_id,
        tokens=reference_tokens,
        lexicon=lexicon,
    )

    assert materialized.objects == reference.objects
    assert materialized.factors == reference.factors
    assert materialized.demands == reference.demands
    factor = local.factors[0]
    assert factor.modal_state == 2
    assert lexicon.residual_ids["modal_sense_unresolved"] in factor.residual_symbol_ids
    assert lexicon.residual_ids["norm_bearer_unresolved"] in factor.residual_symbol_ids


def test_local_delta_contains_ordinals_not_database_token_ids() -> None:
    packed, _reference_tokens, token_ids, lexicon = _packed_and_reference_tokens()

    local = compose_packed_normative_delta(packed, lexicon)

    assert {obj.token_ordinal for obj in local.objects} <= set(range(packed.token_count))
    assert not ({obj.token_ordinal for obj in local.objects} & set(token_ids))
    assert all(
        0 <= slot.source_ordinal < packed.token_count
        for factor in local.factors
        for slot in factor.slots
    )


def test_materialization_rejects_incomplete_or_duplicate_authority_map() -> None:
    packed, _reference_tokens, token_ids, lexicon = _packed_and_reference_tokens()
    local = compose_packed_normative_delta(packed, lexicon)

    with pytest.raises(FibreLayoutError, match="does not cover"):
        materialize_normative_delta(
            local,
            region_id=1,
            token_ids_by_ordinal=token_ids[:-1],
        )

    duplicated = list(token_ids)
    duplicated[-1] = duplicated[0]
    with pytest.raises(FibreLayoutError, match="unique"):
        materialize_normative_delta(
            local,
            region_id=1,
            token_ids_by_ordinal=duplicated,
        )
