from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import pytest

from src.rules.extractor import _split_sentences

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load_samples() -> Iterable[tuple[str, dict]]:
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        yield path.stem, json.loads(path.read_text())


SAMPLES = list(_load_samples())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+(?:'\w+)?\b", text)


@pytest.mark.parametrize(("name", "data"), SAMPLES)
def test_sentence_segmentation_and_tokenization(name: str, data: dict) -> None:
    expected_sentences = [entry["text"] for entry in data["sentences"]]
    actual_sentences = list(_split_sentences(data["text"]))

    assert actual_sentences == expected_sentences

    for sentence, expected in zip(actual_sentences, data["sentences"]):
        tokens = _tokenize(sentence)
        assert tokens == expected["tokens"]
        assert len(tokens) == len(expected["tokens"])
