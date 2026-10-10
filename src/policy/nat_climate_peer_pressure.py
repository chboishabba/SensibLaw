"""Least-privilege Nat climate peer-cohort pressure weld.

The existing Wikidata migration pack builder already owns target-model, subject,
qualifier, reference, temporal and split residuals. This adapter replaces only
its placeholder ``peer_cohort`` row when a governed invariant snapshot and a
revision-bound item surface are available.

Everything else, including diagnostic-only authority and promotion/edit state,
is preserved from the original pressure assessment.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .peer_cohort import build_peer_cohort_residual_from_item_surface


def _text(value: Any) -> str:
    return str(value or "").strip()


def weld_nat_peer_cohort_residual(
    *,
    pressure_assessment: Mapping[str, Any],
    invariant_snapshot: Mapping[str, Any],
    item_surface: Mapping[str, Any],
    candidate_ref: str | None = None,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Replace exactly one peer-cohort residual; preserve all other semantics."""

    if not isinstance(pressure_assessment, Mapping):
        raise ValueError("pressure_assessment must be a mapping")
    existing = deepcopy(dict(pressure_assessment))
    residuals = existing.get("residuals")
    if not isinstance(residuals, list):
        raise ValueError("pressure assessment requires residuals list")

    peer_positions = [
        index
        for index, row in enumerate(residuals)
        if isinstance(row, Mapping) and _text(row.get("residual_kind")) == "peer_cohort"
    ]
    if len(peer_positions) != 1:
        raise ValueError("Nat pressure weld requires exactly one peer_cohort residual")

    candidate = _text(candidate_ref) or _text(existing.get("candidate_ref"))
    if not candidate:
        raise ValueError("candidate_ref is required")
    replacement = build_peer_cohort_residual_from_item_surface(
        candidate_ref=candidate,
        invariant_snapshot=invariant_snapshot,
        item_surface=item_surface,
        evidence_refs=evidence_refs,
    )

    original_authority = existing.get("authority")
    original_promotion = existing.get("promotion_effect")
    original_edit = existing.get("edit_effect")
    residuals[peer_positions[0]] = replacement
    existing["residuals"] = residuals

    if existing.get("authority") != original_authority:
        raise AssertionError("peer weld changed pressure authority")
    if existing.get("promotion_effect") != original_promotion:
        raise AssertionError("peer weld changed promotion state")
    if existing.get("edit_effect") != original_edit:
        raise AssertionError("peer weld changed edit state")
    return existing


__all__ = ["weld_nat_peer_cohort_residual"]
