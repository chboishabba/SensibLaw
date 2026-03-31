"""Shared affidavit candidate-alignment helpers."""
from __future__ import annotations

import re

from src.policy.affidavit_text_normalization import (
    predicate_focus_tokens,
    tokenize_affidavit_text,
)

QUOTE_REBUTTAL_SUPPORT_PATTERNS = (
    r"\bi acknowledge\b",
    r"\bi apolog",
    r"\bi regret",
    r"\bi understand this does not excuse\b",
    r"\bthis is corroborated\b",
    r"\bi confirm\b",
    r"\bi had only received\b",
    r"\bi am not .*attorney\b",
    r"\bi was forced to\b",
)

SIBLING_ACTION_FAMILY_RULES = (
    {
        "family": "audio_control",
        "claim_tokens": frozenset({"listen", "listening", "audio", "computer"}),
        "positive_tokens": frozenset({"listen", "listening", "audio", "computer", "pause", "paused", "turn", "stop", "off"}),
        "negative_tokens": frozenset({"keyboard", "type", "typed", "typing", "pulled", "remove", "removed"}),
    },
    {
        "family": "keyboard_control",
        "claim_tokens": frozenset({"keyboard", "type", "typed", "typing"}),
        "positive_tokens": frozenset({"keyboard", "type", "typed", "typing", "pulled", "remove", "removed"}),
        "negative_tokens": frozenset({"listen", "listening", "audio", "computer", "turn", "stop", "off", "pause", "paused"}),
    },
)

EPOA_REVOCATION_FAMILY_RULE = {
    "claim_tokens": frozenset({"epoa", "revoke", "revocation"}),
    "positive_tokens": frozenset({"revoke", "revocation", "attorney", "signature", "document", "documents", "received"}),
    "negative_tokens": frozenset({"rta", "tenancy", "filed", "dispute", "resolution", "landlord"}),
}


def predicate_alignment_score(proposition_text: str, excerpt_text: str) -> float:
    proposition_focus = predicate_focus_tokens(proposition_text)
    excerpt_focus = predicate_focus_tokens(excerpt_text)
    if not proposition_focus or not excerpt_focus:
        return 0.0
    shared = proposition_focus & excerpt_focus
    if not shared:
        return 0.0
    return round(len(shared) / len(proposition_focus), 6)


def is_quote_rebuttal_support_excerpt(excerpt_text: str) -> bool:
    excerpt = str(excerpt_text or "").strip()
    if not excerpt:
        return False
    return any(re.search(pattern, excerpt, flags=re.IGNORECASE) for pattern in QUOTE_REBUTTAL_SUPPORT_PATTERNS)


def family_alignment_adjustment(
    proposition_text: str,
    candidate_excerpt: str,
    row_text: str,
) -> float:
    proposition_tokens = tokenize_affidavit_text(proposition_text)
    candidate_tokens = tokenize_affidavit_text(candidate_excerpt)
    row_tokens = tokenize_affidavit_text(row_text)
    adjustment = 0.0
    predicate_alignment = predicate_alignment_score(proposition_text, candidate_excerpt)
    if predicate_alignment:
        adjustment += min(0.18, round(predicate_alignment * 0.18, 6))
    for rule in SIBLING_ACTION_FAMILY_RULES:
        claim_tokens = rule["claim_tokens"]
        if not (proposition_tokens & claim_tokens):
            continue
        negative_tokens = rule["negative_tokens"]
        if rule["family"] == "audio_control":
            control_tokens = {"turn", "stop", "off", "pause", "paused", "mute", "muted"}
            audio_tokens = {"listen", "listening", "audio", "computer"}
            candidate_has_positive = bool(candidate_tokens & control_tokens) and bool(candidate_tokens & audio_tokens)
            row_has_positive = bool(row_tokens & control_tokens) and bool(row_tokens & audio_tokens)
            candidate_has_negative = bool(candidate_tokens & negative_tokens) or (
                bool(candidate_tokens & audio_tokens) and not candidate_has_positive
            )
        else:
            candidate_has_positive = bool(candidate_tokens & {"keyboard", "type", "typed", "typing"})
            if "keyboard" in candidate_tokens and bool(candidate_tokens & {"pulled", "remove", "removed"}):
                candidate_has_positive = True
            row_has_positive = bool(row_tokens & {"keyboard", "type", "typed", "typing"})
            if "keyboard" in row_tokens and bool(row_tokens & {"pulled", "remove", "removed"}):
                row_has_positive = True
            candidate_has_negative = bool(candidate_tokens & negative_tokens)
        if candidate_has_positive:
            adjustment += 0.12
        elif candidate_has_negative:
            adjustment -= 0.12
        elif is_quote_rebuttal_support_excerpt(candidate_excerpt) and row_has_positive:
            adjustment += 0.14
        elif predicate_alignment == 0.0:
            adjustment -= 0.08
        break

    if proposition_tokens & EPOA_REVOCATION_FAMILY_RULE["claim_tokens"]:
        positive_tokens = EPOA_REVOCATION_FAMILY_RULE["positive_tokens"]
        negative_tokens = EPOA_REVOCATION_FAMILY_RULE["negative_tokens"]
        candidate_has_positive = bool(candidate_tokens & positive_tokens)
        candidate_has_negative = bool(candidate_tokens & negative_tokens)
        row_has_positive = bool(row_tokens & positive_tokens)
        excerpt_is_strong_confirmation = is_quote_rebuttal_support_excerpt(candidate_excerpt)
        if candidate_has_positive:
            adjustment += 0.14 if excerpt_is_strong_confirmation else 0.1
        elif candidate_has_negative:
            adjustment -= 0.12
        elif excerpt_is_strong_confirmation and row_has_positive:
            adjustment += 0.12

    return adjustment


__all__ = [
    "family_alignment_adjustment",
    "is_quote_rebuttal_support_excerpt",
    "predicate_alignment_score",
]
