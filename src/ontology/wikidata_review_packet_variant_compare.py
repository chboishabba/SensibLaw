from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

Variant = Mapping[str, Any]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

# Flag emitted when split axes disagree once comparisons exist.
UNRECONCILED_SPLIT_AXIS_FLAG = "axis_specific_unreconciled_instance_of"


def _normalize_axes(variant: Variant) -> Mapping[str, Mapping[str, Any]]:
    axes = variant.get("merged_split_axes") or variant.get("split_axes") or []
    normalized: dict[str, dict[str, Any]] = {}
    for axis in axes:
        if not isinstance(axis, Mapping):
            continue
        prop = _stringify(axis.get("property"))
        if not prop:
            continue
        normalized[prop] = {
            "property": prop,
            "cardinality": int(axis.get("cardinality", 0) or 0),
            "reason": _stringify(axis.get("reason")),
            "source": _stringify(axis.get("source")),
        }
    return normalized


def _compare_axes(primary_axes: Mapping[str, Mapping[str, Any]],
                  comparison_axes: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    agreements: list[str] = []
    disagreements: list[str] = []
    all_props = set(primary_axes) | set(comparison_axes)
    for prop in sorted(all_props):
        primary = primary_axes.get(prop)
        comparison = comparison_axes.get(prop)
        if primary and comparison:
            if primary["cardinality"] == comparison["cardinality"] and primary["reason"] == comparison["reason"]:
                agreements.append(prop)
            else:
                disagreements.append(prop)
        else:
            disagreements.append(prop)
    return agreements, disagreements


def compare_review_packet_variants(
    *,
    primary_variant: Variant,
    comparison_variants: Sequence[Variant],
    max_variants: int = 3,
) -> dict[str, Any]:
    """Produce a lightweight agreement/disagreement surface for split-review variants."""
    primary_axes = _normalize_axes(primary_variant)
    diagnostics: list[str] = []
    disagreement_detected = False
    if not primary_axes:
        diagnostics.append("primary_variant_missing_axes")
    primary_id = _stringify(primary_variant.get("candidate_id"))
    comparisons: list[dict[str, Any]] = []
    for variant in comparison_variants[:max_variants]:
        comparison_id = _stringify(variant.get("candidate_id"))
        comparison_axes = _normalize_axes(variant)
        agreements, disagreements = _compare_axes(primary_axes, comparison_axes)
        status = "agreement" if disagreements == [] and agreements else "disagreement"
        comparisons.append(
            {
                "comparison_id": comparison_id,
                "status": status,
                "primary_action": _stringify(primary_variant.get("suggested_action") or primary_variant.get("action")),
                "comparison_action": _stringify(variant.get("suggested_action") or variant.get("action")),
                "agreements": agreements,
                "disagreements": disagreements,
                "notes": diagnostics.copy() if status == "disagreement" else [],
            }
        )
        if status == "disagreement":
            disagreement_detected = True
    if not comparisons:
        diagnostics.append("no_comparisons_provided")
    if disagreement_detected:
        diagnostics.append(UNRECONCILED_SPLIT_AXIS_FLAG)
    return {
        "primary_candidate_id": primary_id,
        "comparisons": comparisons,
        "diagnostic_flags": sorted(set(diagnostics)),
        "non_authoritative": True,
    }


__all__ = ["compare_review_packet_variants"]
