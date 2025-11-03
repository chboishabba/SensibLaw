"""High-level NLP wrappers with optional language detection hooks.

The helpers in this module are intentionally defensive: they try to import
heavy dependencies such as spaCy, Stanza, fastText or Tika only when they are
available in the current environment.  If an optional dependency is missing we
fall back to extremely light-weight stand-ins that mimic the minimal shape of
the respective libraries.  This keeps the core package importable in
environments where those libraries are not installed while still providing
integration points when they *are* present.

The ``SpacyNLP`` wrapper exposes a uniform ``__call__`` interface that returns
``Doc``-like objects.  It can automatically detect the language of the input by
trying one or more language detection hooks.  When a non-English language is
detected and Stanza is available we automatically switch to a Universal
Dependencies pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from typing import Callable, Iterable, Optional, Protocol


class LanguageDetector(Protocol):
    """Protocol implemented by language detection hooks."""

    def __call__(self, text: str) -> Optional[str]:  # pragma: no cover - Protocol
        """Return the ISO language code for *text* or ``None`` if unknown."""


@dataclass
class SimpleDoc:
    """Minimal stand-in for spaCy/Stanza ``Doc`` objects used as a fallback."""

    text: str

    def __iter__(self):  # pragma: no cover - trivial iterator glue
        return iter(self.tokens)

    @property
    def tokens(self) -> list[str]:
        return [token for token in self.text.split() if token]


class _SpaCyBackend:
    """Wrapper around a spaCy pipeline with graceful fallbacks."""

    def __init__(self, lang: str, module: Optional[object] = None) -> None:
        self.lang = lang
        self._module = module if module is not None else _optional_import("spacy")
        self._nlp = None

    @property
    def available(self) -> bool:
        return self._module is not None

    def __call__(self, text: str):
        if not self.available:
            return SimpleDoc(text)

        if self._nlp is None:
            self._nlp = self._load_pipeline()

        try:
            return self._nlp(text)
        except Exception:  # pragma: no cover - defensive, not expected in tests
            return SimpleDoc(text)

    def _load_pipeline(self):
        assert self._module is not None  # For type-checkers
        load = getattr(self._module, "load", None)
        blank = getattr(self._module, "blank", None)

        model_name = _default_spacy_model(self.lang)
        if load is not None:
            try:
                return load(model_name)
            except (OSError, IOError):
                pass

        if blank is not None:
            return blank(self.lang)

        # If spaCy was only partially available fall back to a simple document
        return lambda text: SimpleDoc(text)


class _StanzaBackend:
    """Wrapper around a Stanza pipeline with graceful fallbacks."""

    def __init__(self, lang: str, module: Optional[object] = None) -> None:
        self.lang = lang
        self._module = module if module is not None else _optional_import("stanza")
        self._pipeline = None

    @property
    def available(self) -> bool:
        return self._module is not None

    def __call__(self, text: str):
        if not self.available:
            return SimpleDoc(text)

        if self._pipeline is None:
            self._pipeline = self._load_pipeline()

        try:
            return self._pipeline(text)
        except Exception:  # pragma: no cover - defensive, not expected in tests
            return SimpleDoc(text)

    def _load_pipeline(self):
        assert self._module is not None  # For type-checkers
        pipeline_cls = getattr(self._module, "Pipeline", None)
        if pipeline_cls is None:
            return lambda text: SimpleDoc(text)

        try:
            return pipeline_cls(lang=self.lang, processors="tokenize,pos,lemma")
        except Exception:  # pragma: no cover - depends on external resources
            return lambda text: SimpleDoc(text)


class FastTextLanguageDetector:
    """Language detector backed by a fastText model."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        *,
        loader: Optional[Callable[[str], object]] = None,
    ) -> None:
        self.model_path = model_path
        self._loader = loader
        self._model = None

        if self._loader is None and model_path is not None:
            module = _optional_import("fasttext")
            if module is not None:
                self._loader = getattr(module, "load_model", None)

    @property
    def available(self) -> bool:
        return self.model_path is not None and self._loader is not None

    def __call__(self, text: str) -> Optional[str]:
        if not self.available:
            return None

        if self._model is None:
            self._model = self._loader(self.model_path)

        prediction = getattr(self._model, "predict", None)
        if prediction is None:
            return None

        labels, *_scores = prediction(text)
        if not labels:
            return None

        label = labels[0]
        if isinstance(label, bytes):
            label = label.decode("utf-8")
        if label.startswith("__label__"):
            label = label[len("__label__") :]
        return label or None


class TikaLanguageDetector:
    """Language detector that proxies ``tika.language.from_buffer``."""

    def __init__(self, detector: Optional[Callable[[str], str]] = None) -> None:
        if detector is not None:
            self._detector = detector
        else:
            module = _optional_import("tika.language")
            self._detector = getattr(module, "from_buffer", None) if module else None

    @property
    def available(self) -> bool:
        return self._detector is not None

    def __call__(self, text: str) -> Optional[str]:
        if not self.available:
            return None

        try:
            detected = self._detector(text)
        except Exception:  # pragma: no cover - defensive
            return None
        return detected or None


class SpacyNLP:
    """High-level NLP wrapper with automatic language selection."""

    def __init__(
        self,
        lang: str = "en",
        *,
        detectors: Optional[Iterable[LanguageDetector]] = None,
        spacy_factory: Callable[[str], _SpaCyBackend] = _SpaCyBackend,
        stanza_factory: Callable[[str], _StanzaBackend] = _StanzaBackend,
        fasttext_model_path: Optional[str] = None,
    ) -> None:
        self.lang = lang
        self._spacy_factory = spacy_factory
        self._stanza_factory = stanza_factory
        self._pipelines: dict[str, Callable[[str], object]] = {}

        if detectors is not None:
            self._detectors = list(detectors)
        else:
            self._detectors = []
            fasttext_detector = FastTextLanguageDetector(
                fasttext_model_path
            )
            if fasttext_detector.available:
                self._detectors.append(fasttext_detector)

            tika_detector = TikaLanguageDetector()
            if tika_detector.available:
                self._detectors.append(tika_detector)

    def __call__(self, text: str):
        language = self._resolve_language(text)
        backend = self._get_backend(language)
        return backend(text)

    def _resolve_language(self, text: str) -> str:
        if self.lang != "auto":
            return self.lang

        for detector in self._detectors:
            detected = detector(text)
            if detected:
                return detected

        return "en"

    def _get_backend(self, language: str):
        if language not in self._pipelines:
            if language == "en":
                backend = self._spacy_factory("en")
            else:
                backend = self._stanza_factory(language)
                if not getattr(backend, "available", False):
                    backend = self._spacy_factory(language)

            self._pipelines[language] = backend

        return self._pipelines[language]


def _optional_import(module_name: str) -> Optional[object]:
    """Attempt to import *module_name* returning ``None`` on failure."""

    try:
        spec = find_spec(module_name)
    except ModuleNotFoundError:
        return None

    if spec is None:
        return None

    try:
        return import_module(module_name)
    except Exception:  # pragma: no cover - import side-effects vary
        return None


def _default_spacy_model(lang: str) -> str:
    """Best effort mapping of language code to a spaCy model name."""

    if lang == "en":
        return "en_core_web_sm"
    if len(lang) == 2:
        return f"{lang}_core_news_sm"
    return lang


__all__ = [
    "FastTextLanguageDetector",
    "LanguageDetector",
    "SimpleDoc",
    "SpacyNLP",
    "TikaLanguageDetector",
]

