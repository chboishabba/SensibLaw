"""Receipt-bearing PNF lifecycle after proposal production and before Domain IR.

Reduction, admissibility, resolution, projection, and execution are distinct.
This module derives assessments, admissions, and resolutions from the existing
fibred proposal ledger; it creates no parallel semantic graph and performs no
memory or learning transition.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256

CANDIDATE_ASSESSMENT_SCHEMA_VERSION = "sl.pnf.candidate_assessment.v0_1"
ADMISSIBILITY_RECEIPT_SCHEMA_VERSION = "sl.pnf.admissibility_receipt.v0_1"
RESOLUTION_RECEIPT_SCHEMA_VERSION = "sl.pnf.resolution_receipt.v0_1"
SEMANTIC_LIFECYCLE_SCHEMA_VERSION = "sl.pnf.semantic_lifecycle.v0_1"

_VALIDATION = {"satisfied", "violated", "both", "undetermined", "inapplicable"}
_ADMISSION = {"admitted", "rejected", "blocked"}
_RESOLUTION = {
    "resolved_unique",
    "resolved_preferred",
    "retained_plural",
    "blocked_insufficient_coverage",
    "blocked_conflict",
    "inapplicable",
}
_DEFINITIVE_GROUNDS = {
    "missing_span",
    "incompatible_role",
    "impossible_temporal_scope",
    "incompatible_entity_type",
    "wrong_jurisdiction",
    "excess_authority",
    "failed_typed_meet",
    "invalid_translation_transport",
    "constraint_violation",
}


def _refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _proposal_ref(value: Any) -> str:
    return str(_get(value, "proposal_ref", "") or "")


def _payload(value: Any) -> Mapping[str, Any]:
    row = _get(value, "candidate_payload", {})
    return row if isinstance(row, Mapping) else {}


def _ground(residual: str) -> str | None:
    value = residual.casefold()
    checks = (
        (("no_typed_meet", "failed_typed_meet"), "failed_typed_meet"),
        (("role_mismatch", "incompatible_role"), "incompatible_role"),
        (("impossible_temporal", "invalid_temporal"), "impossible_temporal_scope"),
        (("entity_type", "incompatible_type"), "incompatible_entity_type"),
        (("wrong_jurisdiction", "incompatible_jurisdiction"), "wrong_jurisdiction"),
        (("excess_authority", "authority_overclaim"), "excess_authority"),
        (("invalid_translation", "translation_noncoextensive"), "invalid_translation_transport"),
        (("constraint_violation", "constraint_contradiction"), "constraint_violation"),
    )
    return next((result for needles, result in checks if any(needle in value for needle in needles)), None)


@dataclass(frozen=True)
class CandidateAssessment:
    document_ref: str
    proposal_ref: str
    semantic_coordinate_ref: str
    outcome: str
    invalidation_grounds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    residual_refs: tuple[str, ...]
    required_coverage_refs: tuple[str, ...]
    observed_coverage_refs: tuple[str, ...]
    applied_constraint_refs: tuple[str, ...]
    applicable: bool
    coverage_complete: bool
    assessment_revision: str = "v0_1"

    def __post_init__(self) -> None:
        if self.outcome not in _VALIDATION:
            raise ValueError("unsupported candidate assessment outcome")
        if not self.document_ref or not self.proposal_ref or not self.semantic_coordinate_ref:
            raise ValueError("candidate assessment requires document, proposal, and coordinate")

    @property
    def assessment_ref(self) -> str:
        return "candidate-assessment:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": CANDIDATE_ASSESSMENT_SCHEMA_VERSION,
            **asdict(self),
            "invalidation_grounds": list(_refs(self.invalidation_grounds)),
            "evidence_refs": list(_refs(self.evidence_refs)),
            "residual_refs": list(_refs(self.residual_refs)),
            "required_coverage_refs": list(_refs(self.required_coverage_refs)),
            "observed_coverage_refs": list(_refs(self.observed_coverage_refs)),
            "applied_constraint_refs": list(_refs(self.applied_constraint_refs)),
            "semantic_state_promoted": False,
            "truth_closed": False,
        }
        if include_ref:
            payload["assessment_ref"] = self.assessment_ref
        return payload


@dataclass(frozen=True)
class AdmissibilityReceipt:
    document_ref: str
    proposal_ref: str
    assessment_ref: str
    state: str
    applied_constraint_refs: tuple[str, ...]
    authority_ceiling: str
    required_coverage_refs: tuple[str, ...]
    observed_coverage_refs: tuple[str, ...]
    invalidation_grounds: tuple[str, ...]
    block_reasons: tuple[str, ...]
    receipt_revision: str = "v0_1"

    def __post_init__(self) -> None:
        if self.state not in _ADMISSION:
            raise ValueError("unsupported admissibility state")

    @property
    def receipt_ref(self) -> str:
        return "pnf-admissibility:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": ADMISSIBILITY_RECEIPT_SCHEMA_VERSION,
            **asdict(self),
            "applied_constraint_refs": list(_refs(self.applied_constraint_refs)),
            "required_coverage_refs": list(_refs(self.required_coverage_refs)),
            "observed_coverage_refs": list(_refs(self.observed_coverage_refs)),
            "invalidation_grounds": list(_refs(self.invalidation_grounds)),
            "block_reasons": list(_refs(self.block_reasons)),
            "authority": "admissibility_only",
            "identity_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


@dataclass(frozen=True)
class ResolutionReceipt:
    document_ref: str
    fibre_summary_ref: str
    semantic_coordinate_ref: str
    state: str
    selected_proposal_ref: str | None
    admitted_proposal_refs: tuple[str, ...]
    retained_alternative_refs: tuple[str, ...]
    selector_ref: str
    selection_ground_refs: tuple[str, ...]
    unresolved_residual_refs: tuple[str, ...]
    authority_ceiling: str = "resolved_pnf_candidate"
    receipt_revision: str = "v0_1"

    def __post_init__(self) -> None:
        if self.state not in _RESOLUTION:
            raise ValueError("unsupported semantic resolution state")
        resolved = self.state in {"resolved_unique", "resolved_preferred"}
        if resolved != bool(self.selected_proposal_ref):
            raise ValueError("selected proposal must exactly match resolved state")

    @property
    def operationally_resolved(self) -> bool:
        return self.state in {"resolved_unique", "resolved_preferred"}

    @property
    def resolution_ref(self) -> str:
        return "pnf-resolution:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": RESOLUTION_RECEIPT_SCHEMA_VERSION,
            **asdict(self),
            "admitted_proposal_refs": list(_refs(self.admitted_proposal_refs)),
            "retained_alternative_refs": list(_refs(self.retained_alternative_refs)),
            "selection_ground_refs": list(_refs(self.selection_ground_refs)),
            "unresolved_residual_refs": list(_refs(self.unresolved_residual_refs)),
            "operationally_resolved": self.operationally_resolved,
            "authority": "semantic_resolution_only",
            "identity_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["resolution_ref"] = self.resolution_ref
        return payload


@dataclass(frozen=True)
class SemanticLifecycleResult:
    document_ref: str
    assessments: tuple[CandidateAssessment, ...]
    admissions: tuple[AdmissibilityReceipt, ...]
    resolutions: tuple[ResolutionReceipt, ...]

    @property
    def lifecycle_ref(self) -> str:
        return "pnf-semantic-lifecycle:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": SEMANTIC_LIFECYCLE_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "candidate_assessments": [row.to_dict() for row in self.assessments],
            "admissibility_receipts": [row.to_dict() for row in self.admissions],
            "resolution_receipts": [row.to_dict() for row in self.resolutions],
            "stage_order": ["candidate_assessment", "admissibility", "deterministic_reduction", "semantic_resolution"],
            "reduction_is_not_resolution": True,
            "memory_transition_performed": False,
            "semantic_state_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["lifecycle_ref"] = self.lifecycle_ref
        return payload


def assess_factor_proposals(
    *,
    proposals: Sequence[Any],
    fibre_elements: Sequence[Any] = (),
    constraint_assessments: Sequence[Mapping[str, Any]] = (),
) -> tuple[CandidateAssessment, ...]:
    elements: dict[str, list[Any]] = {}
    for element in fibre_elements:
        coordinate = str(_get(element, "coordinate_ref", "") or "")
        if coordinate:
            elements.setdefault(coordinate, []).append(element)
    constraints = {
        str(row.get("constraint_ref") or ""): row
        for row in constraint_assessments
        if row.get("constraint_ref")
    }
    output: list[CandidateAssessment] = []
    for proposal in proposals:
        proposal_ref = _proposal_ref(proposal)
        coordinate = str(_get(proposal, "semantic_coordinate_ref", "") or "")
        payload = _payload(proposal)
        residuals = _refs(_get(proposal, "residuals", ()) or ())
        spans = _refs(_get(proposal, "source_span_refs", ()) or ())
        observations = _refs(_get(proposal, "input_observation_refs", ()) or ())
        dependencies = _refs(_get(proposal, "dependency_factor_refs", ()) or ())
        axes = _refs(_get(proposal, "ontology_axis_refs", ()) or ())
        transports = _refs(_get(proposal, "transport_refs", ()) or ())
        required = _refs(_get(proposal, "coverage_requirements", ()) or ())
        evidence = set((*spans, *observations, *dependencies, *axes, *transports))
        observed = set(evidence)
        support = contradiction = undetermined = False
        for element in elements.get(coordinate, ()):
            role = str(_get(element, "derivation_role", "") or "")
            support |= role == "support"
            contradiction |= role == "contradict"
            undetermined |= role == "undetermined"
            for name in ("source_refs", "dependency_refs", "transport_refs", "ontology_axis_refs"):
                refs = _refs(_get(element, name, ()) or ())
                evidence.update(refs)
                observed.update(refs)
            element_ref = str(_get(element, "element_ref", "") or "")
            if element_ref:
                evidence.add(element_ref)
                observed.add(element_ref)
        if coordinate not in elements:
            role = str(_get(proposal, "derivation_role", "support") or "support")
            support, contradiction, undetermined = role == "support", role == "contradict", role == "undetermined"

        grounds = {ground for residual in residuals if (ground := _ground(residual))}
        if not spans and not observations and not dependencies:
            grounds.add("missing_span")
        if payload.get("semantic_state_promoted") or str(payload.get("authority") or "") in {"authoritative", "world_fact", "legal_truth"}:
            grounds.add("excess_authority")
        applicable = not (payload.get("applicable") is False or payload.get("validation_state") == "inapplicable")
        declared = _refs((*tuple(payload.get("constraint_refs") or ()), *tuple(payload.get("applied_constraint_refs") or ())))
        applied: list[str] = []
        for constraint_ref in declared:
            row = constraints.get(constraint_ref)
            if row is None:
                continue
            applied.append(constraint_ref)
            evidence.update(_refs(row.get("evidence_refs") or ()))
            residuals = _refs((*residuals, *tuple(row.get("residual_refs") or ())))
            state = str(row.get("state") or "")
            if state in {"violated", "contradicted", "failed"}:
                contradiction = True
                grounds.add("constraint_violation")
            elif state in {"insufficient_evidence", "undetermined"}:
                undetermined = True
        complete = set(required).issubset(observed)
        contradiction |= bool(grounds & _DEFINITIVE_GROUNDS)
        if undetermined and not contradiction:
            support &= complete
        outcome = (
            "inapplicable" if not applicable else
            "both" if support and contradiction else
            "violated" if contradiction else
            "satisfied" if support and complete else
            "undetermined"
        )
        output.append(CandidateAssessment(
            document_ref=str(_get(proposal, "document_ref", "") or ""),
            proposal_ref=proposal_ref,
            semantic_coordinate_ref=coordinate,
            outcome=outcome,
            invalidation_grounds=_refs(grounds),
            evidence_refs=_refs(evidence),
            residual_refs=residuals,
            required_coverage_refs=required,
            observed_coverage_refs=_refs(observed),
            applied_constraint_refs=_refs(applied),
            applicable=applicable,
            coverage_complete=complete,
        ))
    return tuple(sorted(output, key=lambda row: row.assessment_ref))


def admit_factor_proposals(
    assessments: Sequence[CandidateAssessment],
    *,
    authority_ceiling: str = "candidate_pnf_only",
) -> tuple[AdmissibilityReceipt, ...]:
    output: list[AdmissibilityReceipt] = []
    for assessment in assessments:
        grounds = set(assessment.invalidation_grounds)
        if assessment.outcome == "violated" or grounds & _DEFINITIVE_GROUNDS:
            state, reasons = "rejected", ("positive_invalidation",)
        elif assessment.outcome == "both":
            state, reasons = "blocked", ("support_and_contradiction",)
        elif assessment.outcome == "inapplicable":
            state, reasons = "blocked", ("validation_map_inapplicable",)
        elif assessment.outcome == "undetermined" or not assessment.coverage_complete:
            state, reasons = "blocked", (("insufficient_coverage" if not assessment.coverage_complete else "semantic_frontier_unresolved"),)
        else:
            state, reasons = "admitted", ()
        output.append(AdmissibilityReceipt(
            document_ref=assessment.document_ref,
            proposal_ref=assessment.proposal_ref,
            assessment_ref=assessment.assessment_ref,
            state=state,
            applied_constraint_refs=assessment.applied_constraint_refs,
            authority_ceiling=authority_ceiling,
            required_coverage_refs=assessment.required_coverage_refs,
            observed_coverage_refs=assessment.observed_coverage_refs,
            invalidation_grounds=assessment.invalidation_grounds,
            block_reasons=_refs(reasons),
        ))
    return tuple(sorted(output, key=lambda row: row.receipt_ref))


def _preference(proposal: Any) -> tuple[int, float]:
    rank = {"supported": 5, "supported_with_residuals": 4, "candidate": 3, "unscored": 2, "unresolved": 1, "contested": 0, "unsupported": -1}
    return rank.get(str(_get(proposal, "support_state", "candidate") or "candidate"), 0), float(_get(proposal, "confidence", 0.0) or 0.0)


def resolve_reduced_factors(
    *,
    reduced_factors: Sequence[Any],
    proposals: Sequence[Any],
    assessments: Sequence[CandidateAssessment],
    admissions: Sequence[AdmissibilityReceipt],
) -> tuple[ResolutionReceipt, ...]:
    proposal_by_ref = {_proposal_ref(row): row for row in proposals}
    assessment_by_ref = {row.proposal_ref: row for row in assessments}
    admission_by_ref = {row.proposal_ref: row for row in admissions}
    output: list[ResolutionReceipt] = []
    for factor in reduced_factors:
        proposal_refs = _refs(_get(factor, "proposal_refs", ()) or ())
        admitted = tuple(ref for ref in proposal_refs if admission_by_ref.get(ref) and admission_by_ref[ref].state == "admitted")
        selected: str | None = None
        if len(admitted) == 1:
            state, selected = "resolved_unique", admitted[0]
        elif len(admitted) > 1:
            ranked = sorted(((_preference(proposal_by_ref[ref]), ref) for ref in admitted if ref in proposal_by_ref), reverse=True)
            if len(ranked) > 1 and ranked[0][0] > ranked[1][0]:
                state, selected = "resolved_preferred", ranked[0][1]
            else:
                state = "retained_plural"
        else:
            related = [assessment_by_ref[ref] for ref in proposal_refs if ref in assessment_by_ref]
            if related and all(row.outcome == "inapplicable" for row in related):
                state = "inapplicable"
            elif any(row.outcome in {"both", "violated"} for row in related):
                state = "blocked_conflict"
            else:
                state = "blocked_insufficient_coverage"
        grounds = _refs((*(assessment_by_ref[ref].assessment_ref for ref in proposal_refs if ref in assessment_by_ref), *(admission_by_ref[ref].receipt_ref for ref in proposal_refs if ref in admission_by_ref)))
        unresolved = set(_refs(_get(factor, "residuals", ()) or ()))
        for ref in proposal_refs:
            if ref in admission_by_ref:
                unresolved.update(admission_by_ref[ref].block_reasons)
        document_ref = str(_get(factor, "document_ref", "") or next((str(_get(proposal_by_ref[ref], "document_ref", "") or "") for ref in proposal_refs if ref in proposal_by_ref), ""))
        output.append(ResolutionReceipt(
            document_ref=document_ref,
            fibre_summary_ref=str(_get(factor, "factor_ref", "") or ""),
            semantic_coordinate_ref=str(_get(factor, "semantic_coordinate_ref", "") or ""),
            state=state,
            selected_proposal_ref=selected,
            admitted_proposal_refs=_refs(admitted),
            retained_alternative_refs=_refs(ref for ref in proposal_refs if ref != selected),
            selector_ref="deterministic-evidence-order:v0_1",
            selection_ground_refs=grounds,
            unresolved_residual_refs=_refs(unresolved),
        ))
    return tuple(sorted(output, key=lambda row: row.resolution_ref))


def build_semantic_lifecycle(
    *,
    document_ref: str,
    proposals: Sequence[Any],
    reduced_factors: Sequence[Any],
    fibre_elements: Sequence[Any] = (),
    constraint_assessments: Sequence[Mapping[str, Any]] = (),
) -> SemanticLifecycleResult:
    assessments = assess_factor_proposals(proposals=proposals, fibre_elements=fibre_elements, constraint_assessments=constraint_assessments)
    admissions = admit_factor_proposals(assessments)
    return SemanticLifecycleResult(
        document_ref=document_ref,
        assessments=assessments,
        admissions=admissions,
        resolutions=resolve_reduced_factors(reduced_factors=reduced_factors, proposals=proposals, assessments=assessments, admissions=admissions),
    )


__all__ = [
    "AdmissibilityReceipt",
    "CandidateAssessment",
    "ResolutionReceipt",
    "SemanticLifecycleResult",
    "admit_factor_proposals",
    "assess_factor_proposals",
    "build_semantic_lifecycle",
    "resolve_reduced_factors",
]
