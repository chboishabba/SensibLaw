"""Shared affidavit duplicate-response and claim-root helpers."""
from __future__ import annotations

import hashlib

from src.policy.affidavit_text_normalization import tokenize_affidavit_text


def is_duplicate_response_excerpt(proposition_text: str, excerpt_text: str) -> bool:
    proposition_tokens = tokenize_affidavit_text(proposition_text)
    excerpt_tokens = tokenize_affidavit_text(excerpt_text)
    if not proposition_tokens or not excerpt_tokens:
        return False
    shared_ratio = len(proposition_tokens & excerpt_tokens) / len(proposition_tokens)
    return shared_ratio >= 0.85


def normalize_claim_root_text(
    *,
    proposition_text: str,
    duplicate_match_excerpt: str | None,
    best_match_excerpt: str | None,
) -> str | None:
    duplicate_excerpt = str(duplicate_match_excerpt or "").strip()
    if duplicate_excerpt:
        return duplicate_excerpt
    proposition_excerpt = str(proposition_text or "").strip()
    if proposition_excerpt:
        return proposition_excerpt
    best_excerpt = str(best_match_excerpt or "").strip()
    return best_excerpt or None


def stable_claim_root_id(text: str) -> str:
    digest = hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()[:16]
    return f"claim_root:{digest}"


def derive_claim_root_fields(
    *,
    proposition_text: str,
    duplicate_match_excerpt: str | None,
    best_match_excerpt: str | None,
) -> dict[str, str | None]:
    claim_root_text = normalize_claim_root_text(
        proposition_text=proposition_text,
        duplicate_match_excerpt=duplicate_match_excerpt,
        best_match_excerpt=best_match_excerpt,
    )
    if not claim_root_text:
        return {
            "claim_root_text": None,
            "claim_root_id": None,
            "claim_root_basis": None,
            "alternate_context_excerpt": None,
        }
    basis = "duplicate_excerpt" if str(duplicate_match_excerpt or "").strip() else "proposition_text"
    alternate_context_excerpt = None
    best_excerpt = str(best_match_excerpt or "").strip()
    if str(duplicate_match_excerpt or "").strip() and best_excerpt and best_excerpt != str(duplicate_match_excerpt or "").strip():
        alternate_context_excerpt = best_excerpt
    return {
        "claim_root_text": claim_root_text,
        "claim_root_id": stable_claim_root_id(claim_root_text),
        "claim_root_basis": basis,
        "alternate_context_excerpt": alternate_context_excerpt,
    }


__all__ = [
    "derive_claim_root_fields",
    "is_duplicate_response_excerpt",
    "normalize_claim_root_text",
    "stable_claim_root_id",
]
