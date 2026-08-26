from __future__ import annotations

from src.pnf.numeric_hyperfabric import PromotionEvidence, ResolutionState
from src.pnf.packed_numeric_composition import (
    PackedLocalFactor,
    PackedLocalObject,
    PackedLocalSlot,
    PackedNormativeDelta,
)
from src.pnf.packed_operator_family_admission import (
    CONDITION,
    EXCEPTION,
    FAMILY_NAMES,
    NORMATIVE,
    TRANSITION,
    PackedOperatorFamilyAdmission,
    PackedOperatorFamilyResult,
    PackedOperatorFamilyWork,
)
from src.pnf.sentence_paragraph_delta_transport import (
    ParagraphSemanticDelta,
    ParagraphTokenAddress,
    fuse_paragraph_deltas,
    fuse_paragraph_sequence,
    paragraph_interface_keys,
    sentence_semantic_delta_from_operator_families,
    transport_sentence_delta_to_paragraph,
)


def _evidence() -> PromotionEvidence:
    return PromotionEvidence(
        information_gain=2.0,
        representation_cost=1.0,
        ambiguity_cost=0.5,
        factor_participation=1,
    )


def _result(
    *,
    family: str,
    factor_type: int,
    predicate: int,
    residuals: tuple[int, ...],
    token_count: int = 2,
) -> PackedOperatorFamilyResult:
    obj = PackedLocalObject(
        token_ordinal=0,
        object_kind_symbol_id=40,
        head_symbol_id=50,
        promotion_evidence=_evidence(),
    )
    factor = PackedLocalFactor(
        factor_type_symbol_id=factor_type,
        predicate_symbol_id=predicate,
        modal_state=1 if family == NORMATIVE else 0,
        temporal_state=0,
        slots=(
            PackedLocalSlot(
                role_symbol_id=60,
                source_ordinal=0,
                resolution_state=ResolutionState.CANDIDATE,
                required=True,
            ),
        ),
        support_ordinals=(0,),
        residual_symbol_ids=residuals,
        head_lemma_id=50,
    )
    empty = PackedNormativeDelta(token_count, (), ())
    deltas = {name: empty for name in FAMILY_NAMES}
    deltas[family] = PackedNormativeDelta(token_count, (obj,), (factor,))
    return PackedOperatorFamilyResult(
        admission=PackedOperatorFamilyAdmission(
            {name: (1 if name == family else 0) for name in FAMILY_NAMES},
            token_count,
        ),
        deltas=deltas,
        work=PackedOperatorFamilyWork(
            admission_checks=1,
            admitted_fibre_count=1,
            topology_build_count=1,
            family_solve_counts={name: int(name == family) for name in FAMILY_NAMES},
            factor_build_counts={name: int(name == family) for name in FAMILY_NAMES},
        ),
    )


def _paragraph(
    sentence_ordinal: int,
    child_ordinal: int,
    *,
    family: str,
    factor_type: int,
    predicate: int,
    residuals: tuple[int, ...],
):
    sentence = sentence_semantic_delta_from_operator_families(
        sentence_ordinal,
        _result(
            family=family,
            factor_type=factor_type,
            predicate=predicate,
            residuals=residuals,
        ),
    )
    return transport_sentence_delta_to_paragraph(
        sentence,
        child_ordinal=child_ordinal,
    )


def test_sentence_delta_is_built_only_from_emitted_a2_members() -> None:
    sentence = sentence_semantic_delta_from_operator_families(
        7,
        _result(
            family=NORMATIVE,
            factor_type=100,
            predicate=200,
            residuals=(301, 302),
        ),
    )

    assert sentence.sentence_ordinal == 7
    assert len(sentence.objects) == 1
    assert len(sentence.factors) == 1
    assert len(sentence.residuals) == 2
    assert sentence.objects[0].address.sentence_ordinal == 7
    assert sentence.objects[0].address.token_ordinal == 0


def test_transport_disambiguates_identical_sentence_local_ordinals() -> None:
    first = _paragraph(
        10,
        0,
        family=NORMATIVE,
        factor_type=100,
        predicate=200,
        residuals=(301,),
    )
    second = _paragraph(
        11,
        1,
        family=CONDITION,
        factor_type=101,
        predicate=201,
        residuals=(302,),
    )
    fused = fuse_paragraph_deltas(first.delta, second.delta).delta

    addresses = {obj.address for obj in fused.objects}
    assert ParagraphTokenAddress(0, 0) in addresses
    assert ParagraphTokenAddress(1, 0) in addresses
    assert len(addresses) == 2
    assert fused.source_sentence_ordinals == (10, 11)


def test_transport_work_is_delta_proportional_and_never_rescans_tokens() -> None:
    transported = _paragraph(
        3,
        0,
        family=EXCEPTION,
        factor_type=102,
        predicate=202,
        residuals=(303, 304),
    )

    assert transported.work.sentence_delta_count == 1
    assert transported.work.transported_object_count == 1
    assert transported.work.transported_factor_count == 1
    assert transported.work.transported_residual_count == 2
    assert transported.work.source_token_rescan_count == 0


def test_paragraph_fusion_is_associative_after_canonicalization() -> None:
    a = _paragraph(
        1,
        0,
        family=NORMATIVE,
        factor_type=100,
        predicate=200,
        residuals=(301,),
    ).delta
    b = _paragraph(
        2,
        1,
        family=CONDITION,
        factor_type=101,
        predicate=201,
        residuals=(302,),
    ).delta
    c = _paragraph(
        3,
        2,
        family=TRANSITION,
        factor_type=103,
        predicate=203,
        residuals=(305,),
    ).delta

    left = fuse_paragraph_deltas(fuse_paragraph_deltas(a, b).delta, c).delta
    right = fuse_paragraph_deltas(a, fuse_paragraph_deltas(b, c).delta).delta

    assert left == right
    assert left == fuse_paragraph_sequence((a, b, c))


def test_paragraph_fusion_is_canonical_and_duplicate_safe() -> None:
    a = _paragraph(
        5,
        0,
        family=NORMATIVE,
        factor_type=100,
        predicate=200,
        residuals=(301,),
    ).delta
    fused = fuse_paragraph_deltas(a, a)

    assert fused.delta == a
    assert fused.work.source_token_rescan_count == 0


def test_interface_projection_is_reductive_over_transported_delta() -> None:
    a = _paragraph(
        1,
        0,
        family=NORMATIVE,
        factor_type=100,
        predicate=200,
        residuals=(301,),
    ).delta
    b = _paragraph(
        2,
        1,
        family=CONDITION,
        factor_type=101,
        predicate=201,
        residuals=(302,),
    ).delta
    keys = paragraph_interface_keys(fuse_paragraph_deltas(a, b).delta)

    assert keys["object"] == frozenset({(40, 50)})
    assert keys["factor"] == frozenset({(100, 200), (101, 201)})
    assert keys["demand"] == frozenset({(100, 301), (101, 302)})


def test_empty_sequence_has_canonical_empty_paragraph_delta() -> None:
    assert fuse_paragraph_sequence(()) == ParagraphSemanticDelta((), (), (), ())
