from __future__ import annotations

from dataclasses import replace

import pytest

from src.pnf.direct_sentence_compiler import compile_packed_sentence
from src.pnf.direct_sentence_parity import assert_sentence_parity, observe_sentence_closure
from src.pnf.packed_sentence_fibre import PackedSentenceFibre, PackedSourceToken


def _token(local_id: int, digest: bytes, lemma: str, pos: str, dep: str, head: int, start: int) -> PackedSourceToken:
    return PackedSourceToken(
        local_id=local_id,
        evidence_digest=digest,
        ordinal=local_id,
        start_char=start,
        end_char=start + len(lemma),
        start_byte=start,
        end_byte=start + len(lemma),
        orth=lemma,
        lemma=lemma,
        pos=pos,
        tag=pos,
        dependency=dep,
        head_local_id=head,
        morphology=(),
    )


def _receipt():
    fibre = PackedSentenceFibre(
        sentence_digest=b"s" * 32,
        ordinal=0,
        start_char=0,
        end_char=19,
        start_byte=0,
        end_byte=19,
        tokens=(
            _token(0, b"a" * 32, "party", "NOUN", "nsubj", 2, 0),
            _token(1, b"b" * 32, "must", "AUX", "aux", 2, 6),
            _token(2, b"c" * 32, "pay", "VERB", "ROOT", 2, 11),
            _token(3, b"d" * 32, "debt", "NOUN", "obj", 2, 15),
        ),
    )
    return compile_packed_sentence(region_id=7, fibre=fibre)


def test_parity_ignores_transport_surrogates() -> None:
    receipt = _receipt()
    evidence = dict(receipt.source_evidence_ids)
    symbols = {symbol_id: (kind, text) for kind, text, symbol_id in receipt.symbol_ids}
    direct = observe_sentence_closure(
        receipt.closure,
        evidence_by_address=evidence,
        symbol_by_id=symbols,
    )

    evidence_remap = {old: old + 10_000_000_000 for old in evidence}
    symbol_remap = {old: old + 20_000_000_000 for old in symbols}
    remapped_objects = tuple(
        replace(
            row,
            source_token_id=evidence_remap[row.source_token_id],
            object_kind_symbol_id=symbol_remap[row.object_kind_symbol_id],
            head_symbol_id=symbol_remap[row.head_symbol_id],
            object_digest=b"reference-object-digest" + bytes([index]),
        )
        for index, row in enumerate(receipt.closure.objects)
    )
    remapped_factors = tuple(
        replace(
            row,
            factor_digest=b"reference-factor-digest" + bytes([index]),
            factor_type_symbol_id=symbol_remap[row.factor_type_symbol_id],
            predicate_symbol_id=symbol_remap[row.predicate_symbol_id],
            slots=tuple(
                replace(
                    slot,
                    role_symbol_id=symbol_remap[slot.role_symbol_id],
                    source_token_id=evidence_remap[slot.source_token_id],
                )
                for slot in row.slots
            ),
            support_token_ids=tuple(evidence_remap[value] for value in row.support_token_ids),
            residual_symbol_ids=tuple(symbol_remap[value] for value in row.residual_symbol_ids),
        )
        for index, row in enumerate(receipt.closure.factors)
    )
    remapped_demands = tuple(
        replace(
            row,
            demand_digest=b"reference-demand-digest" + bytes([index]),
            expected_factor_type_symbol_id=(
                symbol_remap[row.expected_factor_type_symbol_id]
                if row.expected_factor_type_symbol_id is not None
                else None
            ),
            expected_object_kind_symbol_id=(
                symbol_remap[row.expected_object_kind_symbol_id]
                if row.expected_object_kind_symbol_id is not None
                else None
            ),
            lexical_symbol_id=(
                symbol_remap[row.lexical_symbol_id]
                if row.lexical_symbol_id is not None
                else None
            ),
            role_symbol_id=(
                symbol_remap[row.role_symbol_id] if row.role_symbol_id is not None else None
            ),
            residual_type_symbol_id=symbol_remap[row.residual_type_symbol_id],
        )
        for index, row in enumerate(receipt.closure.demands)
    )
    reference_closure = replace(
        receipt.closure,
        objects=remapped_objects,
        factors=remapped_factors,
        demands=remapped_demands,
    )
    reference = observe_sentence_closure(
        reference_closure,
        evidence_by_address={evidence_remap[key]: value for key, value in evidence.items()},
        symbol_by_id={symbol_remap[key]: value for key, value in symbols.items()},
    )
    assert_sentence_parity(direct, reference)


def test_parity_fails_closed_on_semantic_difference() -> None:
    receipt = _receipt()
    evidence = dict(receipt.source_evidence_ids)
    symbols = {symbol_id: (kind, text) for kind, text, symbol_id in receipt.symbol_ids}
    direct = observe_sentence_closure(
        receipt.closure,
        evidence_by_address=evidence,
        symbol_by_id=symbols,
    )
    changed_symbol = receipt.closure.objects[0].object_kind_symbol_id
    changed = dict(symbols)
    kind, text = changed[changed_symbol]
    changed[changed_symbol] = (kind, text + ":changed")
    reference = observe_sentence_closure(
        receipt.closure,
        evidence_by_address=evidence,
        symbol_by_id=changed,
    )
    with pytest.raises(RuntimeError, match="publication is forbidden"):
        assert_sentence_parity(direct, reference)


def test_parity_observation_orders_distinct_slot_fibres_structurally() -> None:
    """Factor ordering must not depend on dataclass ordering or local addresses."""

    receipt = _receipt()
    factor = receipt.closure.factors[0]
    assert factor.slots
    replacement_token = next(
        spec.source_token_id
        for spec in receipt.closure.objects
        if spec.source_token_id != factor.slots[0].source_token_id
    )
    alternate = replace(
        factor,
        slots=(
            replace(factor.slots[0], source_token_id=replacement_token),
            *factor.slots[1:],
        ),
    )
    closure = replace(receipt.closure, factors=(alternate, factor))
    observed = observe_sentence_closure(
        closure,
        evidence_by_address=dict(receipt.source_evidence_ids),
        symbol_by_id={
            symbol_id: (kind, text)
            for kind, text, symbol_id in receipt.symbol_ids
        },
    )

    assert len(observed.factors) == 2
    assert observed.factors == tuple(
        sorted(
            observed.factors,
            key=lambda row: row.slots[0].source_evidence_digest,
        )
    )


def test_parity_rejects_missing_source_evidence() -> None:
    receipt = _receipt()
    symbols = {symbol_id: (kind, text) for kind, text, symbol_id in receipt.symbol_ids}
    with pytest.raises(RuntimeError, match="no source evidence"):
        observe_sentence_closure(
            receipt.closure,
            evidence_by_address={},
            symbol_by_id=symbols,
        )
