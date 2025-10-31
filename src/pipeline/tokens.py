"""Tokenisation utilities for the processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Sequence

try:  # pragma: no cover - spaCy is an optional dependency
    import spacy
    from spacy.language import Language
except Exception:  # pragma: no cover - provide a graceful fallback
    spacy = None
    Language = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Token:
    """A lightweight representation of an NLP token."""

    text: str
    lemma: str
    pos: str
    dep: str
    ent_type: str


TokenStream = List[Token]


class SpacyAdapter:
    """Adapter around spaCy providing a consistent token stream."""

    def __init__(self, model: str | None = None, *, disable: Sequence[str] | None = None) -> None:
        self.model = model or "en_core_web_sm"
        self._disable = tuple(disable or ())
        self._nlp: Language | None = None

    def _load_pipeline(self) -> Language | None:
        if spacy is None:  # pragma: no cover - exercised when spaCy is absent
            return None

        if self._nlp is not None:
            return self._nlp

        try:  # pragma: no cover - depends on spaCy installation
            self._nlp = spacy.load(self.model, disable=self._disable)
        except Exception:
            # Fallback to a blank English model if the target model isn't
            # available.  This still yields a deterministic token stream even
            # without trained components such as POS taggers.
            self._nlp = spacy.blank("en")

        return self._nlp

    def parse(self, text: str) -> TokenStream:
        """Return a stream of tokens for ``text``.

        When spaCy is not installed, tokenisation degrades gracefully to a
        simple whitespace split so downstream consumers still receive a
        predictable structure.
        """

        if not text:
            return []

        pipeline = self._load_pipeline()
        if pipeline is None:
            return self._fallback_tokens(text)

        doc = pipeline(text)
        return [
            Token(
                token.text,
                token.lemma_ or token.text,
                token.pos_,
                token.dep_,
                token.ent_type_,
            )
            for token in doc
            if not token.is_space
        ]

    @staticmethod
    def _fallback_tokens(text: str) -> TokenStream:
        return [
            Token(part, part.lower(), "", "", "")
            for part in text.split()
            if part
        ]


@lru_cache(maxsize=1)
def get_spacy_adapter() -> SpacyAdapter:
    """Return a cached :class:`SpacyAdapter` instance."""

    return SpacyAdapter(disable=("ner",))


spacy_adapter = get_spacy_adapter()


__all__ = ["Token", "TokenStream", "SpacyAdapter", "get_spacy_adapter", "spacy_adapter"]
