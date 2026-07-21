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

    pipe_names = tuple(pipeline.pipe_names)
    capabilities = {
        "tokenization": True,
        "sentence_segmentation": bool(
            "parser" in pipe_names
            or "senter" in pipe_names
            or "sentencizer" in pipe_names
        ),
        "part_of_speech": "tagger" in pipe_names or "morphologizer" in pipe_names,
        "morphology": "tagger" in pipe_names or "morphologizer" in pipe_names,
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
            "authority": "parser_observation_only",
        },
    }
