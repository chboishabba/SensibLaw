"""Dependency parsing helpers for rule extraction."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Sequence

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from spacy.language import Language
    from spacy.tokens import Doc, Span, Token
else:
    Language = Any  # type: ignore[assignment]
    Doc = Any  # type: ignore[assignment]
    Span = Any  # type: ignore[assignment]
    Token = Any  # type: ignore[assignment]

__all__ = [
    "DependencyCandidate",
    "SentenceDependencies",
    "get_dependencies",
]


_DEFAULT_MODELS: Sequence[str] = (
    "en_core_web_sm",
    "en_core_web_md",
    "en_core_web_lg",
)

_DET_LIKE_DEPS = {"det"}

_SUPPORTED_DEPS = {
    "nsubj",
    "obj",
    "dobj",
    "iobj",
    "obl",
    "ccomp",
    "xcomp",
    "advcl",
    "advmod",
    "mark",
    "aux",
    "auxpass",
    "neg",
    "parataxis",
    "acl",
    "acl:relcl",
    "amod",
    "appos",
    "agent",
}


@dataclass(frozen=True)
class DependencyCandidate:
    """A dependency arc anchored on a token or span."""

    label: str
    text: str
    lemma: str
    pos: str


@dataclass(frozen=True)
class SentenceDependencies:
    """Dependency candidates grouped by sentence."""

    text: str
    candidates: Dict[str, List[DependencyCandidate]]


def _normalise_tokens(tokens: Iterable[Token]) -> str:
    """Return a cleaned phrase from ``tokens``.

    Determiners are dropped so that ``A person`` normalises to ``person``. If
    removing determiners would yield an empty phrase, the original tokens are
    used instead.
    """

    material = list(tokens)
    filtered = [token for token in material if token.dep_.lower() not in _DET_LIKE_DEPS]
    target = filtered or material
    return " ".join(token.text for token in target).strip()


@lru_cache(maxsize=1)
def _load_pipeline() -> Language:
    """Load a spaCy English pipeline with a dependency parser.

    The helper attempts the common small/medium/large English models in order
    and raises a runtime error with a clear remediation step if none are
    available.
    """

    import importlib
    import sys

    project_root = str(Path(__file__).resolve().parents[2])
    reordered = False
    if project_root in sys.path:
        sys.path.remove(project_root)
        sys.path.append(project_root)
        reordered = True

    try:
        spacy = importlib.import_module("spacy")
    finally:
        if reordered:
            sys.path.remove(project_root)
            sys.path.insert(0, project_root)

    for model_name in _DEFAULT_MODELS:
        try:
            return spacy.load(model_name)
        except OSError:
            continue
    raise RuntimeError(
        "No spaCy English model with a dependency parser is installed. "
        "Install one with `python -m spacy download en_core_web_sm`."
    )


def _extract_span(token: Token) -> Span:
    """Return the span covering ``token`` and its modifiers."""

    subtree_tokens = list(token.subtree)
    start = subtree_tokens[0].i
    end = subtree_tokens[-1].i + 1
    return token.doc[start:end]


def _collect_candidates(sentence: Span) -> Dict[str, List[DependencyCandidate]]:
    """Collect dependency candidates for ``sentence``."""

    buckets: Dict[str, List[DependencyCandidate]] = {}

    for token in sentence:
        dep_label = token.dep_.lower()
        if dep_label == "dobj":
            dep_label = "obj"
        if dep_label == "root" and token.pos_ in {"VERB", "AUX"}:
            dep_label = "verb"
        elif dep_label not in _SUPPORTED_DEPS:
            continue

        if dep_label == "verb":
            text = token.lemma_ or token.text
        else:
            span = _extract_span(token)
            text = _normalise_tokens(span)
        candidate = DependencyCandidate(
            label=dep_label,
            text=text,
            lemma=token.lemma_,
            pos=token.pos_,
        )

        candidates = buckets.setdefault(dep_label, [])
        if candidate not in candidates:
            candidates.append(candidate)

    return buckets


def _iterate_sentences(doc: Doc) -> Iterable[Span]:
    """Yield sentence spans from ``doc`` including fallback segmentation."""

    if doc.has_annotation("SENT_START"):
        yield from doc.sents
        return

    yield doc[:]


def get_dependencies(text: str) -> List[SentenceDependencies]:
    """Parse ``text`` returning dependency candidates per sentence."""

    if not text.strip():
        return []

    parser = _load_pipeline()
    doc = parser(text)
    sentences: List[SentenceDependencies] = []

    for sentence in _iterate_sentences(doc):
        candidates = _collect_candidates(sentence)
        sentences.append(
            SentenceDependencies(
                text=sentence.text.strip(),
                candidates=candidates,
            )
        )

    return sentences

