from __future__ import annotations

from dataclasses import dataclass

from src.pnf.direct_sentence_compiler import compile_packed_sentence, source_evidence_id
from src.pnf.packed_sentence_fibre import PackedSentenceFibre, PackedSourceToken


@dataclass(frozen=True)
class _Token:
    local_id: int
    digest: bytes
    lemma: str
    pos: str
    dep: str
    head: int
    start: int
    end: int


def _packed(token: _Token) -> PackedSourceToken:
    return PackedSourceToken(
        local_id=token.local_id,
        evidence_digest=token.digest,
        ordinal=token.local_id,
        start_char=token.start,
        end_char=token.end,
        start_byte=token.start,
        end_byte=token.end,
        orth=token.lemma,
        lemma=token.lemma,
        pos=token.pos,
        tag=token.pos,
        dependency=token.dep,
        head_local_id=token.head,
        morphology=(),
    )


def test_source_evidence_identity_is_stable_and_nonzero() -> None:
    digest = bytes(range(32))
    assert source_evidence_id(digest) == source_evidence_id(digest)
    assert source_evidence_id(digest) > 0


def test_direct_compiler_reuses_sentence_owner_without_database() -> None:
    tokens = (
        _Token(0, b"a" * 32, "party", "NOUN", "nsubj", 2, 0, 5),
        _Token(1, b"b" * 32, "must", "AUX", "aux", 2, 6, 10),
        _Token(2, b"c" * 32, "pay", "VERB", "ROOT", 2, 11, 14),
        _Token(3, b"d" * 32, "debt", "NOUN", "obj", 2, 15, 19),
    )
    fibre = PackedSentenceFibre(
        sentence_digest=b"s" * 32,
        ordinal=0,
        start_char=0,
        end_char=19,
        start_byte=0,
        end_byte=19,
        tokens=tuple(_packed(token) for token in tokens),
    )
    receipt = compile_packed_sentence(region_id=7, fibre=fibre)
    assert receipt.database_crossings == 0
    assert len(receipt.closure.factors) == 1
    assert receipt.closure.factors[0].support_token_ids == tuple(
        sorted((source_evidence_id(b"b" * 32), source_evidence_id(b"c" * 32)))
    )
    assert {digest for _identity, digest in receipt.source_evidence_ids} == {
        b"a" * 32,
        b"b" * 32,
        b"c" * 32,
        b"d" * 32,
    }
