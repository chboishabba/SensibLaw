"""Install typed streamed spaCy execution at the operational parser seam."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
from typing import Any, Mapping

from src.storage.postgres.streaming_spacy_execution import (
    ParserStreamingPolicy,
    run_streaming_spacy_execution,
)


_INSTALL_MARKER = "_streaming_spacy_parser_execution_installed"
_STRICT_STRATEGIES = frozenset(
    {
        "postgresql-leased-exact-execution:v1",
        "postgresql-leased-exact-execution:v2",
        "postgresql-typed-exact-execution:v2",
    }
)


@dataclass(frozen=True)
class _ParserExecution:
    database_url: str
    run_ref: str
    parser_contract_ref: str


_CURRENT: ContextVar[_ParserExecution | None] = ContextVar(
    "sensiblaw_streaming_spacy_parser_execution",
    default=None,
)


def _integer_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    value = default if raw is None or not raw.strip() else int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _boolean_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _safe_ref(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in value
    )


def _is_strict_strategy(strategy: str) -> bool:
    return strategy in _STRICT_STRATEGIES or (
        strategy.startswith("postgresql-") and "exact" in strategy
    )


def _execution_context(
    *,
    database_url: str,
    run_ref: str,
    compiler_context: Any,
) -> _ParserExecution:
    return _ParserExecution(
        database_url=database_url,
        run_ref=run_ref,
        parser_contract_ref=str(
            getattr(compiler_context, "annotation_backend_ref", "parser:spacy")
        ),
    )


def install_streaming_spacy_parser_execution() -> bool:
    """Route strict parser work through typed PostgreSQL observations."""

    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False
    # Import after the operational module is available. This module copied the
    # compiler function with ``from ... import`` historically, so its bindings
    # are explicitly updated below rather than relying on import timing.
    from src.policy import postgres_corpus_compilation as postgres

    original_compile = operational.compile_document_operational
    original_persist = postgres.persist_document_compilation
    compile_signature = inspect.signature(original_compile)
    persist_signature = inspect.signature(original_persist)
    compatibility_parser = operational.parse_document_fibres
    original_policy_to_dict = operational.DocumentFibrePolicy.to_dict

    def semantic_policy_to_dict(self: Any) -> dict[str, Any]:
        execution = _CURRENT.get()
        if execution is None:
            return original_policy_to_dict(self)
        # Physical chunk size, overlap, and worker count are scheduling facts.
        # They are persisted in typed partition rows but excluded from semantic
        # build identity, so tuning throughput cannot fork the document graph.
        return {
            "contract_ref": "parser-physical-partitioning:semantic-inert:v1",
            "parser_contract_ref": execution.parser_contract_ref,
            "physical_partition_semantic_effect": "none",
            "worker_count_semantic_effect": "none",
            "ownership_coverage": "exactly_once",
            "boundary_policy": "durable_obligation_and_targeted_repair",
        }

    def parser_dispatch(
        *,
        document_ref: str,
        canonical_text: str,
        parser: Any,
        policy: Any,
        checkpoint_dir: str | None = None,
        progress: Any | None = None,
    ) -> Mapping[str, Any]:
        execution = _CURRENT.get()
        if execution is None:
            return compatibility_parser(
                document_ref=document_ref,
                canonical_text=canonical_text,
                parser=parser,
                policy=policy,
                checkpoint_dir=checkpoint_dir,
                progress=progress,
            )
        configured_root = os.environ.get("SENSIBLAW_TYPED_PARSER_ARTIFACT_ROOT")
        if configured_root:
            artifact_root = Path(configured_root) / _safe_ref(execution.run_ref)
        elif checkpoint_dir:
            artifact_root = Path(checkpoint_dir) / "typed-spacy"
        else:
            artifact_root = (
                Path(".tmp")
                / "typed-spacy-parser"
                / _safe_ref(execution.run_ref)
            )
        parser_policy = ParserStreamingPolicy(
            target_chars=_integer_env(
                "SENSIBLAW_SPACY_PARTITION_TARGET_CHARS",
                min(int(policy.target_chars), 32_768),
                minimum=1_024,
            ),
            context_chars=_integer_env(
                "SENSIBLAW_SPACY_PARTITION_CONTEXT_CHARS",
                min(int(policy.overlap_chars), 2_048),
                minimum=0,
            ),
            batch_size=_integer_env(
                "SENSIBLAW_SPACY_PIPE_BATCH_SIZE",
                4,
            ),
            lease_seconds=_integer_env(
                "SENSIBLAW_SPACY_PARTITION_LEASE_SECONDS",
                180,
            ),
            max_repair_depth=_integer_env(
                "SENSIBLAW_SPACY_BOUNDARY_REPAIR_DEPTH",
                2,
                minimum=0,
            ),
            cache_docbin=_boolean_env("SENSIBLAW_SPACY_DOCBIN_CACHE", True),
        )
        carrier = run_streaming_spacy_execution(
            database_url=execution.database_url,
            run_ref=execution.run_ref,
            document_ref=document_ref,
            canonical_text=canonical_text,
            parser_contract_ref=execution.parser_contract_ref,
            artifact_root=artifact_root,
            worker_count=int(policy.workers),
            policy=parser_policy,
        )
        if progress is not None and hasattr(progress, "observe"):
            progress.observe(
                measures={"fibres": carrier.partition_count},
                details={
                    "parser_execution_contract": "postgres-streaming-spacy:v1",
                    "authority_backend": "postgresql",
                    "sentence_count": carrier.sentence_count,
                    "token_count": carrier.token_count,
                },
            )
        return carrier

    def compile_wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = compile_signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arguments = bound.arguments
        document_input = arguments.get("document_input")
        compiler_context = arguments.get("compiler_context")
        strategy = str(
            arguments.get("execution_strategy_ref")
            or "local-compatibility-replay"
        )
        strict = _is_strict_strategy(strategy)
        database_url = arguments.get("database_url")
        if strict and not database_url:
            from src.runtime.strict_postgres_execution import StrictExecutionError

            raise StrictExecutionError(
                "postgresql_authority_missing",
                kernel_key="strict.parser_annotation",
            )
        if not strict:
            return original_compile(*args, **kwargs)
        if not isinstance(document_input, Mapping):
            raise ValueError("strict parser execution requires document_input")
        document_ref = str(document_input.get("document_ref") or "")
        execution = _execution_context(
            database_url=str(database_url),
            run_ref=str(
                arguments.get("strict_run_ref")
                or f"strict-parser:{document_ref}"
            ),
            compiler_context=compiler_context,
        )
        token = _CURRENT.set(execution)
        try:
            return original_compile(*args, **kwargs)
        finally:
            _CURRENT.reset(token)

    def persist_wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = persist_signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arguments = bound.arguments
        strategy = str(
            arguments.get("execution_strategy_ref")
            or "local-compatibility-replay"
        )
        if not _is_strict_strategy(strategy):
            return original_persist(*args, **kwargs)
        database_url = arguments.get("database_url")
        if not database_url:
            from src.runtime.strict_postgres_execution import StrictExecutionError

            raise StrictExecutionError(
                "postgresql_authority_missing",
                kernel_key="strict.parser_annotation",
            )
        entry = arguments.get("entry")
        compiler_context = arguments.get("context")
        if not isinstance(entry, Mapping):
            raise ValueError("strict persistence requires a document entry")
        document_ref = str(entry.get("document_ref") or "")
        execution = _execution_context(
            database_url=str(database_url),
            run_ref=str(
                arguments.get("strict_run_ref")
                or f"strict-parser:{document_ref}"
            ),
            compiler_context=compiler_context,
        )
        token = _CURRENT.set(execution)
        try:
            return original_persist(*args, **kwargs)
        finally:
            _CURRENT.reset(token)

    operational.DocumentFibrePolicy.to_dict = semantic_policy_to_dict
    operational.parse_document_fibres = parser_dispatch
    operational.compile_document_operational = compile_wrapper
    operational._compile_document_operational_without_streaming_spacy = original_compile
    # Keep the copied compiler/persistence bindings in the PostgreSQL module on
    # the same strict execution context before its outer build-key calculation.
    postgres.compile_document_operational = compile_wrapper
    postgres.persist_document_compilation = persist_wrapper
    postgres._persist_document_compilation_without_streaming_spacy = original_persist
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = ["install_streaming_spacy_parser_execution"]
