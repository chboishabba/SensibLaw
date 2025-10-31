import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.pipeline import NormalisedText, normalise


def test_normalise_enriches_tokens() -> None:
    text = "We are RUNNING to the members."
    normalised = normalise(text)

    assert isinstance(normalised, NormalisedText)
    assert isinstance(normalised, str)
    assert str(normalised) == "we are running to the members."

    tokens = list(normalised.tokens)
    assert len(tokens) == 7

    we = tokens[0]
    assert we.text == "we"
    assert we.pos_ == "PRON"
    assert "PronType" in we.morph
    assert we._.class_ is None

    running = next(token for token in tokens if token.text == "running")
    assert running.lemma_ == "run"
    assert running.pos_ == "VERB"
    assert "VerbForm" in running.morph

    members = next(token for token in tokens if token.text == "members")
    assert members.lemma_ == "member"
    assert members.morph.startswith("Number=")

    serialised = running.as_dict()
    assert serialised["lemma_"] == "run"
    assert "pos_" in serialised and serialised["pos_"] == "VERB"
    assert "class_" in serialised and serialised["class_"] is None

    we._.class_ = "actor"
    assert we._.class_ == "actor"
