from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SynsetActionMatch:
    action_label: str
    synset_id: str
    resource: str
    confidence: float
    features: Dict[str, Any]


class DeterministicSynsetActionMapper:
    """
    Deterministic, version-pinned synset -> action mapper.

    - WordNet: local NLTK corpus only, version must match configured pin.
    - BabelNet: deterministic lemma -> synset-id table must be provided in profile.
    - No probabilistic/generative WSD path.
    """

    _RESOURCE_ORDER = ("wordnet", "babelnet")

    def __init__(
        self,
        *,
        resource: str,
        wsd_policy: str,
        version_pins: Optional[Dict[str, str]] = None,
        synset_action_map: Optional[Dict[str, str]] = None,
        babelnet_lemma_synsets: Optional[Dict[str, Sequence[str]]] = None,
    ) -> None:
        self._resource = str(resource or "none").strip().lower()
        self._wsd_policy = str(wsd_policy or "none").strip().lower()
        self._version_pins = {str(k).strip().lower(): str(v).strip() for k, v in (version_pins or {}).items() if str(k).strip() and str(v).strip()}
        self._synset_action_map = {
            str(k).strip().lower(): str(v).strip()
            for k, v in (synset_action_map or {}).items()
            if str(k).strip() and str(v).strip()
        }
        self._babelnet_lemma_synsets = {
            str(k).strip().lower(): sorted(
                {str(x).strip().lower() for x in (v or []) if str(x).strip()}
            )
            for k, v in (babelnet_lemma_synsets or {}).items()
            if str(k).strip()
        }
        self._wordnet = None
        self._wordnet_version: Optional[str] = None

        resources = self._resource_set()
        if "wordnet" in resources:
            self._wordnet, self._wordnet_version = self._load_wordnet()

    def metadata(self) -> Dict[str, Any]:
        return {
            "resource": self._resource,
            "wsd_policy": self._wsd_policy,
            "version_pins": dict(self._version_pins),
            "wordnet_version": self._wordnet_version,
            "synset_action_count": int(len(self._synset_action_map)),
        }

    def resolve_action(self, tok: object) -> Optional[SynsetActionMatch]:
        lemma = str(getattr(tok, "lemma_", "") or getattr(tok, "text", "") or "").strip().lower()
        if not lemma:
            return None
        for res in self._resource_sequence():
            if res == "wordnet":
                out = self._resolve_wordnet(lemma, tok)
                if out is not None:
                    return out
            elif res == "babelnet":
                out = self._resolve_babelnet(lemma)
                if out is not None:
                    return out
        return None

    def _resource_set(self) -> set[str]:
        if self._resource == "none":
            return set()
        if self._resource == "wordnet+babelnet":
            return {"wordnet", "babelnet"}
        return {self._resource}

    def _resource_sequence(self) -> List[str]:
        s = self._resource_set()
        return [r for r in self._RESOURCE_ORDER if r in s]

    def _load_wordnet(self) -> Tuple[Any, str]:
        try:
            from nltk.corpus import wordnet as wn  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency contingent
            raise RuntimeError(f"wordnet_unavailable:{type(exc).__name__}") from exc
        version = ""
        try:
            version = str(wn.get_version() or "").strip()
        except Exception:
            version = ""
        if not version:
            raise RuntimeError("wordnet_version_unknown")
        pin = str(self._version_pins.get("wordnet") or "").strip()
        if pin and version != pin:
            raise RuntimeError(f"wordnet_version_pin_mismatch:{pin}:{version}")
        return wn, version

    def _resolve_wordnet(self, lemma: str, tok: object) -> Optional[SynsetActionMatch]:
        if self._wordnet is None:
            return None
        wn = self._wordnet
        wn_pos = wn.VERB if str(getattr(tok, "pos_", "") or "") in {"VERB", "AUX"} else None
        synsets = wn.synsets(lemma, pos=wn_pos) if wn_pos is not None else wn.synsets(lemma)
        if not synsets:
            return None
        candidates = sorted(self._wordnet_synset_id(s) for s in synsets)
        return self._select_single_action_or_abstain(candidates, resource="wordnet")

    def _resolve_babelnet(self, lemma: str) -> Optional[SynsetActionMatch]:
        synsets = self._babelnet_lemma_synsets.get(lemma) or []
        if not synsets:
            return None
        candidates = sorted({str(s or "").strip().lower() for s in synsets if str(s or "").strip()})
        return self._select_single_action_or_abstain(candidates, resource="babelnet")

    def _select_single_action_or_abstain(self, synset_ids: Sequence[str], *, resource: str) -> Optional[SynsetActionMatch]:
        mapped: List[Tuple[str, str]] = []
        for sid in synset_ids:
            key = str(sid or "").strip().lower()
            if not key:
                continue
            label = self._synset_action_map.get(key)
            if not label:
                continue
            mapped.append((key, label))
        if not mapped:
            return None

        actions = sorted({lab for _, lab in mapped})
        if len(actions) != 1:
            # Multiple competing canonical actions -> abstain in canonical path.
            return None

        chosen_action = actions[0]
        supporting = min([sid for sid, lab in mapped if lab == chosen_action])
        return SynsetActionMatch(
            action_label=chosen_action,
            synset_id=supporting,
            resource=str(resource),
            confidence=0.83 if resource == "wordnet" else 0.8,
            features={"rule": f"{resource}_synset_map", "mapped_candidates": mapped},
        )

    @staticmethod
    def _wordnet_synset_id(synset: Any) -> str:
        try:
            return f"wn:{int(synset.offset()):08d}-{str(synset.pos())}"
        except Exception:  # pragma: no cover - defensive
            return str(synset).strip().lower()
