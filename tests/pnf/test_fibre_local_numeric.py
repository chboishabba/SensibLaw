from __future__ import annotations

import pytest

from src.pnf.fibre_local_numeric import (
    BranchPathAddress,
    BranchStep,
    FibreLayoutError,
    SentenceFibreObservation,
    TokenObservation,
    decode_packed_fibre,
    encode_packed_fibre,
    measure_fibre_layout,
    pack_sentence_fibre,
    unpack_sentence_fibre,
)


def _sample() -> SentenceFibreObservation:
    return SentenceFibreObservation(
        fibre_key=b"sentence-digest",
        sentence_ordinal=7,
        start_char=100,
        end_char=130,
        tokens=(
            TokenObservation(
                start_char=100,
                end_char=104,
                head_ordinal=1,
                orth_id=4,
                lemma_id=4,
                pos_id=1,
                tag_id=2,
                dependency_id=3,
                morph_id=0,
                lemma_origin_id=1,
                pos_origin_id=1,
                tag_origin_id=1,
                dependency_origin_id=1,
            ),
            TokenObservation(
                start_char=105,
                end_char=110,
                head_ordinal=1,
                orth_id=4,
                lemma_id=5,
                pos_id=1,
                tag_id=2,
                dependency_id=4,
                morph_id=0,
                lemma_origin_id=1,
                pos_origin_id=1,
                tag_origin_id=1,
                dependency_origin_id=1,
            ),
            TokenObservation(
                start_char=111,
                end_char=115,
                head_ordinal=1,
                orth_id=9,
                lemma_id=9,
                pos_id=1,
                tag_id=2,
                dependency_id=5,
                morph_id=0,
                lemma_origin_id=1,
                pos_origin_id=1,
                tag_origin_id=1,
                dependency_origin_id=1,
            ),
        ),
    )


def test_fibre_pack_round_trip_preserves_token_owned_observation() -> None:
    observation = _sample()
    packed = pack_sentence_fibre(observation)

    assert unpack_sentence_fibre(packed) == observation
    assert packed.columns["start_offset"].as_tuple() == (0, 5, 11)
    assert packed.columns["length"].as_tuple() == (4, 5, 4)
    assert packed.columns["head_delta"].as_tuple() == (1, 0, -1)
    assert packed.token_address(2).token_ordinal == 2


def test_binary_codec_round_trip_is_exact() -> None:
    observation = _sample()
    packed = pack_sentence_fibre(observation)

    decoded = decode_packed_fibre(encode_packed_fibre(packed))

    assert unpack_sentence_fibre(decoded) == observation


def test_small_local_coordinates_select_narrow_columns() -> None:
    packed = pack_sentence_fibre(_sample())
    measurement = measure_fibre_layout(packed)
    widths = dict(measurement.column_widths)

    assert widths["start_offset"] == 1
    assert widths["length"] == 1
    assert widths["head_delta"] == 1
    assert widths["pos_id"] == 1
    assert measurement.packed_numeric_payload_bytes < (
        measurement.naive_u64_equivalent_bytes
    )


def test_head_must_remain_inside_sentence_fibre() -> None:
    with pytest.raises(FibreLayoutError, match="dependency head escapes sentence fibre"):
        SentenceFibreObservation(
            fibre_key=b"x",
            sentence_ordinal=0,
            start_char=0,
            end_char=5,
            tokens=(
                TokenObservation(
                    start_char=0,
                    end_char=5,
                    head_ordinal=1,
                    orth_id=1,
                    lemma_id=1,
                    pos_id=1,
                    tag_id=1,
                    dependency_id=1,
                    morph_id=0,
                ),
            ),
        )


def test_mixed_radix_branch_address_round_trip() -> None:
    path = BranchPathAddress(
        (
            BranchStep(option_count=3, selected_option=2),
            BranchStep(option_count=5, selected_option=4),
            BranchStep(option_count=2, selected_option=1),
        )
    )

    code = path.mixed_radix_code()

    assert BranchPathAddress.from_mixed_radix((3, 5, 2), code) == path


def test_mixed_radix_rejects_out_of_capacity_code() -> None:
    with pytest.raises(FibreLayoutError, match="exceeds path capacity"):
        BranchPathAddress.from_mixed_radix((2, 2), 4)
