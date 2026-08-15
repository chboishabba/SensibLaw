from __future__ import annotations

import inspect

from src.policy import operational_corpus_compilation
from src.policy import postgres_corpus_compilation
from src.policy import streaming_spacy_parser_execution as execution


def test_postgres_omitted_strategy_prefers_numeric_production(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert execution._effective_strategy(
        arguments={
            "database_url": "postgresql://example/sensiblaw",
            "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
        },
        supplied_kwargs={},
    ) == execution.DEFAULT_NUMERIC_PRODUCTION_STRATEGY


def test_explicit_compatibility_strategy_is_authoritative(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert execution._effective_strategy(
        arguments={"database_url": "postgresql://example/sensiblaw"},
        supplied_kwargs={
            "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY
        },
    ) == execution.COMPATIBILITY_REPLAY_STRATEGY


def test_no_database_retains_compatibility_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert execution._effective_strategy(
        arguments={
            "database_url": None,
            "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
        },
        supplied_kwargs={},
    ) == execution.COMPATIBILITY_REPLAY_STRATEGY


def test_numeric_production_default_can_be_disabled_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", "0")

    assert execution._effective_strategy(
        arguments={
            "database_url": "postgresql://example/sensiblaw",
            "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
        },
        supplied_kwargs={},
    ) == execution.COMPATIBILITY_REPLAY_STRATEGY


def test_wrapped_strategy_arguments_are_keyword_only() -> None:
    """The wrapper can distinguish omission from an explicit compatibility request."""

    compile_parameter = inspect.signature(
        operational_corpus_compilation.compile_document_operational
    ).parameters["execution_strategy_ref"]
    persist_parameter = inspect.signature(
        postgres_corpus_compilation.persist_document_compilation
    ).parameters["execution_strategy_ref"]

    assert compile_parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert persist_parameter.kind is inspect.Parameter.KEYWORD_ONLY
