from __future__ import annotations

from dataclasses import asdict

from src.pnf.numeric_hyperfabric import SymbolKind, TargetKind
from src.pnf.numeric_operator_composition import (
    NumericToken,
    build_operator_lexicon,
    compose_numeric_sentence,
    operator_symbol_values,
)


def _lexicon() -> tuple[object, dict[tuple[SymbolKind, str], int]]:
    symbols = {
        value: index
        for index, value in enumerate(operator_symbol_values(), start=1)
    }
    return build_operator_lexicon(symbols), symbols


def _contains_text(value: object) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, dict):
        return any(_contains_text(key) or _contains_text(item) for key, item in value.items())
    if isinstance(value, (tuple, list, set)):
        return any(_contains_text(item) for item in value)
    return False


def test_modal_composition_operates_only_on_numeric_observations() -> None:
    lexicon, symbols = _lexicon()
    dependency = lambda name: symbols[(SymbolKind.DEPENDENCY, name)]
    lemma = lambda name: symbols[(SymbolKind.LEMMA, name)]
    arbitrary = 50_000
    tokens = (
        NumericToken(1, arbitrary + 1, arbitrary + 2, arbitrary + 3, arbitrary + 4, arbitrary + 5, 2, None, 0, 3),
        NumericToken(2, arbitrary + 6, arbitrary + 7, arbitrary + 8, arbitrary + 9, dependency("nsubj"), 4, None, 4, 11),
        NumericToken(3, arbitrary + 10, lemma("must"), arbitrary + 11, arbitrary + 12, dependency("aux"), 4, None, 12, 16),
        NumericToken(4, arbitrary + 13, arbitrary + 14, arbitrary + 15, arbitrary + 16, arbitrary + 17, 4, None, 17, 23),
        NumericToken(5, arbitrary + 18, arbitrary + 19, arbitrary + 20, arbitrary + 21, arbitrary + 22, 6, None, 24, 27),
        NumericToken(6, arbitrary + 23, arbitrary + 24, arbitrary + 25, arbitrary + 26, dependency("obj"), 4, None, 28, 34),
    )

    closure = compose_numeric_sentence(region_id=91, tokens=tokens, lexicon=lexicon)

    assert len(closure.factors) == 1
    factor = closure.factors[0]
    assert factor.factor_type_symbol_id == symbols[
        (SymbolKind.FACTOR_TYPE, "semantic.normative_relation")
    ]
    assert factor.predicate_symbol_id == symbols[
        (SymbolKind.PREDICATE, "normative.obligation")
    ]
    assert {slot.source_token_id for slot in factor.slots} == {2, 4, 6}
    assert closure.demands
    assert all(
        demand.expected_target_kind is TargetKind.FACTOR
        for demand in closure.demands
    )
    assert not _contains_text(asdict(closure))
