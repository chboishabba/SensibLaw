from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from src.ontology.lean_wikidata_certificate import (
    LeanOntologyCertificate,
    compare_external_relation,
)


@dataclass(frozen=True)
class OntologyIssue:
    issue_id: str
    issue_type: str
    scope: str
    subject_ids: tuple[str, ...]
    status: str
    confidence_band: str
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items: list[str] = []
    for item in value:
        text = _stringify(item).strip()
        if text:
            items.append(text)
    return items


def _bounded_issue_status(row: Mapping[str, Any]) -> tuple[str, str]:
    uncertainty_flags = set(_string_list(row.get("uncertainty_flags")))
    if "page_open_questions" in uncertainty_flags:
        return ("review_required", "medium")
    return ("review_required", "low")


def _issue_from_probe_row(
    row: Mapping[str, Any],
    *,
    lane_id: str,
    cohort_id: str,
    required_reviewer_checks: Sequence[Mapping[str, Any]] | Sequence[str],
) -> OntologyIssue | None:
    review_entity_qid = _stringify(row.get("review_entity_qid")).strip()
    if not review_entity_qid:
        return None

    status, confidence_band = _bounded_issue_status(row)
    packet_id = _stringify(row.get("packet_id")).strip()
    split_plan_id = _stringify(row.get("split_plan_id")).strip()
    evidence_refs = tuple(
        ref
        for ref in (packet_id, split_plan_id, f"wikidata:{review_entity_qid}")
        if ref
    )

    reviewer_checks: list[str] = []
    for check in required_reviewer_checks:
        if isinstance(check, Mapping):
            check_id = _stringify(check.get("check_id")).strip()
            if check_id:
                reviewer_checks.append(check_id)
        else:
            text = _stringify(check).strip()
            if text:
                reviewer_checks.append(text)

    return OntologyIssue(
        issue_id=f"issue:wikidata:{review_entity_qid}:unsupported_is_a_chain",
        issue_type="unsupported_is_a_chain",
        scope="wikidata_ontology",
        subject_ids=(review_entity_qid,),
        status=status,
        confidence_band=confidence_band,
        reason_codes=("wikidata_missing_edge",),
        evidence_refs=evidence_refs,
        details={
            "lane_id": lane_id or None,
            "cohort_id": cohort_id or None,
            "packet_id": packet_id or None,
            "split_plan_id": split_plan_id or None,
            "smallest_typing_check": _stringify(
                row.get("smallest_typing_check")
            ).strip()
            or None,
            "recommended_next_step": _stringify(
                row.get("recommended_next_step")
            ).strip()
            or None,
            "packet_status": _stringify(row.get("packet_status")).strip() or None,
            "uncertainty_flags": _string_list(row.get("uncertainty_flags")),
            "required_reviewer_checks": reviewer_checks,
        },
    )


def _issue_from_formal_relation_comparison(row: Mapping[str, Any]) -> OntologyIssue | None:
    raw_certificate = row.get("lean_certificate")
    if not isinstance(raw_certificate, Mapping):
        raise ValueError("formal relation comparison requires lean_certificate")
    certificate = LeanOntologyCertificate.from_mapping(raw_certificate)
    external_state = _stringify(row.get("external_state")).strip()
    external_references = _string_list(row.get("external_references"))
    comparison = compare_external_relation(
        certificate,
        external_state=external_state,
        external_references=external_references,
    )

    # Replication is useful evidence but not an ontology issue.  Unresolved
    # comparisons also remain non-negative: absence of an external edge or a
    # failed/unbacked Lean checker does not manufacture contradiction.
    if comparison.disposition != "conflicting":
        return None

    evidence_refs = tuple(
        dict.fromkeys(
            (
                f"lean-request:{certificate.request_id}",
                f"lean-theorem:{certificate.module_name}:{certificate.theorem_name}",
                *certificate.source_references,
                *comparison.external_references,
            )
        )
    )
    return OntologyIssue(
        issue_id=(
            "issue:cross-ontology:"
            f"{certificate.subject_ref}:{certificate.predicate_ref}:{certificate.object_ref}"
        ),
        issue_type="cross_ontology_explicit_relation_conflict",
        scope="wikidata_ontology",
        subject_ids=(certificate.subject_ref, certificate.object_ref),
        status="review_required",
        confidence_band="high",
        reason_codes=("formal_relation_conflict", "explicit_opposing_evidence"),
        evidence_refs=evidence_refs,
        details={
            "relation_kind": certificate.relation_kind,
            "predicate_ref": certificate.predicate_ref,
            "lean_state": certificate.epistemic_state,
            "external_state": comparison.external_state,
            "checker_name": certificate.checker_name,
            "module_name": certificate.module_name,
            "theorem_name": certificate.theorem_name,
            "source_snapshot": certificate.source_snapshot,
            "truth_authority": False,
            "edit_authority": False,
        },
    )


def detect_ontology_issues(
    *,
    relation_rows: Sequence[Mapping[str, Any]] | None = None,
    equivalence_clusters: Sequence[Mapping[str, Any]] | None = None,
    source_system: str = "wikidata",
    type_probing_surface: Mapping[str, Any] | None = None,
    operator_review_surface: Mapping[str, Any] | None = None,
    formal_relation_comparisons: Sequence[Mapping[str, Any]] | None = None,
) -> list[OntologyIssue]:
    del relation_rows, equivalence_clusters
    if source_system != "wikidata":
        return []

    if formal_relation_comparisons is not None:
        issues = [
            issue
            for row in formal_relation_comparisons
            if isinstance(row, Mapping)
            for issue in [_issue_from_formal_relation_comparison(row)]
            if issue is not None
        ]
        return sorted(issues, key=lambda issue: issue.issue_id)

    if type_probing_surface is not None:
        probe_rows = type_probing_surface.get("probe_rows")
        if not isinstance(probe_rows, list):
            raise ValueError("type_probing_surface requires probe_rows")
        lane_id = _stringify(type_probing_surface.get("lane_id")).strip()
        cohort_id = _stringify(type_probing_surface.get("cohort_id")).strip()
        required_reviewer_checks = type_probing_surface.get("required_reviewer_checks")
        if not isinstance(required_reviewer_checks, list):
            required_reviewer_checks = []
        issues = [
            issue
            for row in probe_rows
            if isinstance(row, Mapping)
            for issue in [
                _issue_from_probe_row(
                    row,
                    lane_id=lane_id,
                    cohort_id=cohort_id,
                    required_reviewer_checks=required_reviewer_checks,
                )
            ]
            if issue is not None
        ]
        return sorted(issues, key=lambda issue: issue.issue_id)

    if operator_review_surface is not None:
        queue_rows = operator_review_surface.get("operator_queue")
        if not isinstance(queue_rows, list):
            raise ValueError("operator_review_surface requires operator_queue")
        lane_id = _stringify(operator_review_surface.get("lane_id")).strip()
        cohort_id = _stringify(operator_review_surface.get("cohort_id")).strip()
        required_reviewer_checks = operator_review_surface.get("required_checklist")
        if not isinstance(required_reviewer_checks, list):
            required_reviewer_checks = []
        issues = [
            issue
            for row in queue_rows
            if isinstance(row, Mapping)
            for issue in [
                _issue_from_probe_row(
                    row,
                    lane_id=lane_id,
                    cohort_id=cohort_id,
                    required_reviewer_checks=required_reviewer_checks,
                )
            ]
            if issue is not None
        ]
        return sorted(issues, key=lambda issue: issue.issue_id)

    return []
