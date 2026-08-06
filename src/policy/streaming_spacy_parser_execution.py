"""Install numeric streamed spaCy and PNF execution for strict compilation."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_fields_sha256
from src.policy.numeric_pnf_compilation import (
    compile_numeric_pnf_document,
    persist_numeric_pnf_document,
)
from src.storage.postgres.streaming_spacy_execution import (
    STREAMING_SPACY_CONTRACT,
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


def _scoped_run_ref(
    *,
    requested_run_ref: str,
    document_ref: str,
    content_sha256: str,
    parser_contract_ref: str,
) -> str:
    if requested_run_ref.startswith("typed-spacy-run:"):
        return requested_run_ref
    return "typed-spacy-run:" + canonical_fields_sha256(
        STREAMING_SPACY_CONTRACT,
        requested_run_ref,
        document_ref,
        content_sha256,
        parser_contract_ref,
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


def _parser_policy(policy: Any) -> ParserStreamingPolicy:
    return ParserStreamingPolicy(
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


def _artifact_root(
    *,
    execution: _ParserExecution,
    checkpoint_dir: str | None,
) -> Path:
    configured_root = os.environ.get("SENSIBLAW_TYPED_PARSER_ARTIFACT_ROOT")
    if configured_root:
        return Path(configured_root) / _safe_ref(execution.run_ref)
    if checkpoint_dir:
        return Path(checkpoint_dir) / "typed-spacy"
    return Path(".tmp") / "typed-spacy-parser" / _safe_ref(execution.run_ref)


def install_streaming_spacy_parser_execution() -> bool:
    """Route strict parser and PNF work through numeric PostgreSQL authority."""

    from src.policy import operational_corpus_compilation as operational

    if getattr(operational, _INSTALL_MARKER, False):
        return False
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
        carrier = run_streaming_spacy_execution(
            database_url=execution.database_url,
            run_ref=execution.run_ref,
            document_ref=document_ref,
            canonical_text=canonical_text,
            parser_contract_ref=execution.parser_contract_ref,
            artifact_root=_artifact_root(
                execution=execution,
                checkpoint_dir=checkpoint_dir,
            ),
            worker_count=int(policy.workers),
            policy=_parser_policy(policy),
        )
        if progress is not None and hasattr(progress, "observe"):
            progress.observe(
                measures={"fibres": carrier.partition_count},
                details={
                    "parser_execution_contract": STREAMING_SPACY_CONTRACT,
                    "authority_backend": "postgresql_numeric_hyperfabric",
                    "sentence_count": carrier.sentence_count,
                    "token_count": carrier.token_count,
                },
            )
        return carrier

    def compile_wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = compile_signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arguments = bound.arguments
        strategy = str(
            arguments.get("execution_strategy_ref")
            or "local-compatibility-replay"
        )
        if not _is_strict_strategy(strategy):
            return original_compile(*bound.args, **bound.kwargs)
        database_url = arguments.get("database_url")
        if not database_url:
            from src.runtime.strict_postgres_execution import StrictExecutionError

            raise StrictExecutionError(
                "postgresql_authority_missing",
                kernel_key="strict.numeric_pnf",
            )
        document_input = arguments.get("document_input")
        context = arguments.get("compiler_context")
        if not isinstance(document_input, Mapping):
            raise ValueError("strict numeric compilation requires document_input")
        document_ref = str(document_input.get("document_ref") or "")
        content_sha256 = str(document_input.get("content_sha256") or "")
        media_type = str(document_input.get("media_type") or "")
        source_text = document_input.get("canonical_text")
        if not isinstance(source_text, str) or not source_text:
            raise ValueError("strict numeric compilation requires canonical text")
        source_ref = str(document_input.get("source_ref") or "")
        canonical_text, canonical_sha, adapter_ref = (
            postgres._canonical_source_coordinates(
                media_type=media_type,
                source_text=source_text,
                source_ref=source_ref,
            )
        )
        expected_document_ref = postgres._operational_document_ref(
            source_content_sha256=content_sha256,
            canonical_text_sha256=canonical_sha,
            media_type=media_type,
            media_adapter_ref=adapter_ref,
            context=context,
        )
        if document_ref != expected_document_ref:
            raise ValueError(
                "numeric operational document identity disagrees with canonical text"
            )
        parser_contract_ref = str(context.annotation_backend_ref)
        effective_run_ref = _scoped_run_ref(
            requested_run_ref=str(
                arguments.get("strict_run_ref")
                or f"strict-parser:{document_ref}"
            ),
            document_ref=document_ref,
            content_sha256=content_sha256,
            parser_contract_ref=parser_contract_ref,
        )
        execution = _execution_context(
            database_url=str(database_url),
            run_ref=effective_run_ref,
            compiler_context=context,
        )
        token = _CURRENT.set(execution)
        try:
            build_key = postgres._operational_build_key(
                document_ref=document_ref,
                content_sha256=content_sha256,
                canonical_text_sha256=canonical_sha,
                media_adapter_ref=adapter_ref,
                context=context,
                parser_workers=int(arguments.get("parser_workers") or 2),
                parser_limit_chars=int(
                    arguments.get("parser_limit_chars") or 1_000_000
                ),
                parser_target_chars=int(
                    arguments.get("parser_target_chars") or 400_000
                ),
                parser_overlap_chars=int(
                    arguments.get("parser_overlap_chars") or 8_192
                ),
            )
            return compile_numeric_pnf_document(
                database_url=str(database_url),
                run_ref=effective_run_ref,
                document_ref=document_ref,
                content_sha256=content_sha256,
                media_type=media_type,
                canonical_text=canonical_text,
                canonical_text_sha256=canonical_sha,
                media_adapter_ref=adapter_ref,
                parser_contract_ref=parser_contract_ref,
                build_key_sha256=build_key,
                parser_workers=int(arguments.get("parser_workers") or 2),
                parser_target_chars=int(
                    arguments.get("parser_target_chars") or 400_000
                ),
                parser_overlap_chars=int(
                    arguments.get("parser_overlap_chars") or 8_192
                ),
                parser_checkpoint_dir=arguments.get("parser_checkpoint_dir"),
                progress=arguments.get("progress"),
            )
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
            return original_persist(*bound.args, **bound.kwargs)
        database_url = arguments.get("database_url")
        if not database_url:
            from src.runtime.strict_postgres_execution import StrictExecutionError

            raise StrictExecutionError(
                "postgresql_authority_missing",
                kernel_key="strict.numeric_pnf",
            )
        entry = arguments.get("entry")
        context = arguments.get("context")
        source_text = arguments.get("source_text")
        if not isinstance(entry, Mapping) or not isinstance(source_text, str):
            raise ValueError("strict numeric persistence requires entry and source text")
        document_ref = str(entry.get("document_ref") or "")
        content_sha256 = str(entry.get("content_sha256") or "")
        media_type = str(entry.get("media_type") or "")
        source_ref = f"document-source:{document_ref}"
        canonical_text, canonical_sha, adapter_ref = (
            postgres._canonical_source_coordinates(
                media_type=media_type,
                source_text=source_text,
                source_ref=source_ref,
            )
        )
        expected_document_ref = postgres._operational_document_ref(
            source_content_sha256=content_sha256,
            canonical_text_sha256=canonical_sha,
            media_type=media_type,
            media_adapter_ref=adapter_ref,
            context=context,
        )
        if document_ref != expected_document_ref:
            raise ValueError(
                "numeric operational document identity disagrees with canonical text"
            )
        if str(entry.get("canonical_text_sha256") or "") != canonical_sha:
            raise ValueError("manifest canonical text hash disagrees with numeric PNF")
        if str(entry.get("media_adapter_ref") or "") != adapter_ref:
            raise ValueError("manifest media adapter disagrees with numeric PNF")
        parser_contract_ref = str(context.annotation_backend_ref)
        effective_run_ref = _scoped_run_ref(
            requested_run_ref=str(
                arguments.get("strict_run_ref")
                or f"strict-parser:{document_ref}"
            ),
            document_ref=document_ref,
            content_sha256=content_sha256,
            parser_contract_ref=parser_contract_ref,
        )
        execution = _execution_context(
            database_url=str(database_url),
            run_ref=effective_run_ref,
            compiler_context=context,
        )
        token = _CURRENT.set(execution)
        try:
            build_key = postgres._operational_build_key(
                document_ref=document_ref,
                content_sha256=content_sha256,
                canonical_text_sha256=canonical_sha,
                media_adapter_ref=adapter_ref,
                context=context,
                parser_workers=int(arguments.get("parser_workers") or 2),
                parser_limit_chars=int(
                    arguments.get("parser_limit_chars") or 1_000_000
                ),
                parser_target_chars=int(
                    arguments.get("parser_target_chars") or 400_000
                ),
                parser_overlap_chars=int(
                    arguments.get("parser_overlap_chars") or 8_192
                ),
            )
            return persist_numeric_pnf_document(
                store=arguments["store"],
                corpus_ref=str(arguments["corpus_ref"]),
                relative_path=str(arguments["relative_path"]),
                entry=entry,
                source_bytes=bytes(arguments["source_bytes"]),
                canonical_text=canonical_text,
                canonical_text_sha256=canonical_sha,
                media_adapter_ref=adapter_ref,
                context=context,
                build_key_sha256=build_key,
                database_url=str(database_url),
                run_ref=effective_run_ref,
                parser_workers=int(arguments.get("parser_workers") or 2),
                parser_target_chars=int(
                    arguments.get("parser_target_chars") or 400_000
                ),
                parser_overlap_chars=int(
                    arguments.get("parser_overlap_chars") or 8_192
                ),
                parser_checkpoint_dir=arguments.get("parser_checkpoint_dir"),
                progress=arguments.get("progress"),
            )
        finally:
            _CURRENT.reset(token)

    operational.DocumentFibrePolicy.to_dict = semantic_policy_to_dict
    operational.parse_document_fibres = parser_dispatch
    operational.compile_document_operational = compile_wrapper
    operational._compile_document_operational_without_streaming_spacy = original_compile
    postgres.compile_document_operational = compile_wrapper
    postgres.persist_document_compilation = persist_wrapper
    postgres._persist_document_compilation_without_streaming_spacy = original_persist
    setattr(operational, _INSTALL_MARKER, True)
    return True


__all__ = ["install_streaming_spacy_parser_execution"]
