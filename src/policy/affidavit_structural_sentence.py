"""Shared parser-facing structural sentence adapter."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

HEDGE_VERBS = {"feel", "believe", "think", "recall"}


@lru_cache(maxsize=32768)
def analyze_structural_sentence(
    text: str,
    *,
    dependencies_getter: Callable[[str], Any] | None,
) -> dict[str, Any]:
    if dependencies_getter is None:
        return {}
    try:
        sentences = dependencies_getter(text)
    except Exception:
        return {}
    if not sentences:
        return {}
    first = sentences[0]
    candidates = getattr(first, "candidates", {}) or {}
    subjects = list(candidates.get("nsubj", [])) + list(candidates.get("nsubjpass", []))
    verbs = list(candidates.get("verb", []))
    negations = list(candidates.get("neg", []))
    subject_texts = [str(getattr(item, "text", "") or "").strip() for item in subjects if str(getattr(item, "text", "") or "").strip()]
    verb_lemmas = [str(getattr(item, "lemma", "") or getattr(item, "text", "") or "").strip().lower() for item in verbs]
    return {
        "subject_texts": subject_texts,
        "verb_lemmas": verb_lemmas,
        "has_negation": bool(negations),
        "has_first_person_subject": any(text.casefold() == "i" for text in subject_texts),
        "has_hedge_verb": any(lemma in HEDGE_VERBS for lemma in verb_lemmas),
    }


__all__ = [
    "HEDGE_VERBS",
    "analyze_structural_sentence",
]
