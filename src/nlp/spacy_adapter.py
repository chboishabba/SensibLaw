"""Integration layer for spaCy tokenization and sentence segmentation."""

from __future__ import annotations

import ctypes
import gc
import importlib
from threading import Lock
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from spacy.language import Language
    from spacy.tokens import Doc, Span, Token

__all__ = [
    "get_default_nlp",
    "get_streaming_nlp",
    "parse",
    "release_default_nlp",
]

_DEFAULT_NLP: Optional["Language"] = None
_STREAMING_NLP: Optional["Language"] = None
_NLP_LOCK = Lock()


def _import_spacy() -> ModuleType:
    return importlib.import_module("spacy")


def _ensure_sentence_boundaries(nlp: "Language") -> None:
    if "parser" in nlp.pipe_names or "senter" in nlp.pipe_names:
        return
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")


def _ensure_lemmatizer(nlp: "Language") -> None:
    if "lemmatizer" in nlp.pipe_names:
        return
    try:
        lemmatizer = nlp.add_pipe("lemmatizer", config={"mode": "lookup"})
        lemmatizer.initialize(lambda: [], nlp=nlp)
    except Exception:
        if "lemmatizer" in nlp.pipe_names:
            nlp.remove_pipe("lemmatizer")


def _load_pipeline(*, include_entities: bool) -> "Language":
    spacy = _import_spacy()
    try:
        nlp = (
            spacy.load("en_core_web_sm")
            if include_entities
            else spacy.load("en_core_web_sm", disable=["ner"])
        )
    except OSError:
        nlp = spacy.blank("en")
    _ensure_sentence_boundaries(nlp)
    _ensure_lemmatizer(nlp)
    return nlp


def get_default_nlp() -> "Language":
    """Return the cached compatibility pipeline without entity recognition."""

    global _DEFAULT_NLP
    if _DEFAULT_NLP is not None:
        return _DEFAULT_NLP
    with _NLP_LOCK:
        if _DEFAULT_NLP is None:
            _DEFAULT_NLP = _load_pipeline(include_entities=False)
        return _DEFAULT_NLP


def get_streaming_nlp() -> "Language":
    """Return one full pipeline per parser worker process.

    The caller feeds bounded partitions through ``Language.pipe`` with
    ``n_process=1``.  Process-level parallelism remains under PostgreSQL lease
    control rather than being nested inside spaCy.
    """

    global _STREAMING_NLP
    if _STREAMING_NLP is not None:
        return _STREAMING_NLP
    with _NLP_LOCK:
        if _STREAMING_NLP is None:
            _STREAMING_NLP = _load_pipeline(include_entities=True)
        return _STREAMING_NLP


def release_default_nlp() -> bool:
    """Release cached parser pipelines after checkpoint-backed work."""

    global _DEFAULT_NLP, _STREAMING_NLP
    with _NLP_LOCK:
        released = _DEFAULT_NLP is not None or _STREAMING_NLP is not None
        _DEFAULT_NLP = None
        _STREAMING_NLP = None
    if released:
        gc.collect()
        try:
            ctypes.CDLL(None).malloc_trim(0)
        except (AttributeError, OSError):  # pragma: no cover - platform allocator
            pass
    return released


def _iter_sentences(doc: "Doc") -> Iterable["Span"]:
    if doc.has_annotation("SENT_START"):
        return doc.sents
    return (doc[:],)


def _serialize_token(token: "Token") -> Dict[str, Any]:
    end = token.idx + len(token.text)
    lemma = token.lemma_ if token.lemma_ else token.text
    morph = {key: list(token.morph.get(key)) for key in token.morph.to_dict()}
    return {
        "index": token.i,
        "text": token.text,
        "lemma": lemma,
        "pos": token.pos_,
        "tag": token.tag_,
        "morph": morph,
        "dep": token.dep_,
        "head_index": token.head.i,
        "head_text": token.head.text,
        "start": token.idx,
        "end": end,
    }


def parse(text: str, *, nlp: Optional["Language"] = None) -> Dict[str, Any]:
    """Compatibility parser; strict execution uses the typed streaming path."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    pipeline = nlp or get_default_nlp()
    if nlp is not None:
        _ensure_sentence_boundaries(pipeline)
    doc = pipeline(text)
    sentences: List[Dict[str, Any]] = []
    for span in _iter_sentences(doc):
        sentences.append(
            {
                "text": span.text,
                "start": span.start_char,
                "end": span.end_char,
                "tokens": [_serialize_token(token) for token in span],
            }
        )
    pipe_names = tuple(pipeline.pipe_names)
    capabilities = {
        "tokenization": True,
        "sentence_segmentation": any(
            name in pipe_names for name in ("parser", "senter", "sentencizer")
        ),
        "part_of_speech": any(
            name in pipe_names for name in ("tagger", "morphologizer")
        ),
        "morphology": any(
            name in pipe_names for name in ("tagger", "morphologizer")
        ),
        "dependencies": "parser" in pipe_names,
        "named_entity_spans": "ner" in pipe_names,
        "coreference_candidates": False,
    }
    return {
        "text": text,
        "sents": sentences,
        "parser_receipt": {
            "backend_ref": "parser:spacy",
            "model_name": str(pipeline.meta.get("name") or "unknown"),
            "model_version": str(pipeline.meta.get("version") or "unknown"),
            "pipeline": list(pipe_names),
            "capabilities": capabilities,
            "authority": "compatibility_parser_observation_only",
        },
    }
