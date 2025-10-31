"""Integration layer for spaCy tokenization and sentence segmentation."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from spacy.language import Language
    from spacy.tokens import Doc, Span, Token

__all__ = ["parse"]

_DEFAULT_NLP: Optional["Language"] = None


def _import_spacy() -> ModuleType:
    return importlib.import_module("spacy")


def _build_default_nlp() -> "Language":
    """Create a deterministic spaCy pipeline with sentence boundaries."""
    global _DEFAULT_NLP
    if _DEFAULT_NLP is not None:
        return _DEFAULT_NLP

    spacy = _import_spacy()

    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner"])
    except OSError:
        nlp = spacy.blank("en")

    if "parser" not in nlp.pipe_names and "senter" not in nlp.pipe_names:
        if "sentencizer" not in nlp.pipe_names:
            nlp.add_pipe("sentencizer")

    if "lemmatizer" not in nlp.pipe_names:
        try:
            lemmatizer = nlp.add_pipe("lemmatizer", config={"mode": "lookup"})
            lemmatizer.initialize(lambda: [], nlp=nlp)
        except Exception:
            if "lemmatizer" in nlp.pipe_names:
                nlp.remove_pipe("lemmatizer")

    _DEFAULT_NLP = nlp
    return nlp


def _ensure_sentence_boundaries(nlp: "Language") -> None:
    """Ensure the pipeline yields sentence boundaries deterministically."""
    if "parser" in nlp.pipe_names or "senter" in nlp.pipe_names:
        return
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")


def _iter_sentences(doc: "Doc") -> Iterable["Span"]:
    if doc.has_annotation("SENT_START"):
        return doc.sents
    return (doc[:],)


def _serialize_token(token: "Token") -> Dict[str, Any]:
    end = token.idx + len(token.text)
    lemma = token.lemma_ if token.lemma_ else token.text
    return {
        "text": token.text,
        "lemma": lemma,
        "pos": token.pos_,
        "dep": token.dep_,
        "start": token.idx,
        "end": end,
    }


def parse(text: str, *, nlp: Optional["Language"] = None) -> Dict[str, Any]:
    """Parse *text* with spaCy and return structured sentence/token data."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    pipeline = nlp or _build_default_nlp()
    if nlp is not None:
        _ensure_sentence_boundaries(pipeline)

    doc = pipeline(text)

    sentences: List[Dict[str, Any]] = []
    for span in _iter_sentences(doc):
        tokens = [_serialize_token(token) for token in span]
        sentences.append(
            {
                "text": span.text,
                "start": span.start_char,
                "end": span.end_char,
                "tokens": tokens,
            }
        )

    return {"text": text, "sents": sentences}
