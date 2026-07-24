"""Project operational worklist and coverage receipts into assessment evidence.

This creates an assessment-only view of immutable proposal rows. The explicit
``proposal_ref`` remains unchanged; neither constraint adjacency nor coverage
telemetry is added to proposal semantic identity.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def annotate_assessment_proposals(
    *,
    proposals: Sequence[Mapping[str, Any]],
    work_items: Sequence[Any],
    coverage_notices: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    constraints_by_factor: dict[str, set[str]] = {}
    for item in work_items:
        for factor_ref in item.incident_factor_refs:
            constraints_by_factor.setdefault(str(factor_ref), set()).add(
                str(item.constraint_ref)
            )

    complete_coverage: dict[tuple[str, str], Mapping[str, Any]] = {}
    for notice in coverage_notices:
        if str(notice.get("state") or "") != "complete":
            continue
        key = (
            str(notice.get("scope_ref") or ""),
            str(notice.get("barrier") or ""),
        )
        if all(key):
            complete_coverage[key] = notice

    output: list[dict[str, Any]] = []
    for proposal in proposals:
        payload = dict(proposal.get("candidate_payload") or {})
        related_factor_refs = {
            str(payload.get("source_factor_ref") or ""),
            *(str(ref) for ref in proposal.get("dependency_factor_refs") or ()),
        }
        related_factor_refs.discard("")
        incident_constraint_refs = {
            constraint_ref
            for factor_ref in related_factor_refs
            for constraint_ref in constraints_by_factor.get(factor_ref, ())
        }
        payload["applied_constraint_refs"] = sorted(
            {
                *(str(ref) for ref in payload.get("applied_constraint_refs") or ()),
                *incident_constraint_refs,
            }
        )

        observed_refs = {
            str(ref) for ref in proposal.get("input_observation_refs") or ()
        }
        notice_refs: set[str] = set()
        scope_ref = str(proposal.get("scope_ref") or "")
        for requirement in proposal.get("coverage_requirements") or ():
            requirement_ref = str(requirement)
            notice = complete_coverage.get((scope_ref, requirement_ref))
            if notice is None:
                continue
            # The barrier label witnesses that the named requirement was closed;
            # notice/evidence refs preserve how that result was established.
            observed_refs.add(requirement_ref)
            notice_ref = str(notice.get("notice_ref") or "")
            if notice_ref:
                observed_refs.add(notice_ref)
                notice_refs.add(notice_ref)
            observed_refs.update(
                str(ref) for ref in notice.get("evidence_refs") or () if str(ref)
            )
        payload["coverage_notice_refs"] = sorted(notice_refs)
        output.append(
            {
                **dict(proposal),
                "candidate_payload": payload,
                "input_observation_refs": sorted(observed_refs),
            }
        )
    return tuple(output)


__all__ = ["annotate_assessment_proposals"]
