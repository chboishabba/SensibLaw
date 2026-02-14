from __future__ import annotations

from src.nlp.event_classifier import EventClassifier
from src.nlp.synset_mapper import DeterministicSynsetActionMapper


class _FakeMorph:
    def __init__(self, verb_form: str = ""):
        self._verb_form = verb_form

    def get(self, key: str):
        if key == "VerbForm" and self._verb_form:
            return [self._verb_form]
        return []


class _FakeToken:
    def __init__(self, text: str, lemma: str, pos: str, dep: str = "", idx: int = 0, verb_form: str = ""):
        self.text = text
        self.lemma_ = lemma
        self.pos_ = pos
        self.dep_ = dep
        self.idx = idx
        self.morph = _FakeMorph(verb_form=verb_form)
        self.children = []


class _FakeDoc:
    def __init__(self, tokens):
        self._tokens = tokens

    def __iter__(self):
        return iter(self._tokens)

    def __getitem__(self, idx):
        return self._tokens[idx]

    def __len__(self):
        return len(self._tokens)


def test_event_classifier_prefers_verb_draw_over_nominal_death() -> None:
    death = _FakeToken("death", "death", "NOUN", dep="pobj", idx=15)
    draw = _FakeToken("drew", "draw", "VERB", dep="ROOT", idx=60, verb_form="Fin")
    doc = _FakeDoc([death, draw])
    classifier = EventClassifier({"died": ("die",), "drew": ("draw",)})
    match = classifier.classify_from_doc(doc)
    assert match is not None
    assert match.action_label == "drew"
    assert match.action_lemma == "draw"


def test_event_classifier_disambiguates_commission_into() -> None:
    commission = _FakeToken("commissioned", "commission", "VERB", dep="ROOT", idx=8, verb_form="Fin")
    into = _FakeToken("into", "into", "ADP", dep="prep", idx=20)
    commission.children = [into]
    doc = _FakeDoc([commission, into])
    classifier = EventClassifier(
        {
            "commissioned": ("commission",),
            "commissioned_into": ("commission",),
        }
    )
    match = classifier.classify_from_doc(doc)
    assert match is not None
    assert match.action_label == "commissioned_into"


def test_event_classifier_falls_back_to_synset_mapping_when_lemma_unmapped() -> None:
    # "perish" not in lemma map, but synset map can supply a canonical action.
    perish = _FakeToken("perished", "perish", "VERB", dep="ROOT", idx=0, verb_form="Fin")
    doc = _FakeDoc([perish])

    mapper = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map={"bn:death": "died"},
        babelnet_lemma_synsets={"perish": ["bn:death"]},
    )
    classifier = EventClassifier({"died": ("die",)}, synset_mapper=mapper)
    match = classifier.classify_from_doc(doc)
    assert match is not None
    assert match.action_label == "died"


def test_event_classifier_abstains_on_multi_action_synset_ambiguity() -> None:
    perish = _FakeToken("perished", "perish", "VERB", dep="ROOT", idx=0, verb_form="Fin")
    doc = _FakeDoc([perish])

    mapper = DeterministicSynsetActionMapper(
        resource="babelnet",
        wsd_policy="rule_deterministic",
        version_pins={},
        synset_action_map={"bn:a": "died", "bn:b": "entered"},
        babelnet_lemma_synsets={"perish": ["bn:a", "bn:b"]},
    )
    classifier = EventClassifier({"died": ("die",), "entered": ("enter",)}, synset_mapper=mapper)
    match = classifier.classify_from_doc(doc)
    assert match is None
