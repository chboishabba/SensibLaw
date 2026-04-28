"""Sentence segmentation utilities backed by spaCy."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterator, List, Mapping, Optional, Sequence

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


@dataclass(frozen=True)
class CanonicalBoundaryState:
    """Structural boundary state for a canonical unit.

    This state is intentionally boolean/native only. It does not store fragment
    strings or semantic labels.
    """

    page: int
    continues_from_previous_page: bool
    continues_to_next_page: bool
    repeated_heading_with_previous: bool
    repeated_heading_with_next: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "continues_from_previous_page": self.continues_from_previous_page,
            "continues_to_next_page": self.continues_to_next_page,
            "repeated_heading_with_previous": self.repeated_heading_with_previous,
            "repeated_heading_with_next": self.repeated_heading_with_next,
        }


@dataclass(frozen=True)
class CanonicalSentenceUnit:
    """A sentence unit with page-local spans and structural boundary state."""

    sentence: Sentence
    boundary_state: CanonicalBoundaryState

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentence": self.sentence.to_dict(),
            "boundary_state": self.boundary_state.to_dict(),
        }


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


def _normalize_heading(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _starts_with_lowercase(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].islower()


def _ends_with_terminal_punctuation(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return True
    return stripped[-1] in ".!?:;)]}\"'"


def _page_boundary_continuation(
    previous_page: Mapping[str, Any] | None,
    current_page: Mapping[str, Any],
) -> bool:
    if previous_page is None:
        return False
    previous_body = str(previous_page.get("text") or "").strip()
    current_body = str(current_page.get("text") or "").strip()
    if not previous_body or not current_body:
        return False
    return (not _ends_with_terminal_punctuation(previous_body)) and _starts_with_lowercase(
        current_body
    )


def build_canonical_sentence_units(
    pages: Sequence[Mapping[str, Any]],
) -> List[CanonicalSentenceUnit]:
    """Build canonical sentence units with structural page-boundary state.

    This is a pre-classification helper for PDF/page-origin text. It does not
    merge fragments by string content. It only exposes sentence-local spans and
    adjacent page boundary state that a caller may use before body
    qualification/classification.
    """

    page_units: list[tuple[Mapping[str, Any], list[Sentence]]] = []
    for page in pages:
        body = str(page.get("text") or "")
        sentences = segment_sentences(body)
        if sentences:
            page_units.append((page, sentences))

    units: list[CanonicalSentenceUnit] = []
    for index, (page, sentences) in enumerate(page_units):
        previous_page = page_units[index - 1][0] if index > 0 else None
        next_page = page_units[index + 1][0] if index + 1 < len(page_units) else None
        heading = _normalize_heading(page.get("heading"))
        repeated_with_previous = bool(
            heading and previous_page is not None and heading == _normalize_heading(previous_page.get("heading"))
        )
        repeated_with_next = bool(
            heading and next_page is not None and heading == _normalize_heading(next_page.get("heading"))
        )
        continues_from_previous = _page_boundary_continuation(previous_page, page)
        continues_to_next = _page_boundary_continuation(page, next_page) if next_page is not None else False
        page_number = int(page.get("page") or (index + 1))

        for sentence_index, sentence in enumerate(sentences):
            boundary_state = CanonicalBoundaryState(
                page=page_number,
                continues_from_previous_page=continues_from_previous and sentence_index == 0,
                continues_to_next_page=continues_to_next and sentence_index == (len(sentences) - 1),
                repeated_heading_with_previous=repeated_with_previous,
                repeated_heading_with_next=repeated_with_next,
            )
            units.append(CanonicalSentenceUnit(sentence=sentence, boundary_state=boundary_state))

    return units


__all__ = [
    "CanonicalBoundaryState",
    "CanonicalSentenceUnit",
    "build_canonical_sentence_units",
    "get_nlp",
    "make_doc",
    "iter_sentence_spans",
    "segment_sentences",
]
