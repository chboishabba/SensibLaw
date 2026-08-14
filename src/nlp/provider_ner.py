"""Secondary named-entity pipeline for late provider-candidate recovery.

This pipeline is deliberately separate from the authoritative streaming syntax
parser. It may add alternative entity-boundary observations, but it never
rewrites parser tokens, dependencies, sentences, or primary ``doc.ents`` rows.
"""
from __future__ import annotations

import importlib
import os
from typing import Any

DEFAULT_PROVIDER_NER_MODEL = "en_core_web_trf"


def load_provider_ner(model_name: str | None = None) -> Any:
    """Load an installed NER-capable model without downloading anything.

    ``SENSIBLAW_PROVIDER_NER_MODEL`` is independent of ``SENSIBLAW_SPACY_MODEL``
    so an experiment with a stronger entity model cannot silently change the
    core parser authority.
    """

    requested = model_name or os.environ.get(
        "SENSIBLAW_PROVIDER_NER_MODEL", DEFAULT_PROVIDER_NER_MODEL
    )
    spacy = importlib.import_module("spacy")
    try:
        nlp = spacy.load(requested)
    except OSError as error:
        raise RuntimeError(
            "secondary provider NER model is not installed: "
            f"{requested!r}; install it explicitly before running the pass"
        ) from error
    if "ner" not in tuple(nlp.pipe_names):
        raise RuntimeError(
            f"secondary provider NER model {requested!r} has no ner component"
        )
    return nlp


def provider_ner_receipt(nlp: Any, *, requested_name: str) -> dict[str, object]:
    return {
        "model_name": requested_name,
        "model_version": str(nlp.meta.get("version") or "unknown"),
        "pipeline": tuple(str(name) for name in nlp.pipe_names),
        "authority": "secondary_entity_boundary_observation_only",
    }


__all__ = [
    "DEFAULT_PROVIDER_NER_MODEL",
    "load_provider_ner",
    "provider_ner_receipt",
]
