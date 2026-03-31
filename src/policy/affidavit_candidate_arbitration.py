"""Shared affidavit candidate arbitration helpers."""
from __future__ import annotations

from typing import Any, Mapping


def candidate_rank_key(item: Mapping[str, Any]) -> tuple[float, float, float, int]:
    return (
        float(item["adjusted_score"]),
        float(item.get("predicate_alignment_score") or 0.0),
        float(item["score"]),
        -len(str(item["match_excerpt"] or "")),
    )


def clause_rank_key(item: Mapping[str, Any]) -> tuple[float, float, int, float]:
    return (
        float(item["adjusted_score"]),
        float(item.get("predicate_alignment_score") or 0.0),
        -len(str(item["match_excerpt"] or "")),
        float(item["score"]),
    )


def select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return max(candidates, key=candidate_rank_key)


def promote_duplicate_root_alternate(
    *,
    comparison_mode: str,
    candidates: list[dict[str, Any]],
    best_candidate: dict[str, Any],
    duplicate_match_excerpt: str | None,
) -> tuple[dict[str, Any], str | None]:
    if comparison_mode != "contested_narrative":
        return best_candidate, duplicate_match_excerpt
    if not (
        best_candidate["response_role"] == "restatement_only" or best_candidate["is_duplicate_excerpt"]
    ):
        return best_candidate, duplicate_match_excerpt
    substantive_candidates = [
        candidate
        for candidate in candidates
        if (
            candidate["response_role"] in {"dispute", "admission", "explanation", "support_or_corroboration"}
            or float(candidate.get("predicate_alignment_score") or 0.0) >= 0.5
        )
        and not candidate["is_duplicate_excerpt"]
    ]
    if not substantive_candidates:
        return best_candidate, duplicate_match_excerpt
    alternate_candidate = max(substantive_candidates, key=candidate_rank_key)
    duplicate_match_excerpt = str(best_candidate["match_excerpt"] or "").strip()
    return alternate_candidate, duplicate_match_excerpt


def promote_non_echo_alternate(
    *,
    comparison_mode: str,
    candidates: list[dict[str, Any]],
    best_candidate: dict[str, Any],
    duplicate_match_excerpt: str | None,
) -> tuple[dict[str, Any], str | None]:
    if comparison_mode != "contested_narrative" or not best_candidate.get("is_proposition_echo"):
        return best_candidate, duplicate_match_excerpt
    substantive_candidates = [
        candidate
        for candidate in candidates
        if not candidate.get("is_proposition_echo")
        and not candidate.get("is_duplicate_excerpt")
        and (
            candidate["response_role"] in {"dispute", "admission", "explanation", "support_or_corroboration"}
            or float(candidate.get("predicate_alignment_score") or 0.0) >= 0.5
        )
    ]
    if not substantive_candidates:
        return best_candidate, duplicate_match_excerpt
    alternate_candidate = max(substantive_candidates, key=candidate_rank_key)
    duplicate_match_excerpt = duplicate_match_excerpt or str(best_candidate["match_excerpt"] or "").strip()
    return alternate_candidate, duplicate_match_excerpt


def preserve_duplicate_match_excerpt(
    *,
    candidates: list[dict[str, Any]],
    duplicate_match_excerpt: str | None,
) -> str | None:
    if duplicate_match_excerpt is not None:
        return duplicate_match_excerpt
    for candidate in candidates:
        if candidate.get("is_proposition_echo"):
            duplicate_match_excerpt = str(candidate.get("match_excerpt") or "").strip() or None
            if duplicate_match_excerpt:
                break
    return duplicate_match_excerpt


def promote_clause_alternate(
    *,
    comparison_mode: str,
    candidates: list[dict[str, Any]],
    best_candidate: dict[str, Any],
    duplicate_match_excerpt: str | None,
) -> dict[str, Any]:
    if comparison_mode != "contested_narrative":
        return best_candidate
    if not duplicate_match_excerpt:
        return best_candidate
    if best_candidate.get("match_basis") != "segment":
        return best_candidate
    if best_candidate.get("response_role") not in {"admission", "explanation", "support_or_corroboration", "procedural_frame"}:
        return best_candidate
    best_adjusted = float(best_candidate.get("adjusted_score") or 0.0)
    best_predicate = float(best_candidate.get("predicate_alignment_score") or 0.0)
    clause_alternates = [
        candidate
        for candidate in candidates
        if candidate.get("match_basis") == "clause"
        and not candidate.get("is_proposition_echo")
        and not candidate.get("is_duplicate_excerpt")
        and candidate.get("response_role") == best_candidate.get("response_role")
        and float(candidate.get("adjusted_score") or 0.0) >= max(best_adjusted - 0.08, 0.0)
        and float(candidate.get("predicate_alignment_score") or 0.0) >= max(best_predicate - 0.15, 0.0)
    ]
    if not clause_alternates:
        return best_candidate
    return max(clause_alternates, key=clause_rank_key)


def finalize_candidate_selection(
    *,
    best_candidate: Mapping[str, Any],
    duplicate_match_excerpt: str | None,
) -> dict[str, Any]:
    return {
        "score": float(best_candidate["score"]),
        "adjusted_score": float(best_candidate["adjusted_score"]),
        "match_basis": str(best_candidate["match_basis"]),
        "match_excerpt": str(best_candidate["match_excerpt"] or "").strip(),
        "duplicate_match_excerpt": duplicate_match_excerpt,
        "response_role": str(best_candidate["response_role"]),
        "response_cues": best_candidate["response_cues"],
        "predicate_alignment_score": float(best_candidate.get("predicate_alignment_score") or 0.0),
        "is_proposition_echo": best_candidate.get("is_proposition_echo", False),
    }


def arbitrate_candidate_selection(
    *,
    comparison_mode: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    best_candidate = select_best_candidate(candidates)
    duplicate_match_excerpt = None
    best_candidate, duplicate_match_excerpt = promote_duplicate_root_alternate(
        comparison_mode=comparison_mode,
        candidates=candidates,
        best_candidate=best_candidate,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )
    best_candidate, duplicate_match_excerpt = promote_non_echo_alternate(
        comparison_mode=comparison_mode,
        candidates=candidates,
        best_candidate=best_candidate,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )
    duplicate_match_excerpt = preserve_duplicate_match_excerpt(
        candidates=candidates,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )
    best_candidate = promote_clause_alternate(
        comparison_mode=comparison_mode,
        candidates=candidates,
        best_candidate=best_candidate,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )
    return finalize_candidate_selection(
        best_candidate=best_candidate,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )


__all__ = [
    "arbitrate_candidate_selection",
    "candidate_rank_key",
    "clause_rank_key",
    "finalize_candidate_selection",
    "preserve_duplicate_match_excerpt",
    "promote_clause_alternate",
    "promote_duplicate_root_alternate",
    "promote_non_echo_alternate",
    "select_best_candidate",
]
