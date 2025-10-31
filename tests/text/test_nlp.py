from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.text.nlp import (
    FastTextLanguageDetector,
    SimpleDoc,
    SpacyNLP,
    TikaLanguageDetector,
)


@dataclass
class _TrackingBackend:
    name: str
    available: bool = True
    calls: list[str] = None

    def __post_init__(self) -> None:
        self.calls = [] if self.calls is None else self.calls

    def __call__(self, text: str):
        self.calls.append(text)
        return SimpleDoc(f"{self.name}:{text}")


def _backend_factory(prefix: str, store: dict[str, _TrackingBackend]) -> Callable[[str], _TrackingBackend]:
    def factory(lang: str) -> _TrackingBackend:
        backend = _TrackingBackend(name=f"{prefix}-{lang}")
        store[f"{prefix}-{lang}"] = backend
        return backend

    return factory


def test_spacynlp_auto_prefers_detector_language() -> None:
    store: dict[str, _TrackingBackend] = {}

    detectors = [lambda text: "es"]
    nlp = SpacyNLP(
        lang="auto",
        detectors=detectors,
        spacy_factory=_backend_factory("spacy", store),
        stanza_factory=_backend_factory("stanza", store),
    )

    doc = nlp("hola mundo")

    assert isinstance(doc, SimpleDoc)
    assert doc.text == "stanza-es:hola mundo"
    assert store["stanza-es"].calls == ["hola mundo"]
    assert "spacy-es" not in store  # stanza backend was selected


def test_spacynlp_auto_defaults_to_english_when_detection_fails() -> None:
    store: dict[str, _TrackingBackend] = {}

    nlp = SpacyNLP(
        lang="auto",
        detectors=[],
        spacy_factory=_backend_factory("spacy", store),
        stanza_factory=_backend_factory("stanza", store),
    )

    doc = nlp("just english text")

    assert doc.text == "spacy-en:just english text"
    assert store["spacy-en"].calls == ["just english text"]


def test_spacynlp_falls_back_to_spacy_when_stanza_unavailable() -> None:
    store: dict[str, _TrackingBackend] = {}

    def stanza_factory(lang: str) -> _TrackingBackend:
        backend = _TrackingBackend(name=f"stanza-{lang}", available=False)
        store[f"stanza-{lang}"] = backend
        return backend

    nlp = SpacyNLP(
        lang="auto",
        detectors=[lambda _: "fr"],
        spacy_factory=_backend_factory("spacy", store),
        stanza_factory=stanza_factory,
    )

    doc = nlp("bonjour")

    assert doc.text == "spacy-fr:bonjour"
    assert store["spacy-fr"].calls == ["bonjour"]


def test_fasttext_language_detector_uses_injected_loader() -> None:
    predictions = []

    class Model:
        def predict(self, text: str):
            predictions.append(text)
            return [["__label__es"], [0.9]]

    def loader(path: str) -> Model:
        assert path == "model.bin"
        return Model()

    detector = FastTextLanguageDetector(model_path="model.bin", loader=loader)

    assert detector.available is True
    detected = detector("hola mundo")
    assert detected == "es"
    assert predictions == ["hola mundo"]


def test_tika_language_detector_handles_missing_dependency() -> None:
    detector = TikaLanguageDetector()

    assert detector.available is False
    assert detector("anything") is None


def test_tika_language_detector_with_custom_callable() -> None:
    detector = TikaLanguageDetector(detector=lambda text: "de" if "hallo" in text else None)

    assert detector.available is True
    assert detector("hallo welt") == "de"

