"""Lightweight processing pipeline utilities."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List
from dataclasses import dataclass, field
import re
import string
from typing import ClassVar, Dict, Iterator, List, Sequence
from weakref import WeakSet

from src.concepts.matcher import MATCHER

from src.tools.glossary import rewrite_text

from src.tools.harm_index import compute_harm_index as harm_index

from .ner import (
    analyze_references,
    get_ner_pipeline,
    REFERENCE_SPAN_KEY,
    REFERENCE_LABEL,
)


class _TokenExtensionAccessor:
    """Provide dotted access to registered token extensions.

    The accessor mimics the subset of the spaCy extension API required by the
    application.  Extensions are stored on the owning :class:`Token` instance
    and can be updated at runtime.
    """

    __slots__ = ("_token",)

    def __init__(self, token: "Token") -> None:
        object.__setattr__(self, "_token", token)

    def __getattr__(self, name: str) -> object:
        extensions = object.__getattribute__(self, "_token")._extension_values
        if name in extensions:
            return extensions[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: object) -> None:
        token = object.__getattribute__(self, "_token")
        if name in token._extension_values:
            token._extension_values[name] = value
            return
        raise AttributeError(name)


class _TokenExtension:
    """Descriptor for per-token extensions."""

    __slots__ = ("default",)

    def __init__(self, default: object) -> None:
        self.default = default


@dataclass(slots=True, weakref_slot=True, unsafe_hash=True)
class Token:
    """A lightweight token representation used by the pipeline.

    The class intentionally mirrors a minimal subset of ``spacy.tokens.Token``
    so that downstream consumers can rely on familiar attribute names.  Each
    token exposes ``text``, ``lemma_``, ``pos_`` and ``morph`` attributes and
    supports custom extensions through :meth:`set_extension`.
    """

    text: str
    lemma_: str
    pos_: str
    morph: str
    idx: int

    _extensions: ClassVar[Dict[str, _TokenExtension]] = {}
    _instances: ClassVar[WeakSet["Token"]] = WeakSet()
    _extension_values: Dict[str, object] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _: _TokenExtensionAccessor = field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_extension_values",
            {name: ext.default for name, ext in self._extensions.items()},
        )
        object.__setattr__(self, "_", _TokenExtensionAccessor(self))
        self._instances.add(self)

    @classmethod
    def set_extension(
        cls, name: str, *, default: object | None = None, force: bool = False
    ) -> None:
        """Register a custom attribute available via ``token._``.

        Parameters
        ----------
        name:
            The name of the extension (e.g. ``"class_"``).
        default:
            Default value applied to both existing and future tokens.
        force:
            If ``True`` re-register an existing extension.
        """

        if name in cls._extensions and not force:
            raise ValueError(f"Extension '{name}' is already registered")
        cls._extensions[name] = _TokenExtension(default)
        for token in list(cls._instances):
            token._extension_values[name] = default
            object.__setattr__(token, "_", _TokenExtensionAccessor(token))

    def as_dict(self) -> Dict[str, object]:
        """Serialise the token and its extensions to a dictionary."""

        data: Dict[str, object] = {
            "text": self.text,
            "lemma_": self.lemma_,
            "pos_": self.pos_,
            "morph": self.morph,
            "idx": self.idx,
        }
        for name in self._extensions:
            data[name] = self._extension_values.get(name)
        return data


Token.set_extension("class_", default=None)


class NormalisedText(str):
    """String subclass bundling token-level annotations."""

    __slots__ = ("_tokens",)

    def __new__(cls, value: str, tokens: Sequence[Token]) -> "NormalisedText":
        obj = str.__new__(cls, value)
        object.__setattr__(obj, "_tokens", tuple(tokens))
        return obj

    @property
    def tokens(self) -> Sequence[Token]:
        """Return the sequence of annotated tokens."""

        return self._tokens


_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

_PRONOUNS = {
    "i": ("PRON", "Person=1|Number=Sing|PronType=Prs"),
    "we": ("PRON", "Person=1|Number=Plur|PronType=Prs"),
    "you": ("PRON", "Person=2|PronType=Prs"),
    "he": ("PRON", "Person=3|Number=Sing|PronType=Prs"),
    "she": ("PRON", "Person=3|Number=Sing|PronType=Prs"),
    "it": ("PRON", "Person=3|Number=Sing|PronType=Prs"),
    "they": ("PRON", "Person=3|Number=Plur|PronType=Prs"),
    "them": ("PRON", "Person=3|Number=Plur|PronType=Prs|Case=Acc"),
    "us": ("PRON", "Person=1|Number=Plur|PronType=Prs|Case=Acc"),
    "him": ("PRON", "Person=3|Number=Sing|PronType=Prs|Case=Acc"),
    "her": ("PRON", "Person=3|Number=Sing|PronType=Prs|Case=Acc"),
}

_DETERMINERS = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
}

_CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so"}
_PREPOSITIONS = {"in", "on", "at", "by", "for", "with", "of", "to", "from"}
_AUXILIARIES = {"is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "have", "has", "had"}
_ADVERB_SUFFIXES = ("ly", "wise")
_ADJECTIVE_SUFFIXES = ("al", "able", "ible", "ous", "ive", "ful", "less", "ary", "ory")
_VERB_PARTICIPLE_SUFFIXES = ("ing",)
_VERB_PAST_SUFFIXES = ("ed",)


def _iter_tokens(text: str) -> Iterator[tuple[str, int]]:
    for match in _TOKEN_PATTERN.finditer(text):
        yield match.group(), match.start()


def _guess_pos(token: str) -> str:
    if not token:
        return ""
    if token in string.punctuation:
        return "PUNCT"
    if token.isdigit():
        return "NUM"
    if token in _PRONOUNS:
        return _PRONOUNS[token][0]
    if token in _DETERMINERS:
        return "DET"
    if token in _CONJUNCTIONS:
        return "CCONJ"
    if token in _PREPOSITIONS:
        return "ADP"
    if token in _AUXILIARIES:
        return "AUX"
    if any(token.endswith(suffix) for suffix in _VERB_PARTICIPLE_SUFFIXES + _VERB_PAST_SUFFIXES):
        return "VERB"
    if any(token.endswith(suffix) for suffix in _ADVERB_SUFFIXES):
        return "ADV"
    if any(token.endswith(suffix) for suffix in _ADJECTIVE_SUFFIXES):
        return "ADJ"
    if token.endswith("s") and len(token) > 2:
        return "NOUN"
    return "NOUN"


def _guess_morph(token: str, pos: str) -> str:
    if pos == "PRON":
        return _PRONOUNS.get(token, ("PRON", "PronType=Prs"))[1]
    if pos == "DET":
        return "PronType=Art"
    if pos == "NUM":
        return "NumType=Card"
    if pos == "ADV":
        return "Degree=Pos"
    if pos == "ADJ":
        return "Degree=Pos"
    if pos == "VERB":
        if token.endswith("ing"):
            return "VerbForm=Part|Tense=Pres"
        if token.endswith("ed"):
            return "VerbForm=Fin|Tense=Past"
        return "VerbForm=Inf"
    if pos in {"NOUN", "PROPN"}:
        return "Number=Plur" if token.endswith("s") and len(token) > 2 else "Number=Sing"
    return ""


def _guess_lemma(token: str, pos: str) -> str:
    if pos == "VERB":
        if token.endswith("ing") and len(token) > 4:
            base = token[:-3]
            if len(base) > 2 and base[-1] == base[-2]:
                base = base[:-1]
            return base
        if token.endswith("ed") and len(token) > 3:
            base = token[:-2]
            if base.endswith("i"):
                base = base[:-1] + "y"
            elif len(base) > 2 and base[-1] == base[-2]:
                base = base[:-1]
            return base
    if pos == "NOUN":
        if token.endswith("ies") and len(token) > 4:
            return token[:-3] + "y"
        if token.endswith("ses") or token.endswith("xes"):
            return token[:-2]
        if token.endswith("s") and len(token) > 3:
            return token[:-1]
    return token


def _build_tokens(text: str) -> List[Token]:
    tokens: List[Token] = []
    for word, start in _iter_tokens(text):
        lower = word.lower()
        pos = _guess_pos(lower)
        lemma = _guess_lemma(lower, pos)
        morph = _guess_morph(lower, pos)
        tokens.append(Token(text=lower, lemma_=lemma, pos_=pos, morph=morph, idx=start))
    return tokens


def normalise(text: str) -> NormalisedText:
    """Normalise text for downstream processing.

    Institutional terminology is first rewritten using the glossary's
    movement equivalents to ensure consistent vocabulary. The rewritten text
    is then lowercased and tokenised with lightweight part-of-speech and
    morphological enrichment suitable for downstream classification.
    """

    rewritten = rewrite_text(text)
    lowered = rewritten.lower()
    tokens = _build_tokens(lowered)
    return NormalisedText(lowered, tokens)


def match_concepts(text: str) -> List[str]:
    """Match concepts within the text.

    Uses an Aho-Corasick automaton to locate concept triggers and returns
    the matched concept IDs.
    """
    return [hit.concept_id for hit in MATCHER.match(text)]


def build_cloud(concepts: List[str]) -> Dict[str, int]:
    """Build a frequency cloud of concepts.

    The current version counts the occurrences of each concept. This will
    eventually be replaced with richer semantic representations.
    """
    return dict(Counter(concepts))


__all__ = [
    "Token",
    "NormalisedText",
    "normalise",
    "match_concepts",
    "build_cloud",
    "harm_index",
    "analyze_references",
    "get_ner_pipeline",
    "REFERENCE_SPAN_KEY",
    "REFERENCE_LABEL",
]
