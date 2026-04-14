from __future__ import annotations

from typing import Any


PROPOSITION_CONTRADICTION_TAXONOMY_VERSION = "sl.proposition_contradiction_taxonomy.v0_1"

PROPOSITION_CONTRADICTION_LABELS = frozenset(
    {
        "none",
        "direct_denial",
        "incompatible_assertion",
        "canonical_form_divergence",
    }
)

EXCLUDED_REVIEW_PRESSURE_LABELS = frozenset(
    {
        "review_claim",
        "missing_review",
        "review_required",
        "candidate_conflict",
        "contested_source",
        "abstained_source",
    }
)

EXCLUDED_AMBIGUITY_LABELS = frozenset(
    {
        "unresolved",
        "ambiguous",
        "partial_overlap",
        "adjacent_event",
        "substitution",
        "missing",
    }
)

EXCLUDED_DUPLICATE_LABELS = frozenset(
    {
        "duplicate_excerpt",
        "duplicate_root",
        "echo_only",
        "restatement_only",
    }
)

EXCLUDED_ROUTE_URGENCY_LABELS = frozenset(
    {
        "authority_follow",
        "archive_follow",
        "legal_follow",
        "manual_review",
        "must_review",
    }
)


def validate_proposition_contradiction_label(label: Any) -> str:
    normalized = str(label or "").strip()
    if normalized not in PROPOSITION_CONTRADICTION_LABELS:
        raise ValueError(f"Unsupported proposition contradiction label: {normalized}")
    return normalized


def build_proposition_contradiction_taxonomy() -> dict[str, Any]:
    return {
        "version": PROPOSITION_CONTRADICTION_TAXONOMY_VERSION,
        "labels": sorted(PROPOSITION_CONTRADICTION_LABELS),
        "excluded_categories": {
            "review_pressure": sorted(EXCLUDED_REVIEW_PRESSURE_LABELS),
            "ambiguity_incompleteness": sorted(EXCLUDED_AMBIGUITY_LABELS),
            "duplicate_repetition": sorted(EXCLUDED_DUPLICATE_LABELS),
            "route_urgency": sorted(EXCLUDED_ROUTE_URGENCY_LABELS),
        },
        "notes": [
            "Policy-only taxonomy; no runtime contradiction emission.",
            "Contradiction remains separate from review pressure, ambiguity, duplicates, and route urgency.",
            "Resolution policy and gate behavior must not derive directly from these labels.",
        ],
    }

