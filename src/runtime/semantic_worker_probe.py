"""Fresh-process probe for semantic-worker import isolation."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any


def probe_semantic_worker_imports() -> dict[str, Any]:
    """Import the actual worker module and report parser-runtime leakage."""

    importlib.import_module("src.policy.parallel_typing_tail")
    loaded = tuple(sorted(sys.modules))
    return {
        "pid": os.getpid(),
        "spacy_loaded": "spacy" in sys.modules,
        "spacy_adapter_loaded": "src.nlp.spacy_adapter" in sys.modules,
        "parser_runtime_loaded": (
            "spacy" in sys.modules or "src.nlp.spacy_adapter" in sys.modules
        ),
        "loaded_module_count": len(loaded),
        "policy_worker_module_loaded": "src.policy.parallel_typing_tail" in sys.modules,
    }


__all__ = ["probe_semantic_worker_imports"]
