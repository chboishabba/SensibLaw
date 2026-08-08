from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.nlp import spacy_adapter


@dataclass
class _Pipeline:
    pipe_names: tuple[str, ...]

    def add_pipe(self, name: str, config: object | None = None) -> object:
        del config
        self.pipe_names = (*self.pipe_names, name)
        return object()

    def remove_pipe(self, name: str) -> None:
        self.pipe_names = tuple(item for item in self.pipe_names if item != name)


class _MissingModelSpacy:
    def load(self, model_name: str, disable: list[str] | None = None) -> object:
        del model_name, disable
        raise OSError("missing model")

    def blank(self, language: str) -> object:
        raise AssertionError(f"strict path must not call blank({language!r})")


def test_strict_pipeline_requires_parser_and_pos_components() -> None:
    with pytest.raises(
        RuntimeError,
        match="parser, tagger-or-morphologizer",
    ):
        spacy_adapter._require_syntax_pipeline(
            _Pipeline(()),
            model_name="test-model",
        )


def test_strict_pipeline_accepts_parser_and_morphologizer() -> None:
    spacy_adapter._require_syntax_pipeline(
        _Pipeline(("parser", "morphologizer")),
        model_name="test-model",
    )


def test_strict_model_load_never_degrades_to_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        spacy_adapter,
        "_import_spacy",
        lambda: _MissingModelSpacy(),
    )
    monkeypatch.setenv("SENSIBLAW_SPACY_MODEL", "missing-model")

    with pytest.raises(
        RuntimeError,
        match="requires an installed syntax-capable spaCy model",
    ):
        spacy_adapter._load_pipeline(
            include_entities=True,
            require_syntax=True,
        )
