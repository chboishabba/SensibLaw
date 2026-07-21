"""Public SensibLaw product surface."""

from __future__ import annotations

__all__ = [
    "WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION",
    "CompilerContext",
    "PostgresCompilerStore",
    "attach_receipt",
    "build_corpus_manifest",
    "build_input_envelope",
    "build_world_model",
    "compile_directory_postgres",
    "compile_document",
    "default_compiler_context",
    "normalize_input_envelope",
    "project_claim_table",
    "project_linkage_case",
    "project_report",
    "project_review_surface",
    "project_timeline",
]

_LAZY_EXPORTS = {
    "CompilerContext": ("src.policy.corpus_compilation", "CompilerContext"),
    "build_corpus_manifest": ("src.policy.corpus_compilation", "build_corpus_manifest"),
    "compile_document": ("src.policy.corpus_compilation", "compile_document"),
    "default_compiler_context": (
        "src.policy.corpus_compilation",
        "default_compiler_context",
    ),
    "compile_directory_postgres": (
        "src.policy.postgres_corpus_compilation",
        "compile_directory_postgres",
    ),
    "WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION": (
        "src.policy.world_model_inputs",
        "WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION",
    ),
    "build_input_envelope": ("src.policy.world_model_inputs", "build_input_envelope"),
    "normalize_input_envelope": (
        "src.policy.world_model_inputs",
        "normalize_input_envelope",
    ),
    "attach_receipt": ("src.policy.world_model_runtime", "attach_receipt"),
    "build_world_model": ("src.policy.world_model_runtime", "build_world_model"),
    "project_claim_table": (
        "src.policy.world_model_runtime",
        "project_claim_table",
    ),
    "project_linkage_case": (
        "src.policy.world_model_runtime",
        "project_linkage_case",
    ),
    "project_report": ("src.policy.world_model_runtime", "project_report"),
    "project_review_surface": (
        "src.policy.world_model_runtime",
        "project_review_surface",
    ),
    "project_timeline": ("src.policy.world_model_runtime", "project_timeline"),
    "PostgresCompilerStore": ("src.storage.postgres", "PostgresCompilerStore"),
}


def __getattr__(name: str):
    import importlib

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
