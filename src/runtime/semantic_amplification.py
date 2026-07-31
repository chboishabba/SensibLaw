"""Semantic amplification accounting without changing semantic output."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from src.policy.algebra.revision_identity import computed_factor_revision_ref


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    method = getattr(value, "to_dict", None)
    if callable(method):
        result = method()
        if isinstance(result, Mapping):
            return dict(result)
    return {}


def meet_refinement_report(
    meets: Sequence[Any], refinements: Sequence[Any]
) -> dict[str, Any]:
    meet_rows = [_row(value) for value in meets]
    refinement_rows = [_row(value) for value in refinements]
    meet_types = Counter(
        str(
            row.get("meet_type_ref")
            or row.get("operator_ref")
            or row.get("state")
            or "unknown"
        )
        for row in meet_rows
    )
    transitions = Counter()
    resulting_revisions: list[str] = []
    no_op = 0
    for row in refinement_rows:
        prior = row.get("prior_factor")
        resulting = row.get("resulting_factor")
        if not isinstance(prior, Mapping) or not isinstance(resulting, Mapping):
            transitions["unknown"] += 1
            continue
        # This is diagnostic telemetry.  Use the canonical content-derived
        # identity without rejecting transitional metadata; persistence and
        # manifest validation retain strict explicit-reference checks.
        prior_revision = computed_factor_revision_ref(prior)
        resulting_revision = computed_factor_revision_ref(resulting)
        resulting_revisions.append(resulting_revision)
        transitions[
            f"{prior.get('closure_state', 'unknown')}->{resulting.get('closure_state', 'unknown')}"
        ] += 1
        if prior_revision == resulting_revision:
            no_op += 1
    return {
        "meet_count": len(meet_rows),
        "meets_by_type": dict(sorted(meet_types.items())),
        "refinement_count": len(refinement_rows),
        "refinements_by_transition": dict(sorted(transitions.items())),
        "no_op_refinement_count": no_op,
        "duplicate_resulting_factor_revision_count": (
            len(resulting_revisions) - len(set(resulting_revisions))
        ),
    }


def _demand_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("subject_kind_ref") or row.get("subject_kind"),
        row.get("subject_ref"),
        row.get("operation_ref") or row.get("producer_contract"),
        tuple(sorted(str(value) for value in row.get("candidate_set_refs") or ())),
        tuple(sorted(str(value) for value in row.get("residual_refs") or ())),
    )


def demand_report(demands: Sequence[Any]) -> dict[str, Any]:
    rows = [_row(value) for value in demands]
    kinds = Counter(
        str(row.get("subject_kind_ref") or row.get("subject_kind") or "unknown")
        for row in rows
    )
    operations = Counter(
        str(
            row.get("operation_ref")
            or row.get("producer_contract")
            or row.get("reason")
            or "unknown"
        )
        for row in rows
    )
    keys = [_demand_key(row) for row in rows]
    refs = [str(row.get("demand_ref") or "") for row in rows if row.get("demand_ref")]
    return {
        "demand_count": len(rows),
        "demands_by_subject_kind": dict(sorted(kinds.items())),
        "demands_by_source_operation": dict(sorted(operations.items())),
        "duplicate_demand_ref_count": len(refs) - len(set(refs)),
        "equivalent_demand_count": len(rows) - len(set(keys)),
    }


def candidate_set_report(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    sets = tuple(artifacts.get("binding_candidate_sets") or ())
    rows = [_row(value) for value in sets]
    sizes = [
        int(row.get("member_count") or len(row.get("members") or ())) for row in rows
    ]
    histogram = Counter(
        "0"
        if size == 0
        else "1"
        if size == 1
        else "2-4"
        if size <= 4
        else "5-16"
        if size <= 16
        else "17-64"
        for size in sizes
    )
    return {
        "candidate_set_count": len(rows),
        "candidate_set_member_count": sum(sizes),
        "candidate_set_size_histogram": dict(sorted(histogram.items())),
        "candidate_set_max_size": max(sizes, default=0),
    }


def closure_amplification_report(counters: Mapping[str, int]) -> dict[str, Any]:
    values = {str(key): int(value) for key, value in counters.items()}
    emitted = values.get("proposals_emitted", 0)
    changed = values.get("changed_factors", 0)
    values["proposals_examined_per_emitted"] = (
        values.get("proposals_examined", 0) / emitted if emitted else None
    )
    values["factor_scans_per_changed_factor"] = (
        values.get("factor_scans", 0) / changed if changed else None
    )
    return values


__all__ = [
    "candidate_set_report",
    "closure_amplification_report",
    "demand_report",
    "meet_refinement_report",
]
