from __future__ import annotations

import pytest

from src.pnf.fibre_local_numeric import FibreLayoutError, pack_sentence_fibre
from src.pnf.fibre_local_relational_bridge import (
    RelationalSentenceRows,
    RelationalTokenRow,
    localize_relational_sentence,
    relational_head_deltas,
)


def _row(
    token_id: int,
    ordinal: int,
    *,
    head_token_id: int,
    start: int,
    end: int,
) -> RelationalTokenRow:
    return RelationalTokenRow(
        token_id=token_id,
        local_token_ordinal=ordinal,
        start_char=start,
        end_char=end,
        head_token_id=head_token_id,
        orth_symbol_id=100 + ordinal,
        lemma_symbol_id=200 + ordinal,
        pos_symbol_id=3,
        tag_symbol_id=4,
        dependency_symbol_id=5 + ordinal,
        morph_set_id=0,
        lemma_origin_id=1,
        pos_origin_id=1,
        tag_origin_id=1,
        dependency_origin_id=1,
    )


def test_global_heads_localize_exactly_to_sentence_ordinals() -> None:
    sentence = RelationalSentenceRows(
        fibre_key=b"fibre",
        sentence_ordinal=4,
        start_char=100,
        end_char=120,
        tokens=(
            _row(9001, 0, head_token_id=9002, start=100, end=104),
            _row(9002, 1, head_token_id=9002, start=105, end=109),
            _row(9003, 2, head_token_id=9002, start=110, end=115),
        ),
    )

    local = localize_relational_sentence(sentence)

    assert tuple(token.head_ordinal for token in local.tokens) == (1, 1, 1)
    assert relational_head_deltas(sentence) == (1, 0, -1)
    assert pack_sentence_fibre(local).columns["head_delta"].as_tuple() == (1, 0, -1)


def test_global_token_magnitude_does_not_enter_local_head_address() -> None:
    sentence = RelationalSentenceRows(
        fibre_key=b"fibre",
        sentence_ordinal=0,
        start_char=0,
        end_char=10,
        tokens=(
            _row(9_000_000_000, 0, head_token_id=9_000_000_001, start=0, end=4),
            _row(9_000_000_001, 1, head_token_id=9_000_000_001, start=5, end=9),
        ),
    )

    packed = pack_sentence_fibre(localize_relational_sentence(sentence))

    assert packed.columns["head_delta"].as_tuple() == (1, 0)
    assert packed.columns["head_delta"].itemsize == 1


def test_cross_sentence_or_missing_head_fails_closed() -> None:
    sentence = RelationalSentenceRows(
        fibre_key=b"fibre",
        sentence_ordinal=0,
        start_char=0,
        end_char=5,
        tokens=(
            _row(1, 0, head_token_id=999, start=0, end=5),
        ),
    )

    with pytest.raises(FibreLayoutError, match="absent from the same sentence fibre"):
        localize_relational_sentence(sentence)


def test_noncontiguous_local_ordinals_fail_closed() -> None:
    sentence = RelationalSentenceRows(
        fibre_key=b"fibre",
        sentence_ordinal=0,
        start_char=0,
        end_char=10,
        tokens=(
            _row(1, 0, head_token_id=1, start=0, end=4),
            _row(2, 2, head_token_id=2, start=5, end=9),
        ),
    )

    with pytest.raises(FibreLayoutError, match="contiguous from zero"):
        localize_relational_sentence(sentence)
