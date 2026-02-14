from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .synset_mapper import DeterministicSynsetActionMapper


@dataclass(frozen=True)
class EventActionMatch:
    action_label: str
    action_lemma: str
    token_index: int
    start_char: int
    confidence: float
    features: Dict[str, Any]


class EventClassifier:
    """
    spaCy-first action classifier for AAO action labels.

    Classification priority:
    1) verb/aux token lemma mapping to configured action labels
    2) deterministic dependency disambiguation for ambiguous lemmas
    3) ordered fallback by label priority
    """

    _TOKEN_POS = {"VERB", "AUX"}

    def __init__(
        self,
        action_lemmas: Dict[str, Tuple[str, ...]],
        *,
        synset_mapper: Optional[DeterministicSynsetActionMapper] = None,
    ) -> None:
        self._action_lemmas = dict(action_lemmas or {})
        self._label_order = list(self._action_lemmas.keys())
        self._synset_mapper = synset_mapper
        lemma_to_labels: Dict[str, List[str]] = {}
        for label in self._label_order:
            for lemma in self._action_lemmas.get(label, ()):
                key = str(lemma or "").strip().lower()
                if not key:
                    continue
                lemma_to_labels.setdefault(key, [])
                if label not in lemma_to_labels[key]:
                    lemma_to_labels[key].append(label)
        self._lemma_to_labels = lemma_to_labels

    def classify_from_doc(self, doc: object) -> Optional[EventActionMatch]:
        cands = self.collect_candidates(doc)
        if not cands:
            return None
        return cands[0]

    def collect_candidates(self, doc: object) -> List[EventActionMatch]:
        if doc is None:
            return []
        out: List[EventActionMatch] = []
        for i, tok in enumerate(doc):
            pos = str(getattr(tok, "pos_", "") or "")
            if pos not in self._TOKEN_POS:
                continue
            lemma = str(getattr(tok, "lemma_", "") or getattr(tok, "text", "") or "").strip().lower()
            if not lemma:
                continue
            resolved = self._resolve_label(tok, lemma)
            if not resolved:
                continue
            label, confidence, feat = resolved
            start_char = int(getattr(tok, "idx", -1))
            if start_char < 0:
                start_char = i
            out.append(
                EventActionMatch(
                    action_label=label,
                    action_lemma=lemma,
                    token_index=i,
                    start_char=start_char,
                    confidence=float(confidence),
                    features=feat,
                )
            )
        out.sort(key=lambda m: self._rank_match(doc, m))
        dedup: List[EventActionMatch] = []
        seen = set()
        for m in out:
            key = (int(m.token_index), str(m.action_label))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(m)
        return dedup

    def _rank_match(self, doc: object, match: EventActionMatch) -> Tuple[int, int, int]:
        tok = doc[int(match.token_index)]
        dep = str(getattr(tok, "dep_", "") or "")
        root_rank = 0 if dep == "ROOT" else 1
        finite_rank = 0 if self._is_finite(tok) else 1
        idx_rank = int(match.start_char)
        return (root_rank, finite_rank, idx_rank)

    def _is_finite(self, tok: object) -> bool:
        morph = getattr(tok, "morph", None)
        if morph is None:
            return False
        try:
            vals = morph.get("VerbForm")
        except Exception:
            vals = []
        return any(str(v).lower() == "fin" for v in (vals or []))

    def _resolve_label(self, tok: object, lemma: str) -> Optional[Tuple[str, float, Dict[str, Any]]]:
        labels = list(self._lemma_to_labels.get(lemma) or [])
        if not labels:
            # Profile-gated synset mapping fallback (deterministic, version-pinned).
            if self._synset_mapper is not None:
                try:
                    syn = self._synset_mapper.resolve_action(tok)
                except Exception:
                    syn = None
                if syn is not None:
                    return syn.action_label, float(syn.confidence), {"rule": "synset_map", "synset_id": syn.synset_id, "resource": syn.resource}
            return None

        # Deterministic dependency disambiguation for known ambiguous lemmas.
        if lemma == "commission":
            if self._has_prep_into(tok):
                return "commissioned_into", 0.96, {"rule": "commission_into"}
            if "commissioned" in labels:
                return "commissioned", 0.92, {"rule": "commission_default"}

        if lemma == "give":
            if self._has_child_lemma(tok, {"birth"}):
                return "gave_birth", 0.96, {"rule": "give_birth"}
            if self._has_child_lemma(tok, {"speech"}):
                return "gave_speech", 0.96, {"rule": "give_speech"}
            # avoid false semantic coercion for generic "give" usages
            return None

        # Stable first-label choice by configured action label order.
        for label in self._label_order:
            if label in labels:
                return label, 0.9, {"rule": "lemma_map"}
        return labels[0], 0.85, {"rule": "lemma_map_fallback"}

    def _has_child_lemma(self, tok: object, lemmas: Sequence[str]) -> bool:
        wanted = {str(x).strip().lower() for x in lemmas if str(x).strip()}
        if not wanted:
            return False
        for ch in getattr(tok, "children", []):
            clem = str(getattr(ch, "lemma_", "") or getattr(ch, "text", "") or "").strip().lower()
            if clem in wanted:
                return True
        return False

    def _has_prep_into(self, tok: object) -> bool:
        for ch in getattr(tok, "children", []):
            dep = str(getattr(ch, "dep_", "") or "")
            txt = str(getattr(ch, "text", "") or "").strip().lower()
            lem = str(getattr(ch, "lemma_", "") or "").strip().lower()
            if dep in {"prep", "prt", "mark"} and (txt == "into" or lem == "into"):
                return True
        return False
