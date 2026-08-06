"""Install typed streamed spaCy execution at the operational parser seam."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
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


def install_streaming_spacy_parser_execution() -> bool:
    """Route strict parser work through typed PostgreSQL observations."""

    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False
    original_compile = operational.compile_document_operational
    compatibility_parser = operational.parse_document_fibres

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
        document_input = args[0] if args else kwargs.get("document_input")
        compiler_context = args[1] if len(args) > 1 else kwargs.get("compiler_context")
        strategy = str(
            kwargs.get("execution_strategy_ref")
            or "local-compatibility-replay"
        )
        strict = strategy in _STRICT_STRATEGIES
        database_url = kwargs.get("database_url")
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
        run_ref = str(
            kwargs.get("strict_run_ref")
            or f"strict-parser:{document_ref}"
        )
        parser_contract_ref = str(
            getattr(compiler_context, "annotation_backend_ref", "parser:spacy")
        )
        token = _CURRENT.set(
            _ParserExecution(
                database_url=str(database_url),
                run_ref=run_ref,
                parser_contract_ref=parser_contract_ref,
            )
        )
        try:
            return original_compile(*args, **kwargs)
        finally:
            _CURRENT.reset(token)

    operational.parse_document_fibres = parser_dispatch
    operational.compile_document_operational = compile_wrapper
    operational._compile_document_operational_without_streaming_spacy = original_compile
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = ["install_streaming_spacy_parser_execution"]
