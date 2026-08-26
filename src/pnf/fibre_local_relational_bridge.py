"""Exact bridge from normalized global parser rows to sentence-local fibres.

The legacy/current PostgreSQL representation is useful authority evidence for
validating the dream carrier.  This bridge does not guess heads or lexical
identity: every global ``head_token_id`` must resolve to exactly one token in the
same sentence, then it is re-addressed by that token's local ordinal.
"""

from __future__ import annotations

from dataclasses import dataclass
from src.pnf.fibre_local_numeric import (
    FibreLayoutError,
    SentenceFibreObservation,
    TokenObservation,
)


@dataclass(frozen=True, slots=True)
class RelationalTokenRow:
    token_id: int
    local_token_ordinal: int
    start_char: int
    end_char: int
    head_token_id: int
    orth_symbol_id: int
    lemma_symbol_id: int
    pos_symbol_id: int
    tag_symbol_id: int
    dependency_symbol_id: int
    morph_set_id: int
    lemma_origin_id: int
    pos_origin_id: int
    tag_origin_id: int
    dependency_origin_id: int


@dataclass(frozen=True, slots=True)
class RelationalSentenceRows:
    fibre_key: bytes
    sentence_ordinal: int
    start_char: int
    end_char: int
    tokens: tuple[RelationalTokenRow, ...]
    # Retained for exact authority joins by read-only adapters.  It is not
    # consumed by the packed local solver.
    sentence_ref: str = ""


def localize_relational_sentence(
    sentence: RelationalSentenceRows,
) -> SentenceFibreObservation:
    """Re-address one exact normalized sentence as a local fibre."""

    ordered = tuple(sorted(sentence.tokens, key=lambda row: row.local_token_ordinal))
    if tuple(row.local_token_ordinal for row in ordered) != tuple(range(len(ordered))):
        raise FibreLayoutError("sentence token ordinals must be contiguous from zero")

    ordinal_by_token_id: dict[int, int] = {}
    for row in ordered:
        previous = ordinal_by_token_id.setdefault(row.token_id, row.local_token_ordinal)
        if previous != row.local_token_ordinal:
            raise FibreLayoutError("duplicate global token id has conflicting ordinal")

    local_tokens: list[TokenObservation] = []
    for row in ordered:
        head_ordinal = ordinal_by_token_id.get(row.head_token_id)
        if head_ordinal is None:
            raise FibreLayoutError(
                "global dependency head is absent from the same sentence fibre"
            )
        local_tokens.append(
            TokenObservation(
                start_char=row.start_char,
                end_char=row.end_char,
                head_ordinal=head_ordinal,
                orth_id=row.orth_symbol_id,
                lemma_id=row.lemma_symbol_id,
                pos_id=row.pos_symbol_id,
                tag_id=row.tag_symbol_id,
                dependency_id=row.dependency_symbol_id,
                morph_id=row.morph_set_id,
                lemma_origin_id=row.lemma_origin_id,
                pos_origin_id=row.pos_origin_id,
                tag_origin_id=row.tag_origin_id,
                dependency_origin_id=row.dependency_origin_id,
            )
        )

    return SentenceFibreObservation(
        fibre_key=bytes(sentence.fibre_key),
        sentence_ordinal=sentence.sentence_ordinal,
        start_char=sentence.start_char,
        end_char=sentence.end_char,
        tokens=tuple(local_tokens),
    )


def relational_head_deltas(sentence: RelationalSentenceRows) -> tuple[int, ...]:
    local = localize_relational_sentence(sentence)
    return tuple(
        token.head_ordinal - ordinal for ordinal, token in enumerate(local.tokens)
    )


__all__ = [
    "RelationalSentenceRows",
    "RelationalTokenRow",
    "localize_relational_sentence",
    "relational_head_deltas",
]
