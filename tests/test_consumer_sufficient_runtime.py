from __future__ import annotations

import pytest

from src.policy.numeric_observation_tape import (
    NumericObservationRow,
    pack_numeric_observation_tape,
    unpack_numeric_observation_tape,
    verify_numeric_observation_tape,
)
from src.policy.world_context import (
    CandidateContextRequirement,
    ContextAxisSymbol,
    ContextPolarity,
    evaluate_context_fit,
)
from src.storage.postgres.numeric_incremental_runtime_store import NumericIncrementalRuntimeStore


def test_context_requirements_require_positive_witness_not_missing_evidence() -> None:
    requirements = (
        CandidateContextRequirement(axis_kind=1, symbol_id=100),
        CandidateContextRequirement(axis_kind=2, symbol_id=200),
    )
    partial = evaluate_context_fit(
        requirements,
        (ContextAxisSymbol(axis_kind=1, symbol_id=100),),
    )
    assert partial.supporting_count == 1
    assert partial.contradicting_count == 0
    assert partial.unknown_count == 1
    assert partial.signed_margin == 1
    assert not partial.requirements_satisfied


def test_explicit_opposite_context_is_negative_evidence() -> None:
    requirement = CandidateContextRequirement(axis_kind=1, symbol_id=100)
    fit = evaluate_context_fit(
        (requirement,),
        (
            ContextAxisSymbol(
                axis_kind=1,
                symbol_id=100,
                polarity=ContextPolarity.CONTRADICTS,
            ),
        ),
    )
    assert fit.supporting_count == 0
    assert fit.contradicting_count == 1
    assert fit.unknown_count == 0
    assert fit.signed_margin == -1
    assert not fit.requirements_satisfied


def test_context_fit_is_axis_typed() -> None:
    fit = evaluate_context_fit(
        (CandidateContextRequirement(axis_kind=1, symbol_id=100),),
        (ContextAxisSymbol(axis_kind=2, symbol_id=100),),
    )
    assert fit.supporting_count == 0
    assert fit.unknown_count == 1


def test_candidate_requirement_rejects_neutral_polarity() -> None:
    with pytest.raises(ValueError, match="positive or negative"):
        CandidateContextRequirement(
            axis_kind=1,
            symbol_id=100,
            polarity=ContextPolarity.NEUTRAL,
        )


def _observation_rows() -> tuple[NumericObservationRow, ...]:
    return (
        NumericObservationRow(
            token_id=1000,
            sentence_id=50,
            local_ordinal=0,
            start_char=0,
            end_char=11,
            orth_symbol_id=10,
            lemma_symbol_id=20,
            pos_symbol_id=30,
            tag_symbol_id=40,
            dependency_symbol_id=50,
            morph_set_id=None,
            head_token_id=1001,
            lemma_origin_id=1,
            pos_origin_id=1,
            tag_origin_id=1,
            dependency_origin_id=1,
        ),
        NumericObservationRow(
            token_id=1001,
            sentence_id=50,
            local_ordinal=1,
            start_char=12,
            end_char=23,
            orth_symbol_id=11,
            lemma_symbol_id=21,
            pos_symbol_id=31,
            tag_symbol_id=41,
            dependency_symbol_id=51,
            morph_set_id=99,
            head_token_id=1001,
            lemma_origin_id=2,
            pos_origin_id=1,
            tag_origin_id=3,
            dependency_origin_id=1,
        ),
        # Deliberately non-monotone imported ids exercise signed delta coding.
        NumericObservationRow(
            token_id=999,
            sentence_id=49,
            local_ordinal=2,
            start_char=24,
            end_char=25,
            orth_symbol_id=1,
            lemma_symbol_id=2,
            pos_symbol_id=None,
            tag_symbol_id=None,
            dependency_symbol_id=None,
            morph_set_id=None,
            head_token_id=999,
            lemma_origin_id=1,
            pos_origin_id=1,
            tag_origin_id=1,
            dependency_origin_id=1,
        ),
    )


def test_numeric_observation_tape_roundtrips_exactly_with_annotation_origins() -> None:
    rows = _observation_rows()
    payload, receipt = pack_numeric_observation_tape(rows)
    assert unpack_numeric_observation_tape(payload) == rows
    verified = verify_numeric_observation_tape(rows, payload)
    assert verified.authority_digest == receipt.authority_digest
    assert verified.packed_digest == receipt.packed_digest
    assert receipt.token_count == len(rows)
    assert receipt.encoded_bytes == len(payload)
    assert receipt.codec_version == 2


def test_numeric_observation_tape_rejects_trailing_or_wrong_bytes() -> None:
    rows = _observation_rows()
    payload, _ = pack_numeric_observation_tape(rows)
    with pytest.raises(ValueError, match="trailing bytes"):
        unpack_numeric_observation_tape(payload + b"\x00")
    mutated = bytearray(payload)
    mutated[-1] ^= 1
    with pytest.raises(ValueError, match="does not reconstruct"):
        verify_numeric_observation_tape(rows, bytes(mutated))


def test_controlled_workload_digest_is_consumer_and_query_relative() -> None:
    authority = b"a" * 32
    a = NumericIncrementalRuntimeStore.controlled_workload_digest(
        authority_digest=authority,
        consumer_ref="consumer:a",
        query_ref="who-was-seen",
    )
    b = NumericIncrementalRuntimeStore.controlled_workload_digest(
        authority_digest=authority,
        consumer_ref="consumer:a",
        query_ref="who-had-telescope",
    )
    c = NumericIncrementalRuntimeStore.controlled_workload_digest(
        authority_digest=authority,
        consumer_ref="consumer:b",
        query_ref="who-was-seen",
    )
    assert len(a) == 32
    assert a != b
    assert a != c
