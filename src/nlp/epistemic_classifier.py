from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PredicateType(str, Enum):
    EVENTIVE = "eventive"
    EPISTEMIC = "epistemic"
    NORMATIVE = "normative"
    PROCEDURAL = "procedural"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassificationResult:
    predicate_type: PredicateType
    confidence: float
    features: Dict[str, Any]


class EpistemicClassifier:
    """
    Deterministic hybrid predicate classifier.

    Phase-1 behavior:
    - dependency signals (ccomp/xcomp) are primary epistemic evidence
    - lexical semantics (WordNet lexname when available) adds epistemic support
    - modal/deontic cues add normative support
    - concrete object cues add eventive support
    """

    _MODAL_AUX = {"must", "should", "shall", "may", "might", "can", "could", "ought"}
    _DEONTIC_LEMMAS = {"require", "permit", "prohibit", "oblige", "mandate"}
    _PROCEDURAL_LEMMAS = {"file", "submit", "apply", "serve", "issue", "enter", "record", "register"}
    _NORMATIVE_CUE_LEMMAS = {
        "must",
        "should",
        "shall",
        "require",
        "required",
        "permit",
        "permitted",
        "prohibit",
        "prohibited",
        "section",
    }

    def __init__(self, nlp: Optional[object]) -> None:
        self.nlp = nlp

    def classify(self, sentence: str, verb_token_index: int) -> ClassificationResult:
        if self.nlp is None:
            return ClassificationResult(
                predicate_type=PredicateType.UNKNOWN,
                confidence=0.0,
                features={"reason": "nlp_unavailable"},
            )
        doc = self.nlp(str(sentence or ""))
        return self.classify_from_doc(doc, verb_token_index)

    def classify_from_doc(self, doc: object, verb_token_index: int) -> ClassificationResult:
        try:
            idx = int(verb_token_index)
        except Exception:
            idx = -1
        if idx < 0 or idx >= len(doc):
            return ClassificationResult(
                predicate_type=PredicateType.UNKNOWN,
                confidence=0.0,
                features={"reason": "invalid_token_index", "verb_token_index": verb_token_index},
            )
        tok = doc[idx]
        return self._classify_token(doc, tok)

    def _classify_token(self, doc: object, tok: object) -> ClassificationResult:
        score: Dict[PredicateType, float] = {
            PredicateType.EPISTEMIC: 0.0,
            PredicateType.EVENTIVE: 0.0,
            PredicateType.NORMATIVE: 0.0,
            PredicateType.PROCEDURAL: 0.0,
        }
        features: Dict[str, Any] = {}

        pos = str(getattr(tok, "pos_", "") or "")
        lemma = str(getattr(tok, "lemma_", "") or "").strip().lower()
        features["token_text"] = str(getattr(tok, "text", "") or "")
        features["token_lemma"] = lemma
        features["token_pos"] = pos

        has_clause = any(str(getattr(ch, "dep_", "") or "") in {"ccomp", "xcomp"} for ch in getattr(tok, "children", []))
        features["has_clausal_complement"] = bool(has_clause)
        if has_clause:
            score[PredicateType.EPISTEMIC] += 3.0

        lexname = self._wordnet_lexname(tok)
        features["wordnet_lexname"] = lexname
        if lexname in {"verb.communication", "verb.cognition"}:
            score[PredicateType.EPISTEMIC] += 2.0

        modal_detected = self._has_modal_aux(tok)
        deontic_lemma = lemma in self._DEONTIC_LEMMAS
        normative_text = self._has_normative_text_cue(doc)
        features["modal_detected"] = bool(modal_detected)
        features["deontic_lemma"] = bool(deontic_lemma)
        features["normative_text_pattern"] = bool(normative_text)
        if modal_detected or deontic_lemma:
            score[PredicateType.NORMATIVE] += 3.0
        elif normative_text:
            score[PredicateType.NORMATIVE] += 1.0

        procedural_lemma = lemma in self._PROCEDURAL_LEMMAS
        features["procedural_lemma"] = bool(procedural_lemma)
        if procedural_lemma:
            score[PredicateType.PROCEDURAL] += 2.0

        has_concrete_object = self._has_concrete_object(tok)
        features["has_concrete_object"] = bool(has_concrete_object)
        if has_concrete_object:
            score[PredicateType.EVENTIVE] += 2.0
        if pos == "VERB" and not has_clause:
            score[PredicateType.EVENTIVE] += 1.0

        positive = {k: v for k, v in score.items() if v > 0}
        features["score"] = {k.value: float(v) for k, v in score.items()}
        if not positive:
            return ClassificationResult(
                predicate_type=PredicateType.UNKNOWN,
                confidence=0.0,
                features=features,
            )

        order = [
            PredicateType.EPISTEMIC,
            PredicateType.NORMATIVE,
            PredicateType.PROCEDURAL,
            PredicateType.EVENTIVE,
        ]
        best = max(order, key=lambda t: (score[t], -order.index(t)))
        total = sum(positive.values())
        confidence = float(score[best] / total) if total > 0 else 0.0
        return ClassificationResult(predicate_type=best, confidence=confidence, features=features)

    def _wordnet_lexname(self, tok: object) -> Optional[str]:
        # Optional signal: only if spacy-wordnet extension is installed and available.
        try:
            underscore = getattr(tok, "_", None)
            if underscore is None:
                return None
            wn = getattr(underscore, "wordnet", None)
            if wn is None:
                return None
            synsets = wn.synsets()
            if not synsets:
                return None
            syn = synsets[0]
            if syn is None:
                return None
            return str(syn.lexname() or "").strip() or None
        except Exception:
            return None

    def _has_modal_aux(self, tok: object) -> bool:
        for ch in getattr(tok, "children", []):
            dep = str(getattr(ch, "dep_", "") or "")
            if dep not in {"aux", "auxpass"}:
                continue
            lemma = str(getattr(ch, "lemma_", "") or getattr(ch, "text", "") or "").strip().lower()
            if lemma in self._MODAL_AUX:
                return True
        return False

    def _has_concrete_object(self, tok: object) -> bool:
        for ch in getattr(tok, "children", []):
            dep = str(getattr(ch, "dep_", "") or "")
            if dep not in {"obj", "dobj", "pobj", "attr", "oprd"}:
                continue
            pos = str(getattr(ch, "pos_", "") or "")
            if pos in {"NOUN", "PROPN", "NUM"}:
                return True
        return False

    def _has_normative_text_cue(self, doc: object) -> bool:
        prev_lemma = ""
        for tok in doc:
            lemma = str(getattr(tok, "lemma_", "") or getattr(tok, "text", "") or "").strip().lower()
            if not lemma:
                continue
            if lemma in self._NORMATIVE_CUE_LEMMAS:
                return True
            if prev_lemma == "under" and lemma == "section":
                return True
            prev_lemma = lemma
        return False


__all__ = ["ClassificationResult", "EpistemicClassifier", "PredicateType"]
