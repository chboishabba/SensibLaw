from __future__ import annotations

import inspect
from pathlib import Path

from src.policy import operational_corpus_compilation
from src.policy import postgres_corpus_compilation
from src.policy import streaming_spacy_parser_execution as execution


ROOT = Path(__file__).resolve().parents[2]
STREAMING = ROOT / "src/policy/streaming_spacy_parser_execution.py"


def test_postgres_omitted_strategy_prefers_numeric_production(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert (
        execution._effective_strategy(
            arguments={
                "database_url": "postgresql://example/sensiblaw",
                "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
            },
            supplied_kwargs={},
        )
        == execution.DEFAULT_NUMERIC_PRODUCTION_STRATEGY
    )


def test_explicit_compatibility_strategy_is_authoritative(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert (
        execution._effective_strategy(
            arguments={"database_url": "postgresql://example/sensiblaw"},
            supplied_kwargs={
                "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY
            },
        )
        == execution.COMPATIBILITY_REPLAY_STRATEGY
    )


def test_no_database_retains_compatibility_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", raising=False)

    assert (
        execution._effective_strategy(
            arguments={
                "database_url": None,
                "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
            },
            supplied_kwargs={},
        )
        == execution.COMPATIBILITY_REPLAY_STRATEGY
    )


def test_numeric_production_default_can_be_disabled_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT", "0")

    assert (
        execution._effective_strategy(
            arguments={
                "database_url": "postgresql://example/sensiblaw",
                "execution_strategy_ref": execution.COMPATIBILITY_REPLAY_STRATEGY,
            },
            supplied_kwargs={},
        )
        == execution.COMPATIBILITY_REPLAY_STRATEGY
    )


def test_wrapped_strategy_arguments_are_keyword_only() -> None:
    """The wrapper can distinguish omission from an explicit compatibility request."""

    execution.install_streaming_spacy_parser_execution()
    compile_parameter = inspect.signature(
        operational_corpus_compilation.compile_document_operational
    ).parameters["execution_strategy_ref"]
    persist_parameter = inspect.signature(
        postgres_corpus_compilation.persist_document_compilation
    ).parameters["execution_strategy_ref"]

    assert compile_parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert persist_parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_strict_numeric_path_fails_closed_without_postgres_authority() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    compile_branch = source.split("def compile_wrapper", 1)[1].split(
        "def persist_wrapper", 1
    )[0]
    assert "if not _is_strict_strategy(strategy):" in compile_branch
    assert "return original_compile" in compile_branch
    strict_tail = compile_branch.split("if not _is_strict_strategy(strategy):", 1)[1]
    assert "StrictExecutionError(" in strict_tail
    assert '"postgresql_authority_missing"' in strict_tail
    assert "return original_compile" not in strict_tail.split("database_url =", 1)[1]


def test_strict_numeric_persistence_fails_closed_without_postgres_authority() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    persist_branch = source.split("def persist_wrapper", 1)[1].split(
        "operational.DocumentFibrePolicy.to_dict", 1
    )[0]
    assert "if not _is_strict_strategy(strategy):" in persist_branch
    assert "return original_persist" in persist_branch
    strict_tail = persist_branch.split("if not _is_strict_strategy(strategy):", 1)[1]
    assert "StrictExecutionError(" in strict_tail
    assert '"postgresql_authority_missing"' in strict_tail
    assert "return original_persist" not in strict_tail.split("database_url =", 1)[1]
