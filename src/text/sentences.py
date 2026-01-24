"""Sentence segmentation utilities backed by spaCy."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator, List, Optional

try:  # pragma: no cover - spaCy may be unavailable
    import spacy
    from spacy.language import Language
    from spacy.tokens import Doc, Span
except Exception:  # pragma: no cover - degrade gracefully when spaCy fails
    spacy = None  # type: ignore[assignment]
    Language = None  # type: ignore[assignment]
    Doc = None  # type: ignore[assignment]
    Span = None  # type: ignore[assignment]

from src.models.sentence import Sentence


@lru_cache(maxsize=1)
def get_nlp() -> Optional[Language]:
    """Return a cached English spaCy pipeline with sentence boundaries."""

    if spacy is None:
        return None
    nlp = spacy.blank("en")
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp


def make_doc(text: str) -> Doc:
    """Create a spaCy :class:`Doc` with sentence boundaries enabled."""

    doc = get_nlp()(text)
    _mark_paragraph_boundaries(doc)
    return doc


def _mark_paragraph_boundaries(doc: Doc) -> None:
    """Ensure blank-line paragraph breaks start new sentences."""

    for token in doc[:-1]:
        if "\n\n" in token.text:
            next_token = doc[token.i + 1]
            next_token.is_sent_start = True


def iter_sentence_spans(doc: Doc) -> Iterator[Span]:
    """Yield non-empty sentence spans from ``doc``."""

    for span in doc.sents:
        if span.text.strip():
            yield span


def segment_sentences(text: str) -> List[Sentence]:
    """Segment ``text`` into :class:`Sentence` objects."""

    if get_nlp() is None:
        if not text:
            return []
        # Minimal fallback: split on sentence terminators to maintain structure without spaCy.
        parts = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
        return [
            Sentence(text=part, start_char=0, end_char=len(part), index=idx)
            for idx, part in enumerate(parts)
        ]

    doc = make_doc(text)
    sentences: List[Sentence] = []
    for index, span in enumerate(iter_sentence_spans(doc)):
        raw = span.text
        stripped = raw.strip()
        if not stripped:
            continue
        leading_ws = len(raw) - len(raw.lstrip())
        trailing_ws = len(raw) - len(raw.rstrip())
        start_char = span.start_char + leading_ws
        end_char = span.end_char - trailing_ws
        sentences.append(
            Sentence(
                text=stripped,
                start_char=start_char,
                end_char=end_char,
                index=index,
            )
        )
    return sentences


__all__ = ["get_nlp", "make_doc", "iter_sentence_spans", "segment_sentences"]
