from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


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
            "smallest_typing_check": _stringify(row.get("smallest_typing_check")).strip() or None,
            "recommended_next_step": _stringify(row.get("recommended_next_step")).strip() or None,
            "packet_status": _stringify(row.get("packet_status")).strip() or None,
            "uncertainty_flags": _string_list(row.get("uncertainty_flags")),
            "required_reviewer_checks": reviewer_checks,
        },
    )


def detect_ontology_issues(
    *,
    relation_rows: Sequence[Mapping[str, Any]] | None = None,
    equivalence_clusters: Sequence[Mapping[str, Any]] | None = None,
    source_system: str = "wikidata",
    type_probing_surface: Mapping[str, Any] | None = None,
    operator_review_surface: Mapping[str, Any] | None = None,
) -> list[OntologyIssue]:
    del relation_rows, equivalence_clusters
    if source_system != "wikidata":
        return []

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
            for issue in [_issue_from_probe_row(
                row,
                lane_id=lane_id,
                cohort_id=cohort_id,
                required_reviewer_checks=required_reviewer_checks,
            )]
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
            for issue in [_issue_from_probe_row(
                row,
                lane_id=lane_id,
                cohort_id=cohort_id,
                required_reviewer_checks=required_reviewer_checks,
            )]
            if issue is not None
        ]
        return sorted(issues, key=lambda issue: issue.issue_id)

    return []
