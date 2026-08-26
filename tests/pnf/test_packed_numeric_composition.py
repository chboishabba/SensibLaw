from __future__ import annotations

from src.pnf.fibre_local_numeric import (
    SentenceFibreObservation,
    TokenObservation,
    pack_sentence_fibre,
)
from src.pnf.numeric_operator_composition import (
    NumericToken,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)
from src.pnf.packed_numeric_composition import compose_packed_modal_sentence
from src.pnf.packed_operator_kernel import solve_packed_operator_kernel


def _lexicon():
    symbols = {
        value: index for index, value in enumerate(operator_symbol_values(), start=1)
    }
    return build_operator_lexicon(symbols)


def _inputs():
    lexicon = _lexicon()
    lemma = lexicon.lemma_ids
    dependency = lexicon.dependency_ids
    pos = lexicon.pos_ids
    rows = (
        # must -> enact, with a subject and object; not is attached to enact
        (lemma["must"], dependency["aux"], pos["AUX"], 1),
        (
            80_001,
            dependency["ROOT"] if "ROOT" in dependency else dependency["advmod"],
            pos["VERB"],
            1,
        ),
        (80_002, dependency["nsubj"], pos["VERB"], 1),
        (80_003, dependency["obj"], pos["VERB"], 1),
        (lemma["not"], dependency["advmod"], pos["AUX"], 1),
    )
    observation = SentenceFibreObservation(
        fibre_key=b"packed-modal-composition",
        sentence_ordinal=0,
        start_char=100,
        end_char=130,
        tokens=tuple(
            TokenObservation(
                start_char=100 + ordinal * 2,
                end_char=101 + ordinal * 2,
                head_ordinal=head,
                orth_id=value,
                lemma_id=value,
                pos_id=pos_id,
                tag_id=1,
                dependency_id=dep_id,
                morph_id=0,
            )
            for ordinal, (value, dep_id, pos_id, head) in enumerate(rows)
        ),
    )
    numeric = tuple(
        NumericToken(
            token_id=ordinal,
            orth_id=token.orth_id,
            lemma_id=token.lemma_id,
            pos_id=token.pos_id,
            tag_id=token.tag_id,
            dependency_id=token.dependency_id,
            head_token_id=token.head_ordinal,
            morph_set_id=token.morph_id,
            start_char=token.start_char,
            end_char=token.end_char,
        )
        for ordinal, token in enumerate(observation.tokens)
    )
    return observation, numeric, lexicon


def test_packed_modal_closure_matches_current_local_authority() -> None:
    observation, numeric, lexicon = _inputs()
    packed = pack_sentence_fibre(observation)

    expected = compose_numeric_sentence(
        region_id=19,
        tokens=numeric,
        lexicon=lexicon,
    )
    actual = compose_packed_modal_sentence(
        region_id=19,
        fibre=packed,
        lexicon=lexicon,
    )

    assert actual == expected


def test_packed_modal_swar_path_preserves_factor_closure() -> None:
    observation, _, lexicon = _inputs()
    packed = pack_sentence_fibre(observation)
    scalar = compose_packed_modal_sentence(
        region_id=19,
        fibre=packed,
        lexicon=lexicon,
        kernel=solve_packed_operator_kernel(packed, lexicon),
    )
    swar = compose_packed_modal_sentence(
        region_id=19,
        fibre=packed,
        lexicon=lexicon,
        kernel=solve_packed_operator_kernel(packed, lexicon, use_swar=True),
    )

    assert swar == scalar
