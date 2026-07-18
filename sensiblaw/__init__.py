"""
Namespace shim so `import sensiblaw.*` resolves to the runtime code in src/sensiblaw.
This prevents the doc-side package at the repo root from shadowing the real
implementation modules (db, event_participants, ingest, etc.) when pytest runs
with rootdir at the project root.
"""

import pathlib
import pkgutil

_runtime_pkg = pathlib.Path(__file__).resolve().parent.parent / "src" / "sensiblaw"
if _runtime_pkg.exists():
    __path__ = pkgutil.extend_path(__path__, __name__)
    __path__.append(str(_runtime_pkg))

from src.policy.world_model_inputs import (  # noqa: E402
    WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION,
    build_input_envelope,
    normalize_input_envelope,
)
from src.policy.world_model_runtime import (  # noqa: E402
    attach_receipt,
    build_world_model,
    project_claim_table,
    project_linkage_case,
    project_report,
    project_review_surface,
    project_timeline,
)
from src.policy.corpus_compilation import (  # noqa: E402
    CompilerContext,
    build_corpus_manifest,
    compile_directory,
    compile_document,
    default_compiler_context,
)

__all__ = [
    "WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION",
    "CompilerContext",
    "attach_receipt",
    "build_input_envelope",
    "build_corpus_manifest",
    "build_world_model",
    "normalize_input_envelope",
    "compile_directory",
    "compile_document",
    "default_compiler_context",
    "project_claim_table",
    "project_linkage_case",
    "project_report",
    "project_review_surface",
    "project_timeline",
]
