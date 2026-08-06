from __future__ import annotations

from src.policy.streaming_spacy_parser_execution import _is_strict_strategy


def test_postgresql_exact_strategies_select_typed_parser() -> None:
    assert _is_strict_strategy("postgresql-leased-exact-execution:v1")
    assert _is_strict_strategy("postgresql-typed-exact-execution:v2")
    assert _is_strict_strategy("postgresql-future-exact-parser:v7")


def test_compatibility_strategy_does_not_select_typed_parser() -> None:
    assert not _is_strict_strategy("local-compatibility-replay")
    assert not _is_strict_strategy("postgresql-reporting-only")
