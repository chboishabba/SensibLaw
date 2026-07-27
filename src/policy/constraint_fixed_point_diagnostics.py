"""Deterministic diagnostics for document-local constraint refinement.

The operational compiler owns semantic state.  This module only observes the
compiler's durable artefacts and produces a non-authoritative diagnostic receipt.
It deliberately does not perform refinement, replace factors, resolve demands,
or alter convergence policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


DIAGNOSTIC_CONTRACT_REF = "constraint-fixed-point-diagnostics:v0_1"


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return [_canonical(item) for item in sorted(value, key=repr)]
    return value


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(row for row in value if isinstance(row, Mapping))


def _factor_rows(graph: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    return _rows((graph or {}).get("factors") or ())


def _factor_ref(row: Mapping[str, Any]) -> str:
    return str(row.get("factor_ref") or "")


def _factor_map(graph: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    return {
        ref: row
        for row in _factor_rows(graph)
        if (ref := _factor_ref(row))
    }


def _residual_count(graph: Mapping[str, Any] | None) -> int:
    return sum(len(tuple(row.get("residuals") or ())) for row in _factor_rows(graph))


def _alternative_refs(row: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("alternative_ref") or "")
        for item in _rows(row.get("alternatives") or ())
        if item.get("alternative_ref")
    }


def _binding_candidate_count(rows: Sequence[Mapping[str, Any]]) -> int:
    total = 0
    for row in rows:
        candidates = row.get("candidate_factor_refs")
        if candidates is None:
            candidates = row.get("candidates")
        if isinstance(candidates, Sequence) and not isinstance(
            candidates, (str, bytes, bytearray)
        ):
            total += len(candidates)
    return total


def _stage_elapsed_ms(
    semantic_stage_timing: Mapping[str, Any] | None,
    stage_name: str,
) -> int:
    timing = semantic_stage_timing or {}
    totals = timing.get("stage_totals_ms") or {}
    if isinstance(totals, Mapping):
        value = totals.get(stage_name)
        if value is not None:
            return max(0, int(value))
    return sum(
        max(0, int(row.get("elapsed_ms") or 0))
        for row in _rows(timing.get("timings") or ())
        if str(row.get("stage") or "") == stage_name
    )


def _persistence_elapsed_ms(semantic_stage_timing: Mapping[str, Any] | None) -> int:
    return _stage_elapsed_ms(semantic_stage_timing, "postgres_persistence")


@dataclass(frozen=True)
class ConstraintFixedPointDiagnostics:
    receipt: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.receipt)


def build_constraint_fixed_point_diagnostics(
    *,
    pnf_graph: Mapping[str, Any],
    refined_pnf_graph: Mapping[str, Any],
    constraint_assessments: Sequence[Mapping[str, Any]] = (),
    local_meet_plan: Sequence[Mapping[str, Any]] = (),
    typed_meets: Sequence[Mapping[str, Any]] = (),
    factor_refinements: Sequence[Mapping[str, Any]] = (),
    resolution_demands: Sequence[Mapping[str, Any]] = (),
    binding_candidate_sets_before: Sequence[Mapping[str, Any]] = (),
    binding_candidate_sets_after: Sequence[Mapping[str, Any]] = (),
    semantic_stage_timing: Mapping[str, Any] | None = None,
    iteration: int = 1,
) -> ConstraintFixedPointDiagnostics:
    """Build a diagnostic receipt from authoritative compiler artefacts.

    The current operational compiler performs one document-local assessment / meet /
    refinement pass.  ``iteration`` is therefore explicit and defaults to one rather
    than pretending that an unobserved iterative loop exists.
    """

    before = _factor_map(pnf_graph)
    after = _factor_map(refined_pnf_graph)
    assessment_rows = tuple(constraint_assessments)
    plan_rows = tuple(local_meet_plan)
    meet_rows = tuple(typed_meets)
    refinement_rows = tuple(factor_refinements)
    demand_rows = tuple(resolution_demands)
    binding_before_rows = tuple(binding_candidate_sets_before)
    binding_after_rows = tuple(binding_candidate_sets_after)

    rewritten_refs = tuple(
        sorted(
            ref
            for ref in before.keys() & after.keys()
            if _fingerprint(before[ref]) != _fingerprint(after[ref])
        )
    )
    added_factor_refs = tuple(sorted(after.keys() - before.keys()))
    removed_factor_refs = tuple(sorted(before.keys() - after.keys()))

    added_alternative_refs = {
        str(ref)
        for row in refinement_rows
        for ref in row.get("added_alternative_refs") or ()
        if ref
    }
    rejected_candidate_refs = {
        str(ref)
        for row in refinement_rows
        for ref in row.get("rejected_candidate_refs") or ()
        if ref
    }
    refinement_refs = [
        str(row.get("refinement_ref") or "") for row in refinement_rows
    ]
    duplicate_refinement_count = len(refinement_refs) - len(set(refinement_refs))
    effective_refinement_count = len(rewritten_refs) + len(added_factor_refs)
    proposed_refinement_count = len(refinement_rows)
    rejected_refinement_count = max(
        0,
        proposed_refinement_count
        - effective_refinement_count
        - duplicate_refinement_count,
    )

    candidate_meets_considered = len(plan_rows)
    accepted_meets = sum(
        1
        for row in meet_rows
        if str(row.get("state") or "")
        not in {"", "incompatible", "rejected", "violated"}
    )

    residuals_before = _residual_count(pnf_graph)
    residuals_after = _residual_count(refined_pnf_graph)
    resolved_demands = max(0, residuals_before - residuals_after)
    residuals_emitted = max(0, residuals_after - residuals_before)
    new_accepted_facts = len(added_factor_refs) + len(added_alternative_refs)

    elapsed_ms = _stage_elapsed_ms(semantic_stage_timing, "constraint_fixed_point")
    elapsed_seconds = elapsed_ms / 1_000.0
    semantic_progress = (
        new_accepted_facts + effective_refinement_count + resolved_demands
    )
    semantic_yield_per_second = (
        semantic_progress / elapsed_seconds if elapsed_seconds > 0 else None
    )

    assessment_to_effective_ratio = (
        len(assessment_rows) / max(1, effective_refinement_count)
    )
    meet_acceptance_ratio = accepted_meets / max(1, candidate_meets_considered)
    same_semantic_state = _fingerprint(pnf_graph) == _fingerprint(refined_pnf_graph)
    syntactic_change_without_semantic_progress = (
        bool(refinement_rows) and semantic_progress == 0
    )

    if syntactic_change_without_semantic_progress or (
        same_semantic_state and proposed_refinement_count > 0
    ):
        classification = "fixed_point_churn"
    elif (
        len(assessment_rows) >= 100
        and assessment_to_effective_ratio >= 20
    ) or (
        candidate_meets_considered >= 100 and meet_acceptance_ratio <= 0.05
    ):
        classification = "combinatorial_candidate_explosion"
    else:
        classification = "legitimate_high_volume_closure"

    receipt = {
        "contract_ref": DIAGNOSTIC_CONTRACT_REF,
        "authority": "diagnostic_only",
        "iteration": int(iteration),
        "iteration_elapsed_ms": elapsed_ms,
        "cumulative_database_read_write_ms": _persistence_elapsed_ms(
            semantic_stage_timing
        ),
        "factors_before": len(before),
        "factors_after": len(after),
        "constraint_assessments_evaluated": len(assessment_rows),
        "candidate_meets_considered": candidate_meets_considered,
        "candidate_meets_accepted": accepted_meets,
        "refinements_proposed": proposed_refinement_count,
        "refinements_applied": effective_refinement_count,
        "refinements_deduplicated": duplicate_refinement_count,
        "refinements_rejected": rejected_refinement_count,
        "factors_rewritten": len(rewritten_refs),
        "factor_refs_rewritten": list(rewritten_refs),
        "factor_refs_added": list(added_factor_refs),
        "factor_refs_removed": list(removed_factor_refs),
        "residuals_before": residuals_before,
        "residuals_after": residuals_after,
        "residuals_emitted": residuals_emitted,
        "unresolved_demands_produced": len(demand_rows),
        "resolved_demands": resolved_demands,
        "binding_candidates_before_compaction": _binding_candidate_count(
            binding_before_rows
        ),
        "binding_candidates_after_compaction": _binding_candidate_count(
            binding_after_rows
        ),
        "new_accepted_facts": new_accepted_facts,
        "effective_refinements": effective_refinement_count,
        "semantic_progress_units": semantic_progress,
        "semantic_yield_per_second": semantic_yield_per_second,
        "graph_fingerprint_before": _fingerprint(pnf_graph),
        "graph_fingerprint_after": _fingerprint(refined_pnf_graph),
        "semantic_state_stable": same_semantic_state,
        "assessment_to_effective_refinement_ratio": assessment_to_effective_ratio,
        "meet_acceptance_ratio": meet_acceptance_ratio,
        "classification": classification,
        "classification_contract": {
            "legitimate_high_volume_closure": (
                "semantic progress remains material relative to assessed candidates"
            ),
            "combinatorial_candidate_explosion": (
                "candidate or assessment volume is high relative to accepted work"
            ),
            "fixed_point_churn": (
                "syntactic refinement activity produces no semantic progress"
            ),
        },
        "zelph_boundary": {
            "eligible_shape": "(immutable_fact_set, versioned_rule_pack) -> additive_delta",
            "compiler_retains": [
                "factor_replacement",
                "non_monotone_refinement_choices",
                "residual_and_demand_state",
                "graph_identity",
                "transactional_persistence",
                "convergence_and_resource_limit_policy",
            ],
        },
    }
    return ConstraintFixedPointDiagnostics(_canonical(receipt))


def build_diagnostics_from_artifacts(
    artifacts: Mapping[str, Any],
) -> ConstraintFixedPointDiagnostics:
    """Build diagnostics directly from a document compilation artefact mapping."""

    candidate_sets = tuple(
        row
        for row in artifacts.get("binding_candidate_sets") or ()
        if isinstance(row, Mapping)
    )
    candidate_builds = tuple(
        row
        for row in artifacts.get("binding_candidate_set_builds") or ()
        if isinstance(row, Mapping)
    )
    return build_constraint_fixed_point_diagnostics(
        pnf_graph=dict(artifacts.get("pnf_graph") or {}),
        refined_pnf_graph=dict(artifacts.get("refined_pnf_graph") or {}),
        constraint_assessments=_rows(artifacts.get("constraint_assessments") or ()),
        local_meet_plan=_rows(artifacts.get("local_meet_plan") or ()),
        typed_meets=_rows(artifacts.get("typed_meets") or ()),
        factor_refinements=_rows(artifacts.get("factor_refinements") or ()),
        resolution_demands=_rows(artifacts.get("resolution_demands") or ()),
        binding_candidate_sets_before=candidate_builds,
        binding_candidate_sets_after=candidate_sets,
        semantic_stage_timing=dict(artifacts.get("semantic_stage_timing") or {}),
    )
