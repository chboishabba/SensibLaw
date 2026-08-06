from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.policy.streaming_spacy_parser_execution import (
    _is_strict_strategy,
    _scoped_run_ref,
)


def test_postgresql_exact_strategies_select_typed_parser() -> None:
    assert _is_strict_strategy("postgresql-leased-exact-execution:v1")
    assert _is_strict_strategy("postgresql-typed-exact-execution:v2")
    assert _is_strict_strategy("postgresql-future-exact-parser:v7")


def test_compatibility_strategy_does_not_select_typed_parser() -> None:
    assert not _is_strict_strategy("local-compatibility-replay")
    assert not _is_strict_strategy("postgresql-reporting-only")


def test_parser_run_ref_is_stable_and_semantically_scoped() -> None:
    values = {
        "requested_run_ref": "strict:document:1",
        "document_ref": "document:1",
        "content_sha256": "abc",
        "parser_contract_ref": "parser:spacy:v1",
    }
    first = _scoped_run_ref(**values)
    second = _scoped_run_ref(**values)

    assert first == second
    assert first.startswith("typed-spacy-run:")
    assert _scoped_run_ref(**{**values, "content_sha256": "def"}) != first
    assert (
        _scoped_run_ref(
            **{**values, "parser_contract_ref": "parser:spacy:v2"}
        )
        != first
    )
    assert (
        _scoped_run_ref(
            requested_run_ref=first,
            document_ref="document:other",
            content_sha256="different",
            parser_contract_ref="parser:other",
        )
        == first
    )


def test_wrappers_bind_the_real_function_signatures() -> None:
    import src.policy.streaming_spacy_parser_execution as execution

    source = Path(execution.__file__).read_text(encoding="utf-8")
    assert "inspect.signature(original_compile)" in source
    assert "inspect.signature(original_persist)" in source
    assert source.count(".bind_partial(*args, **kwargs)") == 2
    assert "arguments.get(\"execution_strategy_ref\")" in source
    assert "arguments.get(\"database_url\")" in source
    assert "arguments.get(\"strict_run_ref\")" in source
    assert source.count("original_compile(*bound.args, **bound.kwargs)") == 1
    assert source.count("original_persist(*bound.args, **bound.kwargs)") == 1


def test_policy_installs_in_a_fresh_interpreter_without_import_cycle() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import src.policy; "
                "import src.policy.postgres_corpus_compilation as pg; "
                "import src.policy.operational_corpus_compilation as op; "
                "assert pg.compile_document_operational "
                "is op.compile_document_operational"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
