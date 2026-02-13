from __future__ import annotations

from typing import Dict, Optional

_TENSE_MAP = {
    "past": "past",
    "pres": "present",
    "fut": "future",
}

_VERB_FORM_MAP = {
    "fin": "finite",
    "inf": "infinitive",
    "part": "participle",
    "ger": "gerund",
}

_MOOD_MAP = {
    "ind": "indicative",
    "cnd": "conditional",
    "imp": "imperative",
    "sub": "subjunctive",
}

_MODALITY_VALUES = {
    "asserted",
    "reported",
    "projected",
    "estimated",
    "alleged",
    "inferred",
}


def _morph_values(token: object, name: str) -> list[str]:
    morph = getattr(token, "morph", None)
    if morph is None:
        return []
    try:
        vals = morph.get(name)
    except Exception:
        return []
    out: list[str] = []
    for v in vals or []:
        s = str(v or "").strip().lower()
        if s:
            out.append(s)
    return out


def canonical_action_morphology(
    token: Optional[object],
    *,
    surface: str = "",
    source: str = "dep_lemma",
    modality_hint: Optional[str] = None,
) -> Dict[str, str]:
    """
    Parser-agnostic canonical mapping for ActionEvent morphology.

    Returns canonical enum values only (never raw spaCy values).
    """
    if token is None:
        return unknown_action_morphology(surface=surface, source=source, modality_hint=modality_hint)

    verb_form_raw = _morph_values(token, "VerbForm")
    tense_raw = _morph_values(token, "Tense")
    aspect_raw = set(_morph_values(token, "Aspect"))
    mood_raw = _morph_values(token, "Mood")

    verb_form = "unknown"
    for raw in verb_form_raw:
        mapped = _VERB_FORM_MAP.get(raw)
        if mapped:
            verb_form = mapped
            break

    tense = "unknown"
    for raw in tense_raw:
        mapped = _TENSE_MAP.get(raw)
        if mapped:
            tense = mapped
            break

    mood = "unknown"
    for raw in mood_raw:
        mapped = _MOOD_MAP.get(raw)
        if mapped:
            mood = mapped
            break

    if "perf" in aspect_raw and "prog" in aspect_raw:
        aspect = "perfect_progressive"
    elif "perf" in aspect_raw:
        aspect = "perfect"
    elif "prog" in aspect_raw:
        aspect = "progressive"
    elif verb_form != "unknown":
        aspect = "simple"
    else:
        aspect = "unknown"

    dep = str(getattr(token, "dep_", "") or "").strip().lower()
    children = list(getattr(token, "children", []) or [])
    passive = dep == "auxpass" or any(
        str(getattr(c, "dep_", "") or "").strip().lower() in {"auxpass", "nsubjpass"}
        for c in children
    )
    voice = "passive" if passive else "active"

    modality = str(modality_hint or "").strip().lower() or "asserted"
    if modality not in _MODALITY_VALUES:
        modality = "asserted"

    return {
        "surface": str(surface or getattr(token, "text", "") or ""),
        "tense": tense,
        "aspect": aspect,
        "verb_form": verb_form,
        "voice": voice,
        "mood": mood,
        "modality": modality,
        "source": str(source or "dep_lemma"),
    }


def unknown_action_morphology(
    *,
    surface: str = "",
    source: str = "fallback",
    modality_hint: Optional[str] = None,
) -> Dict[str, str]:
    modality = str(modality_hint or "").strip().lower() or "asserted"
    if modality not in _MODALITY_VALUES:
        modality = "asserted"
    return {
        "surface": str(surface or ""),
        "tense": "unknown",
        "aspect": "unknown",
        "verb_form": "unknown",
        "voice": "unknown",
        "mood": "unknown",
        "modality": modality,
        "source": str(source or "fallback"),
    }


__all__ = ["canonical_action_morphology", "unknown_action_morphology"]
