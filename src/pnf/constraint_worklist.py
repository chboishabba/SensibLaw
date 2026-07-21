"""Adjacency-indexed, document-local constraint propagation.

Only constraints incident on changed factors are placed on the worklist.  Assessments are
immutable candidate-only evidence and never close a factor, identity, or legal conclusion.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.policy.algebra import ConstraintAssessment, FactorConstraint
from src.policy.carriers.canonical import canonical_sha256


CONSTRAINT_WORKLIST_SCHEMA_VERSION = "sl.pnf.constraint_worklist.v0_1"

_SUPPORTED_STRUCTURAL_CONSTRAINTS = {
    "syntactic_subject_of",
    "syntactic_object_of",
    "syntactic_oblique_of",
    "syntactic_complement_of",
    "content_of",
    "host_of_embedded_proposition",
    "nominal_head_of",
    "nominal_modifier_of",
}


@dataclass(frozen=True)
class ConstraintWorkItem:
    constraint_ref: str
    incident_factor_refs: tuple[str, ...]
    triggering_factor_refs: tuple[str, ...]

    @property
    def work_ref(self) -> str:
        return "constraint-work:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "constraint_ref": self.constraint_ref,
            "incident_factor_refs": list(self.incident_factor_refs),
            "triggering_factor_refs": list(self.triggering_factor_refs),
        }
        if include_ref:
            payload["work_ref"] = self.work_ref
        return payload


@dataclass(frozen=True)
class ConstraintWorklistResult:
    document_ref: str
    assessments: tuple[ConstraintAssessment, ...]
    work_items: tuple[ConstraintWorkItem, ...]
    changed_factor_refs: tuple[str, ...]
    fixed_point_rounds: int

    @property
    def result_ref(self) -> str:
        return "constraint-worklist-result:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": CONSTRAINT_WORKLIST_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "assessments": [row.to_dict() for row in self.assessments],
            "work_items": [row.to_dict() for row in self.work_items],
            "changed_factor_refs": list(self.changed_factor_refs),
            "fixed_point_rounds": self.fixed_point_rounds,
            "pending_work_items": 0,
            "semantic_state_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["result_ref"] = self.result_ref
        return payload


def _coerce_constraint(value: FactorConstraint | Mapping[str, Any]) -> FactorConstraint:
    if isinstance(value, FactorConstraint):
        return value
    return FactorConstraint(
        constraint_ref=str(value["constraint_ref"]),
        constraint_type=str(value["constraint_type"]),
        payload=dict(value.get("payload") or {}),
        provenance_refs=tuple(value.get("provenance_refs") or ()),
        source_factor_refs=tuple(value.get("source_factor_refs") or ()),
        target_factor_refs=tuple(value.get("target_factor_refs") or ()),
        alternative_group=(
            str(value["alternative_group"])
            if value.get("alternative_group") is not None
            else None
        ),
        required=bool(value.get("required", True)),
        residual_on_failure=(
            str(value["residual_on_failure"])
            if value.get("residual_on_failure")
            else None
        ),
    )


def evaluate_constraint_worklist(
    *,
    document_ref: str,
    factor_refs: Iterable[str],
    constraints: Sequence[FactorConstraint | Mapping[str, Any]],
    changed_factor_refs: Iterable[str] | None = None,
) -> ConstraintWorklistResult:
    """Evaluate only constraints incident on the changed factor frontier."""

    known_factors = frozenset(str(ref) for ref in factor_refs)
    declarations = tuple(
        sorted(
            (_coerce_constraint(row) for row in constraints),
            key=lambda row: row.constraint_ref,
        )
    )
    by_ref = {row.constraint_ref: row for row in declarations}
    if len(by_ref) != len(declarations):
        raise ValueError("constraint worklist requires unique constraint refs")

    adjacency: dict[str, set[str]] = {}
    for declaration in declarations:
        incident = set(declaration.source_factor_refs) | set(
            declaration.target_factor_refs
        )
        for factor_ref in incident:
            adjacency.setdefault(factor_ref, set()).add(
                declaration.constraint_ref
            )

    changed = (
        frozenset(str(ref) for ref in changed_factor_refs)
        if changed_factor_refs is not None
        else known_factors
    )
    queue = deque(
        sorted(
            {
                constraint_ref
                for factor_ref in changed
                for constraint_ref in adjacency.get(factor_ref, ())
            }
            or set(by_ref)
        )
    )
    queued = set(queue)
    assessments: dict[str, ConstraintAssessment] = {}
    work_items: list[ConstraintWorkItem] = []
    rounds = 0

    while queue:
        rounds += 1
        constraint_ref = queue.popleft()
        queued.discard(constraint_ref)
        declaration = by_ref[constraint_ref]
        incident = tuple(
            sorted(
                set(declaration.source_factor_refs)
                | set(declaration.target_factor_refs)
            )
        )
        triggers = tuple(sorted(set(incident) & set(changed)))
        work_items.append(
            ConstraintWorkItem(
                constraint_ref=constraint_ref,
                incident_factor_refs=incident,
                triggering_factor_refs=triggers,
            )
        )
        source_ok = set(declaration.source_factor_refs).issubset(known_factors)
        target_ok = set(declaration.target_factor_refs).issubset(known_factors)
        state = (
            "satisfied_with_alternatives"
            if declaration.constraint_type in _SUPPORTED_STRUCTURAL_CONSTRAINTS
            and source_ok
            and target_ok
            else "insufficient_evidence"
        )
        assessment = ConstraintAssessment(
            assessment_ref="constraint-assessment:"
            + canonical_sha256(
                {
                    "constraint_ref": declaration.constraint_ref,
                    "state": state,
                    "provenance_refs": declaration.provenance_refs,
                }
            ),
            constraint_ref=declaration.constraint_ref,
            state=state,
            evidence_refs=declaration.provenance_refs,
            residual_refs=(declaration.residual_on_failure,)
            if declaration.residual_on_failure
            else (),
        )
        prior = assessments.get(constraint_ref)
        assessments[constraint_ref] = assessment
        if prior is not None and prior.to_dict() != assessment.to_dict():
            for factor_ref in incident:
                for neighbour in adjacency.get(factor_ref, ()):
                    if neighbour not in queued:
                        queue.append(neighbour)
                        queued.add(neighbour)

    return ConstraintWorklistResult(
        document_ref=document_ref,
        assessments=tuple(
            sorted(assessments.values(), key=lambda row: row.assessment_ref)
        ),
        work_items=tuple(work_items),
        changed_factor_refs=tuple(sorted(changed)),
        fixed_point_rounds=rounds,
    )


__all__ = [
    "CONSTRAINT_WORKLIST_SCHEMA_VERSION",
    "ConstraintWorkItem",
    "ConstraintWorklistResult",
    "evaluate_constraint_worklist",
]
