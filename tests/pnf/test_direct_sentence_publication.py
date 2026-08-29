from __future__ import annotations

from src.pnf.direct_sentence_compiler import compile_packed_sentence
from src.pnf.direct_sentence_publication import remap_direct_closure
from src.pnf.packed_sentence_fibre import PackedSentenceFibre, PackedSourceToken


def _token(local_id: int, digest: bytes, lemma: str, pos: str, dep: str, head: int) -> PackedSourceToken:
    return PackedSourceToken(
        local_id=local_id,
        evidence_digest=digest,
        ordinal=local_id,
        start_char=local_id * 5,
        end_char=local_id * 5 + 4,
        start_byte=local_id * 5,
        end_byte=local_id * 5 + 4,
        orth=lemma,
        lemma=lemma,
        pos=pos,
        tag=pos,
        dependency=dep,
        head_local_id=head,
        morphology=(),
    )


def test_publication_remap_preserves_semantic_digests_and_replaces_addresses() -> None:
    fibre = PackedSentenceFibre(
        sentence_digest=b"s" * 32,
        ordinal=0,
        start_char=0,
        end_char=19,
        start_byte=0,
        end_byte=19,
        tokens=(
            _token(0, b"a" * 32, "party", "NOUN", "nsubj", 2),
            _token(1, b"b" * 32, "must", "AUX", "aux", 2),
            _token(2, b"c" * 32, "pay", "VERB", "ROOT", 2),
            _token(3, b"d" * 32, "debt", "NOUN", "obj", 2),
        ),
    )
    direct = compile_packed_sentence(region_id=7, fibre=fibre)
    local_symbols = {local_id for _kind, _text, local_id in direct.symbol_ids}
    local_evidence = {local_id for local_id, _digest in direct.source_evidence_ids}
    symbol_map = {local_id: local_id + 10_000_000 for local_id in local_symbols}
    evidence_map = {local_id: local_id + 20_000_000 for local_id in local_evidence}

    resolved = remap_direct_closure(
        direct.closure,
        symbol_ids=symbol_map,
        evidence_ids=evidence_map,
    )

    assert tuple(spec.object_digest for spec in resolved.objects) == tuple(
        spec.object_digest for spec in direct.closure.objects
    )
    assert tuple(spec.factor_digest for spec in resolved.factors) == tuple(
        spec.factor_digest for spec in direct.closure.factors
    )
    assert tuple(spec.demand_digest for spec in resolved.demands) == tuple(
        spec.demand_digest for spec in direct.closure.demands
    )
    assert all(spec.source_token_id in set(evidence_map.values()) for spec in resolved.objects)
    assert all(
        token_id in set(evidence_map.values())
        for factor in resolved.factors
        for token_id in factor.support_token_ids
    )
    assert all(
        spec.object_kind_symbol_id in set(symbol_map.values())
        and spec.head_symbol_id in set(symbol_map.values())
        for spec in resolved.objects
    )


def test_publication_remap_fails_closed_on_missing_address() -> None:
    fibre = PackedSentenceFibre(
        sentence_digest=b"s" * 32,
        ordinal=0,
        start_char=0,
        end_char=9,
        start_byte=0,
        end_byte=9,
        tokens=(
            _token(0, b"a" * 32, "must", "AUX", "aux", 1),
            _token(1, b"b" * 32, "pay", "VERB", "ROOT", 1),
        ),
    )
    direct = compile_packed_sentence(region_id=7, fibre=fibre)
    symbol_map = {local_id: local_id + 100 for _kind, _text, local_id in direct.symbol_ids}

    try:
        remap_direct_closure(direct.closure, symbol_ids=symbol_map, evidence_ids={})
    except RuntimeError as error:
        assert "evidence mapping" in str(error)
    else:
        raise AssertionError("publication remap must fail closed on missing evidence")
