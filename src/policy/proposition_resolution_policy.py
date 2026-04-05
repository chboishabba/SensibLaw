from __future__ import annotations

from typing import Any


PROPOSITION_RESOLUTION_POLICY_VERSION = "sl.proposition_resolution_policy.v0_1"

PROPOSITION_RESOLUTION_STATES = frozenset(
    {
        "hold",
        "abstain",
    }
)

EXCLUDED_RUNTIME_RESOLUTION_STATES = frozenset(
    {
        "resolve",
        "promote",
        "merge",
        "unify",
        "compiled",
        "canonical_write",
    }
)

EXCLUDED_REVIEW_PRESSURE_STATES = frozenset(
    {
        "review_claim",
        "missing_review",
        "review_required",
        "candidate_conflict",
        "must_review",
    }
)

EXCLUDED_CONTRADICTION_LABELS = frozenset(
    {
        "direct_denial",
        "incompatible_assertion",
        "canonical_form_divergence",
    }
)


def validate_proposition_resolution_state(state: Any) -> str:
    normalized = str(state or "").strip()
    if normalized not in PROPOSITION_RESOLUTION_STATES:
        raise ValueError(f"Unsupported proposition resolution state: {normalized}")
    return normalized


def build_proposition_resolution_policy() -> dict[str, Any]:
    return {
        "version": PROPOSITION_RESOLUTION_POLICY_VERSION,
        "allowed_states": sorted(PROPOSITION_RESOLUTION_STATES),
        "default_state": "hold",
        "fail_closed": True,
        "excluded_categories": {
            "runtime_resolution": sorted(EXCLUDED_RUNTIME_RESOLUTION_STATES),
            "review_pressure": sorted(EXCLUDED_REVIEW_PRESSURE_STATES),
            "contradiction_labels": sorted(EXCLUDED_CONTRADICTION_LABELS),
        },
        "notes": [
            "Policy-only resolution layer; no runtime proposition resolution emission.",
            "Fail closed to hold unless a later runtime adopter explicitly governs a narrower path.",
            "Abstain remains available for explicit non-resolution without canonical write or promotion.",
            "Review pressure and contradiction labels must not be treated as resolution states.",
        ],
    }
