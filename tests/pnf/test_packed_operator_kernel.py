from __future__ import annotations

from src.pnf.fibre_local_numeric import (
    NarrowIntColumn,
    SentenceFibreObservation,
    TokenObservation,
    pack_sentence_fibre,
)
from src.pnf.numeric_operator_composition import OperatorLexicon
from src.pnf.packed_operator_kernel import (
    GuardedSwarColumn,
    build_local_topology,
    scalar_operator_masks,
    solve_packed_operator_kernel,
    swar_operator_masks,
)


def _lexicon() -> OperatorLexicon:
    lemma_names = (
        "must",
        "shall",
        "may",
        "not",
        "never",
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
    )
    dependency_names = (
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
    )
    pos_names = ("VERB", "AUX")
    return OperatorLexicon(
        lemma_ids={name: 300 + index for index, name in enumerate(lemma_names)},
        dependency_ids={
            name: 700 + index for index, name in enumerate(dependency_names)
        },
        pos_ids={name: 1000 + index for index, name in enumerate(pos_names)},
        factor_type_ids={},
        predicate_ids={},
        role_ids={},
        residual_ids={},
        object_kind_ids={},
    )


def _token(
    *,
    start: int,
    head: int,
    lemma: int,
    dependency: int,
    pos: int,
) -> TokenObservation:
    return TokenObservation(
        start_char=start,
        end_char=start + 1,
        head_ordinal=head,
        orth_id=lemma,
        lemma_id=lemma,
        pos_id=pos,
        tag_id=1,
        dependency_id=dependency,
        morph_id=0,
    )


def _sample():
    lexicon = _lexicon()
    lemmas = lexicon.lemma_ids
    deps = lexicon.dependency_ids
    pos = lexicon.pos_ids
    observation = SentenceFibreObservation(
        fibre_key=b"packed-operator-kernel",
        sentence_ordinal=0,
        start_char=100,
        end_char=120,
        tokens=(
            _token(
                start=100,
                head=1,
                lemma=lemmas["must"],
                dependency=deps["aux"],
                pos=pos["AUX"],
            ),
            _token(
                start=102,
                head=1,
                lemma=9000,
                dependency=deps["advmod"],
                pos=pos["VERB"],
            ),
            _token(
                start=104,
                head=1,
                lemma=lemmas["not"],
                dependency=deps["advmod"],
                pos=pos["AUX"],
            ),
            _token(
                start=106,
                head=1,
                lemma=9100,
                dependency=deps["nsubj"],
                pos=pos["AUX"],
            ),
            _token(
                start=108,
                head=1,
                lemma=9200,
                dependency=deps["obj"],
                pos=pos["AUX"],
            ),
            _token(
                start=110,
                head=6,
                lemma=lemmas["if"],
                dependency=deps["mark"],
                pos=pos["AUX"],
            ),
            _token(
                start=112,
                head=1,
                lemma=9300,
                dependency=deps["advmod"],
                pos=pos["VERB"],
            ),
            _token(
                start=114,
                head=7,
                lemma=lemmas["amend"],
                dependency=deps["advmod"],
                pos=pos["VERB"],
            ),
        ),
    )
    return pack_sentence_fibre(observation), lexicon


def test_guarded_swar_equality_does_not_borrow_across_byte_lanes() -> None:
    # 0x0100 is the classic false-positive shape for unguarded byte has-zero
    # tricks: the zero low lane must not make the neighbouring 1 lane look zero.
    column = NarrowIntColumn.from_values((0, 1, 0, 255), signed=False)
    assert column.itemsize == 1

    swar = GuardedSwarColumn.from_column(column)

    assert swar.membership_mask({0}) == 0b0101
    assert swar.membership_mask({1}) == 0b0010
    assert swar.membership_mask({255}) == 0b1000


def test_guarded_swar_matches_scalar_membership_at_wider_lane_widths() -> None:
    column = NarrowIntColumn.from_values((1, 300, 65535, 300, 2), signed=False)
    assert column.itemsize == 2
    swar = GuardedSwarColumn.from_column(column)

    assert swar.membership_mask({300}) == 0b01010
    assert swar.membership_mask({1, 65535}) == 0b00101


def test_local_topology_uses_only_ordinal_plus_head_delta() -> None:
    fibre, _ = _sample()

    topology = build_local_topology(fibre)

    assert topology.head_ordinals == (1, 1, 1, 1, 1, 6, 1, 7)
    assert topology.children(1) == (0, 1, 2, 3, 4, 6)
    assert topology.children(6) == (5,)
    assert topology.children(7) == (7,)


def test_scalar_packed_kernel_identifies_reference_operator_classes() -> None:
    fibre, lexicon = _sample()

    masks = scalar_operator_masks(fibre, lexicon)

    assert masks.ordinals("modal_aux") == (0,)
    assert masks.ordinals("negation") == (2,)
    assert masks.ordinals("condition_marker") == (5,)
    assert masks.ordinals("exception_marker") == ()
    assert masks.ordinals("transition_predicate") == (7,)
    assert masks.ordinals("subject_dependency") == (3,)
    assert masks.ordinals("object_dependency") == (4,)


def test_swar_and_scalar_masks_are_exactly_equal() -> None:
    fibre, lexicon = _sample()

    assert swar_operator_masks(fibre, lexicon) == scalar_operator_masks(fibre, lexicon)


def test_complete_kernel_preserves_same_topology_under_scalar_and_swar() -> None:
    fibre, lexicon = _sample()

    scalar = solve_packed_operator_kernel(fibre, lexicon)
    swar = solve_packed_operator_kernel(fibre, lexicon, use_swar=True)

    assert scalar == swar
