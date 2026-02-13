from __future__ import annotations

from src.nlp.ontology_mapping import canonical_action_morphology, unknown_action_morphology


class _DummyMorph:
    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    def get(self, name: str):
        return self._mapping.get(name, [])


class _DummyToken:
    def __init__(
        self,
        *,
        text: str = "",
        dep: str = "",
        morph: dict[str, list[str]] | None = None,
        children: list[object] | None = None,
    ) -> None:
        self.text = text
        self.dep_ = dep
        self.morph = _DummyMorph(morph or {})
        self.children = children or []


def test_canonical_action_morphology_maps_spacy_style_values() -> None:
    child = _DummyToken(dep="auxpass")
    tok = _DummyToken(
        text="estimated",
        dep="ROOT",
        morph={
            "Tense": ["Past"],
            "Aspect": ["Perf", "Prog"],
            "VerbForm": ["Fin"],
            "Mood": ["Ind"],
        },
        children=[child],
    )
    meta = canonical_action_morphology(tok, surface="estimated", source="dep_lemma", modality_hint="estimated")
    assert meta["tense"] == "past"
    assert meta["aspect"] == "perfect_progressive"
    assert meta["verb_form"] == "finite"
    assert meta["mood"] == "indicative"
    assert meta["voice"] == "passive"
    assert meta["modality"] == "estimated"


def test_canonical_action_morphology_defaults_unknown_and_asserted() -> None:
    tok = _DummyToken(text="turning", dep="ROOT", morph={}, children=[])
    meta = canonical_action_morphology(tok, surface="turning", source="dep_lemma", modality_hint="not_real")
    assert meta["tense"] == "unknown"
    assert meta["aspect"] == "unknown"
    assert meta["verb_form"] == "unknown"
    assert meta["mood"] == "unknown"
    assert meta["voice"] == "active"
    assert meta["modality"] == "asserted"


def test_unknown_action_morphology_is_canonical_shape() -> None:
    meta = unknown_action_morphology(surface="reported", source="fallback:action_lemmas")
    assert meta == {
        "surface": "reported",
        "tense": "unknown",
        "aspect": "unknown",
        "verb_form": "unknown",
        "voice": "unknown",
        "mood": "unknown",
        "modality": "asserted",
        "source": "fallback:action_lemmas",
    }
