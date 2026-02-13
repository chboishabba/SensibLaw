from __future__ import annotations

from src.nlp.epistemic_classifier import EpistemicClassifier, PredicateType


class _FakeWordNet:
    def synsets(self):
        return []


class _FakeUnderscore:
    def __init__(self):
        self.wordnet = _FakeWordNet()


class _FakeToken:
    def __init__(self, text: str, lemma: str, pos: str, dep: str = ""):
        self.text = text
        self.lemma_ = lemma
        self.pos_ = pos
        self.dep_ = dep
        self.children = []
        self._ = _FakeUnderscore()


class _FakeDoc:
    def __init__(self, tokens):
        self._tokens = tokens
        self.text = " ".join(t.text for t in tokens)

    def __len__(self):
        return len(self._tokens)

    def __getitem__(self, idx):
        return self._tokens[idx]

    def __iter__(self):
        return iter(self._tokens)


def test_classifier_marks_epistemic_from_clausal_complement() -> None:
    root = _FakeToken("reported", "report", "VERB")
    ccomp = _FakeToken("approved", "approve", "VERB", dep="ccomp")
    root.children = [ccomp]
    doc = _FakeDoc([root, ccomp])
    cls = EpistemicClassifier(None).classify_from_doc(doc, 0)
    assert cls.predicate_type == PredicateType.EPISTEMIC
    assert cls.features["has_clausal_complement"] is True


def test_classifier_marks_normative_from_modal_aux() -> None:
    root = _FakeToken("comply", "comply", "VERB")
    aux = _FakeToken("must", "must", "AUX", dep="aux")
    root.children = [aux]
    doc = _FakeDoc([aux, root])
    cls = EpistemicClassifier(None).classify_from_doc(doc, 1)
    assert cls.predicate_type == PredicateType.NORMATIVE
    assert cls.features["modal_detected"] is True


def test_classifier_marks_eventive_from_object_signal() -> None:
    root = _FakeToken("signed", "sign", "VERB")
    obj = _FakeToken("order", "order", "NOUN", dep="obj")
    root.children = [obj]
    doc = _FakeDoc([root, obj])
    cls = EpistemicClassifier(None).classify_from_doc(doc, 0)
    assert cls.predicate_type == PredicateType.EVENTIVE
    assert cls.features["has_concrete_object"] is True

