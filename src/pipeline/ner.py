"""spaCy-powered named entity recognition utilities."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Sequence

import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler
from spacy.tokens import Doc, Span

LOGGER = logging.getLogger(__name__)

REFERENCE_LABEL = "REFERENCE"
REFERENCE_SPAN_KEY = "REFERENCE"
NER_REFERENCE_LABELS = {"PERSON", "ORG", "LAW"}

_PATTERNS_PATH = Path(__file__).resolve().parents[2] / "patterns" / "legal_patterns.jsonl"

if not Span.has_extension("reference_source"):
    Span.set_extension("reference_source", default=None)


def _load_language(model_name: str | None = None) -> Language:
    """Load a spaCy language model.

    Attempts to load ``model_name`` (defaulting to ``en_core_web_sm``). When the
    requested model is unavailable the loader falls back to ``spacy.blank('en')``
    and logs a warning so callers understand that statistical NER coverage will
    be limited to rule-based matches.
    """

    preferred_model = model_name or "en_core_web_sm"
    try:
        return spacy.load(preferred_model)
    except (OSError, ImportError) as exc:  # pragma: no cover - depends on env
        LOGGER.warning(
            "Falling back to spaCy blank 'en' model because '%s' could not be loaded: %s",
            preferred_model,
            exc,
        )
        return spacy.blank("en")


def _ensure_entity_ruler(
    nlp: Language,
    patterns_path: Path | None = None,
    *,
    overwrite: bool = False,
) -> EntityRuler:
    """Ensure an ``EntityRuler`` is present and hydrated with legal patterns."""

    if overwrite and "entity_ruler" in nlp.pipe_names:
        nlp.remove_pipe("entity_ruler")

    if "entity_ruler" in nlp.pipe_names:
        ruler = nlp.get_pipe("entity_ruler")
    else:
        insert_before = "ner" if "ner" in nlp.pipe_names else None
        ruler = nlp.add_pipe(
            "entity_ruler",
            before=insert_before,
            config={"overwrite_ents": False},
        )

    # Ensure rule matches are accessible via ``doc.spans['REFERENCE']`` even if
    # an EntityRuler instance was injected by callers with custom settings.
    if hasattr(ruler, "overwrite"):
        ruler.overwrite = False
    if hasattr(ruler, "spans_key"):
        ruler.spans_key = REFERENCE_SPAN_KEY

    resolved_path = patterns_path or _PATTERNS_PATH
    if resolved_path.exists():
        ruler.from_disk(resolved_path)
    else:
        LOGGER.debug("Entity ruler patterns not found at %s", resolved_path)
    return ruler


def _normalise_pattern_span(span: Span) -> None:
    """Populate the ``reference_source`` extension for rule-based spans."""

    if span._.reference_source:
        return
    if span.ent_id_:
        span._.reference_source = span.ent_id_
    elif span.kb_id_:
        span._.reference_source = span.kb_id_
    else:
        span._.reference_source = "pattern"


@Language.component("reference_resolver")
def reference_resolver(doc: Doc) -> Doc:
    """Collect NER and rule-based hits into ``doc.spans['REFERENCE']``."""

    spans: List[Span] = []
    seen: set[tuple[int, int]] = set()

    for span in doc.spans.get(REFERENCE_SPAN_KEY, []):
        _normalise_pattern_span(span)
        key = (span.start, span.end)
        if key not in seen:
            spans.append(span)
            seen.add(key)

    for ent in doc.ents:
        key = (ent.start, ent.end)
        if key in seen:
            continue
        if ent.label_ == REFERENCE_LABEL:
            span = Span(doc, ent.start, ent.end, label=REFERENCE_LABEL)
            span._.reference_source = ent.ent_id_ or ent.kb_id_ or "pattern"
            spans.append(span)
            seen.add(key)
            continue
        if ent.label_ not in NER_REFERENCE_LABELS:
            continue
        span = Span(doc, ent.start, ent.end, label=REFERENCE_LABEL)
        span._.reference_source = ent.label_
        spans.append(span)
        seen.add(key)

    doc.spans[REFERENCE_SPAN_KEY] = spans
    return doc


def configure_ner_pipeline(
    nlp: Language,
    *,
    patterns_path: Path | None = None,
    overwrite_ruler: bool = False,
) -> Language:
    """Attach legal reference recognition components to ``nlp``."""

    _ensure_entity_ruler(nlp, patterns_path, overwrite=overwrite_ruler)
    if "reference_resolver" not in nlp.pipe_names:
        nlp.add_pipe("reference_resolver", last=True)
    return nlp


@lru_cache(maxsize=2)
def get_ner_pipeline(model_name: str | None = None) -> Language:
    """Return a configured spaCy pipeline for legal NER."""

    nlp = _load_language(model_name)
    return configure_ner_pipeline(nlp)


def analyze_references(
    text: str,
    *,
    model_name: str | None = None,
) -> Sequence[Span]:
    """Run the NER pipeline over ``text`` and return REFERENCE spans."""

    doc = get_ner_pipeline(model_name)(text)
    return tuple(doc.spans.get(REFERENCE_SPAN_KEY, ()))


__all__ = [
    "REFERENCE_LABEL",
    "REFERENCE_SPAN_KEY",
    "NER_REFERENCE_LABELS",
    "analyze_references",
    "configure_ner_pipeline",
    "get_ner_pipeline",
    "reference_resolver",
]
