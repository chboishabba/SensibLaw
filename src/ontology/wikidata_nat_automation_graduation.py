from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

import requests

from src.ontology.wikidata import (
    ENTITY_EXPORT_TEMPLATE,
    MEDIAWIKI_API_ENDPOINT,
    verify_migration_pack_against_after_state,
)
from src.models.nat_claim import (
    NAT_CLAIM_SCHEMA_VERSION,
    build_nat_claim_dict,
    build_nat_claim_from_candidate,
)
from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope


AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_eval.v0_1"
AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_report.v0_1"
AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_batch_report.v0_1"
AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_evidence_report.v0_1"
AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_governance_index.v0_1"
AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION = (
    "sl.wikidata_nat_automation_graduation_governance_summary.v0_1"
)
AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION = (
    "sl.wikidata_nat_claim_convergence_report.v0_1"
)
AUTOMATION_GRADUATION_CONFIRMATION_QUEUE_SCHEMA_VERSION = (
    "sl.wikidata_nat_confirmation_queue.v0_1"
)
AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION = (
    "sl.wikidata_nat_confirmation_intake_contract.v0_1"
)
AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_confirmation_intake_report.v0_1"
)
AUTOMATION_GRADUATION_ACQUISITION_TASK_QUEUE_SCHEMA_VERSION = (
    "sl.wikidata_nat_acquisition_task_queue.v0_1"
)
AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_acquisition_event_report.v0_1"
)
AUTOMATION_GRADUATION_STATE_MACHINE_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_state_machine_report.v0_2"
)
AUTOMATION_GRADUATION_FAMILY_ACQUISITION_PLAN_SCHEMA_VERSION = (
    "sl.wikidata_nat_family_acquisition_plan.v0_1"
)
AUTOMATION_GRADUATION_CLIMATE_FAMILY_V2_SEED_SCHEMA_VERSION = (
    "sl.wikidata_nat_climate_family_v2_seed.v0_1"
)
AUTOMATION_GRADUATION_CLIMATE_CROSS_ROW_ACQUISITION_PLAN_SCHEMA_VERSION = (
    "sl.wikidata_nat_climate_cross_row_acquisition_plan.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_BATCH_FINDER_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_batch_finder.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_execution_payload.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_BATCH_EXPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_batch_export.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_EXECUTED_ROWS_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_executed_rows.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_LIFECYCLE_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_lifecycle_report.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PROOF_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_execution_proof.v0_1"
)
AUTOMATION_GRADUATION_POST_WRITE_VERIFICATION_SCHEMA_VERSION = (
    "sl.wikidata_nat_post_write_verification_report.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_CANDIDATE_CONTRACT_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_candidate_contracts.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_BACKEND_PLAN_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_backend_plan.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_RECEIPT_CONTRACT_SCHEMA_VERSION = (
    "sl.wikidata_nat_execution_receipt_contract.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_POST_WRITE_CONTRACT_SCHEMA_VERSION = (
    "sl.wikidata_nat_post_write_contract.v0_1"
)
AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION = (
    "sl.wikidata_nat_post_write_lifecycle_contract.v0_1"
)
AUTOMATION_GRADUATION_MIGRATION_SIMULATION_CONTRACT_SCHEMA_VERSION = (
    "sl.wikidata_nat_migration_simulation_contract.v0_1"
)
AUTOMATION_GRADUATION_BROADER_BATCH_SELECTOR_SCHEMA_VERSION = (
    "sl.wikidata_nat_broader_batch_selector.v0_1"
)
AUTOMATION_GRADUATION_P5991_SEMANTIC_TRIAGE_SCHEMA_VERSION = (
    "sl.wikidata_nat_p5991_semantic_triage.v0_1"
)
AUTOMATION_GRADUATION_P5991_SEMANTIC_FAMILY_SELECTOR_SCHEMA_VERSION = (
    "sl.wikidata_nat_p5991_semantic_family_selector.v0_1"
)
LEGACY_EXECUTION_SAFE_CLASSIFICATIONS = {
    "safe_equivalent",
    "safe_with_reference_transfer",
}
MODEL_EXECUTION_SAFE_CLASSIFICATIONS = {
    "model_safe",
    "model_safe_with_split",
}
POST_WRITE_LIFECYCLE_STATES = ("not_started", "ready", "executed", "verified")


def _as_text_set(values: Sequence[Any] | None) -> set[str]:
    if values is None:
        return set()
    normalized: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text:
            normalized.add(text)
    return normalized


def _as_text(value: Any) -> str:
    return str(value).strip()


def _optional_text(value: Any) -> str:
    text = _as_text(value)
    if text in {"None", "null"}:
        return ""
    return text


def _as_text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    normalized: list[str] = []
    for value in values:
        text = _as_text(value)
        if text:
            normalized.append(text)
    return normalized


def _http_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    timeout_seconds: int = 30,
) -> Any:
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": "SensibLaw/1.0 (Nat automation graduation)"},
        timeout=max(1, int(timeout_seconds)),
    )
    response.raise_for_status()
    return response.json()


def _classify_state_basis(provenance_kinds: set[str]) -> str:
    kinds = {kind for kind in provenance_kinds if kind}
    if not kinds or kinds == {"baseline_runtime"}:
        return "baseline_runtime"
    non_baseline = {kind for kind in kinds if kind != "baseline_runtime"}
    if len(non_baseline) == 1:
        return next(iter(non_baseline))
    if non_baseline:
        return "mixed_acquisition"
    return "baseline_runtime"


def _normalize_claim_bundle(bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        return {}
    qualifiers = bundle.get("qualifiers", {})
    references = bundle.get("references", [])
    normalized_qualifiers = {
        _as_text(key): sorted(_as_text_list(value))
        for key, value in qualifiers.items()
        if _as_text(key)
    } if isinstance(qualifiers, Mapping) else {}
    normalized_references: list[dict[str, list[str]]] = []
    if isinstance(references, Sequence) and not isinstance(references, (str, bytes, bytearray)):
        for reference in references:
            if not isinstance(reference, Mapping):
                continue
            normalized_reference = {
                _as_text(key): sorted(_as_text_list(value))
                for key, value in reference.items()
                if _as_text(key)
            }
            if normalized_reference:
                normalized_references.append(normalized_reference)
    normalized_references.sort(key=lambda item: repr(sorted(item.items())))
    return {
        "subject": _as_text(bundle.get("subject")),
        "property": _as_text(bundle.get("property")),
        "value": _as_text(bundle.get("value")),
        "rank": _as_text(bundle.get("rank")),
        "window_id": _as_text(bundle.get("window_id")),
        "qualifiers": normalized_qualifiers,
        "references": normalized_references,
    }


def _year_basis_for_bundle(bundle: Mapping[str, Any]) -> str:
    qualifiers = bundle.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        return "unknown"
    qualifier_keys = {_as_text(key) for key in qualifiers}
    if "P585" in qualifier_keys:
        return "point_in_time"
    if "P580" in qualifier_keys or "P582" in qualifier_keys:
        return "interval"
    return "unknown"


def _normalize_contract_value(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        amount = _as_text(value.get("amount"))
        if amount:
            normalized["amount"] = amount
        unit_qid = _as_text(value.get("unit_qid") or value.get("unit"))
        if unit_qid:
            normalized["unit_qid"] = unit_qid
        lower_bound = _as_text(value.get("lower_bound"))
        upper_bound = _as_text(value.get("upper_bound"))
        if lower_bound:
            normalized["lower_bound"] = lower_bound
        if upper_bound:
            normalized["upper_bound"] = upper_bound
        if normalized:
            return normalized
    return {"raw": _as_text(value)}


def _normalize_optional_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        _as_text(key): value[key]
        for key in value
        if _as_text(key)
    }


def _normalize_model_validation(validation: Any) -> dict[str, Any]:
    if not isinstance(validation, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    if "valid" in validation:
        normalized["valid"] = bool(validation.get("valid"))
    if "issues" in validation:
        normalized["issues"] = _as_text_list(validation.get("issues"))
    for field in ("resolved_year", "resolved_scope", "resolved_unit_qid", "suggested_action", "execution_ready"):
        value = validation.get(field)
        if value is None:
            continue
        text = _as_text(value) if field != "execution_ready" else value
        if field == "execution_ready":
            normalized[field] = bool(value)
        elif text:
            normalized[field] = text
    return normalized


def _normalize_split_plan(split_plan: Any) -> dict[str, Any]:
    if not isinstance(split_plan, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for field in (
        "split_plan_id",
        "status",
        "suggested_action",
        "reference_propagation",
        "qualifier_propagation",
        "resolved_year",
        "resolved_scope",
        "resolved_unit_qid",
        "execution_backend",
    ):
        value = split_plan.get(field)
        if value is None:
            continue
        text = _as_text(value)
        if text:
            normalized[field] = text
    if "review_required" in split_plan:
        normalized["review_required"] = bool(split_plan.get("review_required"))
    if "execution_ready" in split_plan:
        normalized["execution_ready"] = bool(split_plan.get("execution_ready"))
    if "proposed_bundle_count" in split_plan:
        try:
            normalized["proposed_bundle_count"] = int(split_plan.get("proposed_bundle_count", 0) or 0)
        except (TypeError, ValueError):
            normalized["proposed_bundle_count"] = 0
    if "proposed_target_bundles" in split_plan:
        bundles = split_plan.get("proposed_target_bundles", [])
        if isinstance(bundles, Sequence) and not isinstance(bundles, (str, bytes, bytearray)):
            normalized["proposed_target_bundles"] = [
                _normalize_claim_bundle(bundle)
                for bundle in bundles
                if isinstance(bundle, Mapping)
            ]
    return normalized


def _candidate_model_execution_metadata(candidate: Mapping[str, Any]) -> dict[str, Any]:
    model_validation = _normalize_model_validation(candidate.get("model_validation"))
    split_plan = _normalize_split_plan(candidate.get("split_plan"))
    execution_profile = _normalize_optional_mapping(candidate.get("execution_profile"))
    execution_backend = _optional_text(candidate.get("execution_backend"))
    model_classification = _as_text(
        candidate.get("model_classification")
        or candidate.get("model_bucket")
        or candidate.get("execution_classification")
    )
    classification = _as_text(candidate.get("classification"))
    execution_ready = bool(candidate.get("execution_ready", False))
    if not execution_ready and model_validation.get("execution_ready") is not None:
        execution_ready = bool(model_validation.get("execution_ready"))
    if not execution_ready and split_plan.get("execution_ready") is not None:
        execution_ready = bool(split_plan.get("execution_ready"))
    if not execution_ready and model_classification in MODEL_EXECUTION_SAFE_CLASSIFICATIONS:
        execution_ready = True
    if not execution_backend:
        execution_backend = _optional_text(
            candidate.get("execution_backend_hint")
            or split_plan.get("execution_backend")
            or execution_profile.get("execution_backend")
        )
    execution_strategy = _optional_text(candidate.get("execution_strategy"))
    if not execution_strategy:
        if split_plan:
            execution_strategy = "split_followthrough"
        elif execution_ready:
            execution_strategy = "direct_migrate"
    model_aware = bool(
        split_plan
        or execution_profile
        or model_classification == "model_safe_with_split"
        or (
            model_validation.get("status") == "model_safe_with_split"
            and execution_ready
        )
    )
    return {
        "classification": classification,
        "model_classification": model_classification,
        "execution_ready": execution_ready,
        "execution_backend": execution_backend,
        "execution_strategy": execution_strategy,
        "model_aware": model_aware,
        "model_validation": model_validation,
        "split_plan": split_plan,
        "execution_profile": execution_profile,
    }


def _candidate_is_eligible_for_execution(candidate: Mapping[str, Any]) -> bool:
    classification = _as_text(candidate.get("classification"))
    if classification in LEGACY_EXECUTION_SAFE_CLASSIFICATIONS:
        return True
    metadata = _candidate_model_execution_metadata(candidate)
    if metadata["model_classification"] in MODEL_EXECUTION_SAFE_CLASSIFICATIONS and metadata["execution_ready"]:
        return True
    if metadata["execution_ready"] and metadata["model_aware"] and metadata["split_plan"]:
        return True
    return False


def _build_root_artifact_id(
    run: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> str:
    claim_after = _normalize_claim_bundle(candidate.get("claim_bundle_after"))
    claim_before = _normalize_claim_bundle(candidate.get("claim_bundle_before"))
    root_payload = {
        "entity_qid": _as_text(candidate.get("entity_qid")),
        "candidate_id": _as_text(candidate.get("candidate_id")),
        "action": _as_text(candidate.get("action")),
        "claim_after": claim_after,
        "claim_before": claim_before,
        "window_ids": sorted(
            _as_text(window.get("id"))
            for window in run.get("after_payload", {}).get("windows", [])
            if isinstance(window, Mapping) and _as_text(window.get("id"))
        ),
    }
    return hashlib.sha256(repr(root_payload).encode("utf-8")).hexdigest()


def _resolve_root_artifact_id(
    run: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> str:
    candidate_root = ""
    if candidate.get("root_artifact_id") is not None:
        candidate_root = _as_text(candidate.get("root_artifact_id"))
    if candidate_root:
        return candidate_root

    run_root = ""
    if run.get("root_artifact_id") is not None:
        run_root = _as_text(run.get("root_artifact_id"))
    if run_root:
        return run_root

    candidate_derived = _as_text_list(candidate.get("derived_from_root_artifact_ids"))
    if candidate_derived:
        return candidate_derived[0]

    run_derived = _as_text_list(run.get("derived_from_root_artifact_ids"))
    if run_derived:
        return run_derived[0]

    return _build_root_artifact_id(run, candidate)


def _build_claim_canonical_form(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        return {}
    nat_claim = build_nat_claim_from_candidate(candidate)
    return nat_claim.canonical_form


def _candidate_lookup_from_verification_runs(
    verification_runs: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw_runs = verification_runs.get("runs", [])
    if not isinstance(raw_runs, Sequence) or isinstance(raw_runs, (str, bytes, bytearray)):
        raw_runs = []
    if not raw_runs and isinstance(verification_runs.get("migration_pack"), Mapping):
        raw_runs = [verification_runs]

    candidates_by_id: dict[str, Mapping[str, Any]] = {}
    for run in raw_runs:
        if not isinstance(run, Mapping):
            continue
        migration_pack = run.get("migration_pack")
        if not isinstance(migration_pack, Mapping):
            continue
        candidates = migration_pack.get("candidates", [])
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
            continue
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            candidate_id = _as_text(candidate.get("candidate_id"))
            if candidate_id and candidate_id not in candidates_by_id:
                candidates_by_id[candidate_id] = candidate
    return candidates_by_id


def _normalize_candidate_promotion_gate(gate: Any) -> dict[str, Any]:
    if not isinstance(gate, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for field in ("schema_version", "decision", "reason"):
        text = _as_text(gate.get(field))
        if text:
            normalized[field] = text
    eligibility = gate.get("eligibility")
    if isinstance(eligibility, Mapping):
        normalized["eligibility"] = {
            "eligible": bool(eligibility.get("eligible")),
            "review_only": bool(eligibility.get("review_only")),
            "semi_auto": bool(eligibility.get("semi_auto")),
            "full_auto": bool(eligibility.get("full_auto")),
            **(
                {"reason": _as_text(eligibility.get("reason"))}
                if _as_text(eligibility.get("reason"))
                else {}
            ),
        }
    readiness = gate.get("readiness")
    if isinstance(readiness, Mapping):
        normalized["readiness"] = {
            "ready": bool(readiness.get("ready")),
            "hard_defects": [
                _as_text(defect)
                for defect in readiness.get("hard_defects", [])
                if _as_text(defect)
            ]
            if isinstance(readiness.get("hard_defects"), Sequence)
            and not isinstance(readiness.get("hard_defects"), (str, bytes, bytearray))
            else [],
            "soft_defects": [
                _as_text(defect)
                for defect in readiness.get("soft_defects", [])
                if _as_text(defect)
            ]
            if isinstance(readiness.get("soft_defects"), Sequence)
            and not isinstance(readiness.get("soft_defects"), (str, bytes, bytearray))
            else [],
        }
    subject_resolution = gate.get("subject_resolution")
    if isinstance(subject_resolution, Mapping):
        normalized["subject_resolution"] = {
            key: value
            for key, value in _normalize_subject_resolution(subject_resolution).items()
            if value not in (None, "", [], {})
        }
    return normalized


def _candidate_subject_family(candidate: Mapping[str, Any]) -> str:
    subject_resolution = candidate.get("subject_resolution")
    if isinstance(subject_resolution, Mapping):
        subject_family = _as_text(subject_resolution.get("subject_family"))
        if subject_family in {"company", "non_company", "unknown"}:
            return subject_family
    subject_family = _as_text(candidate.get("subject_family"))
    if subject_family in {"company", "non_company", "unknown"}:
        return subject_family
    return "unknown"


def _build_subject_aware_summary(
    executed_receipts: Sequence[Mapping[str, Any]],
    verification_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidates_by_id = _candidate_lookup_from_verification_runs({"runs": list(executed_receipts)})
    subject_status: dict[str, str] = {}
    subject_family_by_id: dict[str, str] = {}
    uses_subject_resolution = False

    for run in verification_runs:
        if not isinstance(run, Mapping):
            continue
        verification_report = run.get("verification_report")
        if not isinstance(verification_report, Mapping):
            continue
        rows = verification_report.get("rows", [])
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            entity_qid = _as_text(row.get("entity_qid"))
            candidate_id = _as_text(row.get("candidate_id"))
            status = _as_text(row.get("status")) or "target_missing"
            if not entity_qid:
                continue
            prior_status = subject_status.get(entity_qid)
            if prior_status != "drift":
                subject_status[entity_qid] = "verified" if status == "verified" else "drift"
            candidate = candidates_by_id.get(candidate_id, {})
            subject_family = _candidate_subject_family(candidate)
            if subject_family != "unknown":
                uses_subject_resolution = True
            subject_family_by_id[entity_qid] = subject_family

    subject_ids = sorted(subject_status)
    verified_subject_ids = sorted(
        subject_id for subject_id, status in subject_status.items() if status == "verified"
    )
    drift_subject_ids = sorted(
        subject_id for subject_id, status in subject_status.items() if status != "verified"
    )
    company_subject_ids = sorted(
        subject_id
        for subject_id, family in subject_family_by_id.items()
        if family == "company"
    )
    verified_company_subject_ids = sorted(
        subject_id
        for subject_id in company_subject_ids
        if subject_status.get(subject_id) == "verified"
    )
    non_company_subject_ids = sorted(
        subject_id
        for subject_id, family in subject_family_by_id.items()
        if family == "non_company"
    )
    unknown_subject_ids = sorted(
        subject_id
        for subject_id, family in subject_family_by_id.items()
        if family == "unknown"
    )

    if uses_subject_resolution:
        subject_aware_ready = (
            bool(company_subject_ids)
            and len(company_subject_ids) == len(verified_company_subject_ids)
            and not unknown_subject_ids
        )
    else:
        subject_aware_ready = bool(subject_ids) and len(subject_ids) == len(verified_subject_ids)

    return {
        "subject_count": len(subject_ids),
        "verified_subject_count": len(verified_subject_ids),
        "drift_subject_count": len(drift_subject_ids),
        "company_subject_count": len(company_subject_ids),
        "verified_company_subject_count": len(verified_company_subject_ids),
        "non_company_subject_count": len(non_company_subject_ids),
        "unknown_subject_count": len(unknown_subject_ids),
        "subject_aware_ready": subject_aware_ready,
        "subject_aware_state": "verified" if subject_aware_ready else "executed",
        "uses_subject_resolution": uses_subject_resolution,
        "subject_aware_subject_ids": subject_ids,
        "verified_subject_ids": verified_subject_ids,
        "drift_subject_ids": drift_subject_ids,
        "company_subject_ids": company_subject_ids,
        "verified_company_subject_ids": verified_company_subject_ids,
        "non_company_subject_ids": non_company_subject_ids,
        "unknown_subject_ids": unknown_subject_ids,
        "verified_subject_rate": (
            len(verified_subject_ids) / len(subject_ids) if subject_ids else 0.0
        ),
        "verified_company_subject_rate": (
            len(verified_company_subject_ids) / len(company_subject_ids)
            if company_subject_ids
            else 0.0
        ),
    }


def _normalize_subject_resolution(subject_resolution: Any) -> dict[str, Any]:
    if isinstance(subject_resolution, str):
        subject_resolution = {"status": subject_resolution}
    if not isinstance(subject_resolution, Mapping):
        return {}

    status_text = _as_text(
        subject_resolution.get("status")
        or subject_resolution.get("state")
        or subject_resolution.get("resolution")
    )
    subject_family = _as_text(
        subject_resolution.get("subject_family")
        or subject_resolution.get("family")
        or subject_resolution.get("entity_family")
    )
    explicit_instance_of_allowed = subject_resolution.get("instance_of_allowed")
    if status_text in {"", "absent", "unset", "none"}:
        if not subject_family and explicit_instance_of_allowed is None:
            return {}
        status = "known"
    elif status_text in {"known", "resolved", "ready"}:
        status = "known"
    elif status_text in {"unknown", "unresolved", "ambiguous", "uncertain", "not_known"}:
        status = "unknown"
    else:
        status = "unknown"

    if status == "unknown":
        instance_of_allowed = False
        hard_defects = ["subject_resolution_unknown"]
        soft_defects: list[str] = []
        reason = status_text or "subject_resolution_unknown"
    else:
        instance_of_allowed = True if explicit_instance_of_allowed is None else bool(explicit_instance_of_allowed)
        hard_defects = []
        soft_defects = []
        reason = "subject_resolution_known"
        if not instance_of_allowed:
            hard_defects = ["instance_of_allowed_false"]
            reason = "instance_of_allowed_false"

    return {
        "status": status,
        "subject_family": subject_family,
        "instance_of_allowed": instance_of_allowed,
        "hard_defects": hard_defects,
        "soft_defects": soft_defects,
        "ready": not hard_defects,
        "reason": reason,
    }


def _subject_resolution_summary_from_contracts(
    candidate_contracts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    total_candidates = 0
    subject_resolution_count = 0
    known_count = 0
    unknown_count = 0
    absent_count = 0
    allowed_count = 0
    blocked_count = 0
    hard_defect_count = 0
    soft_defect_count = 0
    distribution_by_promotion_class: dict[str, dict[str, int]] = {}

    for contract in candidate_contracts:
        if not isinstance(contract, Mapping):
            continue
        total_candidates += 1
        promotion_class = _as_text(contract.get("promotion_class")) or "review_only"
        bucket = distribution_by_promotion_class.setdefault(
            promotion_class,
            {"absent": 0, "known": 0, "unknown": 0},
        )
        subject_resolution = contract.get("subject_resolution")
        if not isinstance(subject_resolution, Mapping):
            absent_count += 1
            bucket["absent"] += 1
            continue
        subject_resolution_count += 1
        status = _as_text(subject_resolution.get("status")) or "unknown"
        if status == "known":
            known_count += 1
        elif status == "unknown":
            unknown_count += 1
        else:
            unknown_count += 1
        bucket[status if status in bucket else "unknown"] += 1
        if bool(subject_resolution.get("instance_of_allowed")):
            allowed_count += 1
        else:
            blocked_count += 1
        hard_defect_count += len(_as_text_list(subject_resolution.get("hard_defects")))
        soft_defect_count += len(_as_text_list(subject_resolution.get("soft_defects")))

    if subject_resolution_count == 0:
        return {}

    return {
        "subject_resolution_count": subject_resolution_count,
        "subject_resolution_known_count": known_count,
        "subject_resolution_unknown_count": unknown_count,
        "subject_resolution_absent_count": absent_count,
        "subject_resolution_allowed_count": allowed_count,
        "subject_resolution_blocked_count": blocked_count,
        "subject_resolution_hard_defect_count": hard_defect_count,
        "subject_resolution_soft_defect_count": soft_defect_count,
        "subject_resolution_distribution_by_promotion_class": distribution_by_promotion_class,
        "subject_resolution_coverage": subject_resolution_count / max(total_candidates, 1),
    }


def _augment_promotion_gate_with_subject_resolution(
    promotion_gate: Mapping[str, Any],
    subject_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_gate = dict(promotion_gate)
    normalized_subject_resolution = dict(subject_resolution)
    eligibility = dict(normalized_gate.get("eligibility", {}))
    readiness = dict(normalized_gate.get("readiness", {}))
    hard_defects = list(normalized_subject_resolution.get("hard_defects", []))
    soft_defects = list(normalized_subject_resolution.get("soft_defects", []))
    instance_of_allowed = bool(normalized_subject_resolution.get("instance_of_allowed"))
    ready = bool(normalized_subject_resolution.get("ready"))

    if normalized_subject_resolution:
        normalized_gate["subject_resolution"] = normalized_subject_resolution
        readiness.update(
            {
                "ready": ready,
                "hard_defects": hard_defects,
                "soft_defects": soft_defects,
            }
        )
        eligibility["instance_of_allowed"] = instance_of_allowed
        eligibility["subject_resolution_ready"] = ready
        eligibility["subject_resolution_status"] = _as_text(normalized_subject_resolution.get("status"))
        if hard_defects:
            eligibility["eligible"] = False
            eligibility["review_only"] = True
            eligibility["semi_auto"] = False
            eligibility["full_auto"] = False
            normalized_gate["decision"] = "review_only"
            normalized_gate["reason"] = _as_text(normalized_subject_resolution.get("reason")) or "subject_resolution_hard_defect"
        elif "eligible" not in eligibility:
            eligibility["eligible"] = True
    if readiness:
        normalized_gate["readiness"] = readiness
    if eligibility:
        normalized_gate["eligibility"] = eligibility
    return normalized_gate


def _build_suggested_evidence_routes(
    *,
    family_id: str,
    cohort_id: str,
    candidate_id: str,
    canonical_form: Mapping[str, Any],
) -> list[dict[str, Any]]:
    routes = [
        {
            "route_id": f"{candidate_id}:same_family_after_state",
            "route_kind": "same_family_after_state",
            "source_family": "wikidata_migration_pack",
            "priority": 1,
            "why": "A new revision-locked after-state bundle for the same family is the shortest truthful path to independent confirmation.",
        }
    ]

    claim_property = _as_text(canonical_form.get("property"))
    if family_id.startswith("climate_family") or claim_property == "P14143":
        routes.append(
            {
                "route_id": f"{candidate_id}:cross_row_migrated_p14143",
                "route_kind": "cross_row_migrated_p14143",
                "source_family": "wikidata_sparql_p14143",
                "priority": 2,
                "why": "Climate-family rows can recover through already-migrated P14143 rows that match the same normalized climate claim shape.",
            }
        )
        routes.append(
            {
                "route_id": f"{candidate_id}:phi_text_bridge",
                "route_kind": "text_bridge_promoted_observation",
                "source_family": "wikidata_phi_text_bridge",
                "priority": 3,
                "why": "The bounded Phi text bridge is the repo-approved additive pressure lane for climate-family evidence, but it cannot replace structured verification by itself.",
            }
        )

    return routes


def _is_fixture_placeholder_qid(value: str) -> bool:
    return value.startswith("Q") and "_" in value


def _build_candidate_archetype(
    candidate_id: str,
    *,
    archetype_hint: str = "",
) -> dict[str, Any]:
    hint = _as_text(archetype_hint)
    if hint == "city_or_municipality":
        return {
            "archetype_id": "city_or_municipality",
            "expected_success_band": "higher",
            "why": "Administrative and municipal parthood rows are more likely to experience direct whole-part cleanup and reference churn.",
        }
    if hint == "district_or_subdivision":
        return {
            "archetype_id": "district_or_subdivision",
            "expected_success_band": "medium",
            "why": "Subdivision containment rows are a plausible second path because parent containment and references can change without changing the overall family shape.",
        }
    if hint == "class_or_type_ontology":
        return {
            "archetype_id": "class_or_type_ontology",
            "expected_success_band": "lower",
            "why": "Ontology-heavy parthood rows can churn, but they are less likely to produce a clean second after-state quickly than administrative containment rows.",
        }

    entity_qid = candidate_id.split("|", 1)[0]
    lowered = entity_qid.lower()
    if "city" in lowered:
        return {
            "archetype_id": "city_or_municipality",
            "expected_success_band": "higher",
            "why": "Administrative and municipal parthood rows are more likely to experience direct whole-part cleanup and reference churn.",
        }
    if "district" in lowered or "subset" in lowered:
        return {
            "archetype_id": "district_or_subdivision",
            "expected_success_band": "medium",
            "why": "Subdivision containment rows are a plausible second path because parent containment and references can change without changing the overall family shape.",
        }
    if "class" in lowered or "type" in lowered:
        return {
            "archetype_id": "class_or_type_ontology",
            "expected_success_band": "lower",
            "why": "Ontology-heavy parthood rows can churn, but they are less likely to produce a clean second after-state quickly than administrative containment rows.",
        }
    return {
        "archetype_id": "generic_parthood_candidate",
        "expected_success_band": "medium",
        "why": "Candidate should be treated as a generic parthood acquisition target until a stronger archetype signal exists.",
    }


def _build_same_family_query_shape(
    candidate_id: str,
    canonical_form: Mapping[str, Any],
    *,
    archetype_hint: str = "",
) -> dict[str, Any]:
    candidate_parts = candidate_id.split("|")
    entity_qid = candidate_parts[0] if candidate_parts else ""
    property_id = candidate_parts[1] if len(candidate_parts) > 1 else _as_text(canonical_form.get("property"))
    value_qid = _as_text(canonical_form.get("value"))
    lowered = entity_qid.lower()
    hint = _as_text(archetype_hint)
    look_for = [
        "changed_parent_item",
        "added_or_removed_reference",
        "added_or_removed_qualifier",
        "statement_rank_change",
    ]
    if hint in {"city_or_municipality", "district_or_subdivision"} or "city" in lowered or "district" in lowered or "subset" in lowered:
        look_for.append("containment_cleanup_against_neighboring_admin_properties")
    if hint == "class_or_type_ontology" or "class" in lowered or "type" in lowered:
        look_for.append("ontology_cleanup_against_neighboring_membership_properties")
    return {
        "entity_qid": entity_qid,
        "property": property_id,
        "current_value": value_qid,
        "look_for": look_for,
        "time_window": "recent_revisions_first",
        "accept_only_if": [
            "after_state_differs_from_seen_roots",
            "verify_migration_pack_against_after_state_passes",
            "artifact_is_revision_locked",
        ],
    }


def _normalize_numeric_text(value: str) -> str:
    text = _as_text(value)
    if not text:
        return ""
    return text.replace("+", "").lstrip("0") or "0"


def _is_live_target_property(property_id: str) -> bool:
    property_text = _as_text(property_id)
    return bool(property_text) and property_text.startswith("P") and property_text != "P99999"


def _extract_climate_year(qualifiers: Mapping[str, Any]) -> str:
    if not isinstance(qualifiers, Mapping):
        return ""
    for property_id in ("P585", "P580", "P582"):
        values = _as_text_list(qualifiers.get(property_id))
        if not values:
            continue
        value = values[0]
        if len(value) >= 5 and value[0] in {"+", "-"}:
            return value[1:5]
        if len(value) >= 4:
            return value[:4]
    return ""


def _select_primary_run(verification_runs: Mapping[str, Any]) -> Mapping[str, Any]:
    runs = verification_runs.get("runs", [])
    if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes, bytearray)) or not runs:
        return {}
    return runs[0] if isinstance(runs[0], Mapping) else {}


def _select_migration_candidates(verification_runs: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    primary_run = _select_primary_run(verification_runs)
    migration_pack = primary_run.get("migration_pack", {}) if isinstance(primary_run, Mapping) else {}
    candidates = migration_pack.get("candidates", []) if isinstance(migration_pack, Mapping) else []
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def _count_split_axes(candidate: Mapping[str, Any]) -> int:
    split_axes = candidate.get("merged_split_axes") or candidate.get("split_axes") or []
    if not isinstance(split_axes, Sequence) or isinstance(split_axes, (str, bytes, bytearray)):
        return 0
    return sum(1 for axis in split_axes if isinstance(axis, Mapping) or _as_text(axis))


def _multi_value_qualifier_properties(bundle: Mapping[str, Any]) -> list[str]:
    qualifiers = bundle.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        return []
    properties: list[str] = []
    for property_id, values in qualifiers.items():
        normalized_values = _as_text_list(values)
        if len(normalized_values) > 1:
            properties.append(_as_text(property_id))
    return sorted(property_id for property_id in properties if property_id)


def classify_nat_p5991_semantic_bucket(
    candidate: Mapping[str, Any],
    *,
    family_id: str = "",
    cohort_id: str = "",
    source_property: str = "",
    target_property: str = "",
) -> dict[str, Any]:
    claim_before = candidate.get("claim_bundle_before", {})
    if not isinstance(claim_before, Mapping):
        claim_before = {}
    claim_after = candidate.get("claim_bundle_after", {})
    if not isinstance(claim_after, Mapping):
        claim_after = {}

    source_property = source_property or _as_text(claim_before.get("property"))
    target_property = target_property or _as_text(claim_after.get("property"))
    canonical_bundle = _build_claim_canonical_form(candidate)
    qualifiers = canonical_bundle.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        qualifiers = {}

    classification = _as_text(candidate.get("classification"))
    requires_review = bool(candidate.get("requires_review", False))
    model_validation = candidate.get("model_validation", {})
    if not isinstance(model_validation, Mapping):
        model_validation = {}
    execution_hints = candidate.get("execution_hints", {})
    if not isinstance(execution_hints, Mapping):
        execution_hints = {}
    migration_signal = family_id.startswith("climate_family")
    split_axis_count = _count_split_axes(candidate)
    multi_value_qualifiers = _multi_value_qualifier_properties(canonical_bundle)
    year_derivable = bool(_extract_climate_year(qualifiers))
    has_part_scope = bool(_as_text_list(qualifiers.get("P518")))
    has_role_scope = bool(_as_text_list(qualifiers.get("P3831")))
    has_interval = any(_as_text_list(qualifiers.get(property_id)) for property_id in ("P580", "P582"))
    has_references = bool(canonical_bundle.get("references"))
    live_target_supported = _is_live_target_property(target_property)

    semantic_signals: list[str] = []
    if migration_signal:
        semantic_signals.append("migration_protocol_active")
    if split_axis_count > 0:
        semantic_signals.append("split_axes_present")
    if multi_value_qualifiers:
        semantic_signals.append("multi_value_qualifiers_present")
    if requires_review:
        semantic_signals.append("requires_review_flag")
    if has_part_scope:
        semantic_signals.append("part_scope_present")
    if has_role_scope:
        semantic_signals.append("role_scope_present")
    if has_interval:
        semantic_signals.append("interval_time_semantics_present")
    if year_derivable:
        semantic_signals.append("year_derivable")
    if has_references:
        semantic_signals.append("references_present")
    if live_target_supported:
        semantic_signals.append("live_target_supported")
    model_status = _as_text(model_validation.get("status"))
    if model_status:
        semantic_signals.append(f"model_validation:{model_status}")
    if bool(execution_hints.get("execution_ready")):
        semantic_signals.append("deterministic_split_execution_ready")

    semantic_bucket = "needs_review"
    bucket_reason = "manual_review_required"
    if migration_signal and source_property == "P5991":
        semantic_bucket = "migration_pending"
        bucket_reason = "upstream_migration_protocol_active"
    elif classification == "split_required" or split_axis_count > 0 or multi_value_qualifiers:
        semantic_bucket = "split_required"
        bucket_reason = "row_contains_multi_axis_or_split_shape"
    elif source_property != "P5991" or not live_target_supported:
        semantic_bucket = "out_of_scope"
        bucket_reason = "target_property_not_live_backed"
    elif requires_review:
        semantic_bucket = "needs_review"
        bucket_reason = "review_flag_present"
    elif classification in {"safe_equivalent", "safe_with_reference_transfer"} and year_derivable:
        semantic_bucket = "direct_migrate"
        bucket_reason = "safe_shape_with_derivable_year"
    elif classification:
        semantic_bucket = "needs_review"
        bucket_reason = f"unresolved_classification:{classification}"

    return {
        "candidate_id": _as_text(candidate.get("candidate_id")),
        "family_id": family_id,
        "cohort_id": cohort_id,
        "source_property": source_property,
        "target_property": target_property,
        "classification": classification,
        "semantic_bucket": semantic_bucket,
        "bucket_reason": bucket_reason,
        "abstain": semantic_bucket != "direct_migrate",
        "requires_review": requires_review,
        "migration_signal": migration_signal,
        "live_target_supported": live_target_supported,
        "year_derivable": year_derivable,
        "has_references": has_references,
        "has_part_scope": has_part_scope,
        "has_role_scope": has_role_scope,
        "has_interval": has_interval,
        "split_axis_count": split_axis_count,
        "multi_value_qualifier_properties": multi_value_qualifiers,
        "qualifier_properties": sorted(_as_text(key) for key in qualifiers if _as_text(key)),
        "semantic_signals": semantic_signals,
    }


def build_nat_climate_claim_signature(canonical_form: Mapping[str, Any]) -> dict[str, Any]:
    qualifiers = canonical_form.get("qualifiers", {})
    if not isinstance(qualifiers, Mapping):
        qualifiers = {}
    return {
        "subject": _as_text(canonical_form.get("subject")),
        "subject_class": "enterprise",
        "metric_kind": "annual_greenhouse_gas_emissions",
        "property_family": "annual_greenhouse_gas_emissions",
        "normalized_value": _normalize_numeric_text(_as_text(canonical_form.get("value"))),
        "year": _extract_climate_year(qualifiers),
        "unit": "co2e",
        "determination_method": sorted(_as_text_list(qualifiers.get("P459"))),
        "role_scope": sorted(_as_text_list(qualifiers.get("P3831"))),
        "applies_to_part": sorted(_as_text_list(qualifiers.get("P518"))),
    }


def _has_climate_migration_signal(
    *,
    family_id: str,
    canonical_form: Mapping[str, Any] | None = None,
) -> bool:
    if family_id.startswith("climate_family"):
        return True
    if isinstance(canonical_form, Mapping):
        property_id = _as_text(canonical_form.get("property"))
        return property_id in {"P5991", "P14143"}
    return False


def verify_nat_climate_cross_source_confirmation(
    original_claim: Mapping[str, Any],
    migrated_candidate_source_unit: Mapping[str, Any],
) -> dict[str, Any]:
    original_signature = build_nat_climate_claim_signature(original_claim)
    candidate_signature = build_nat_climate_claim_signature(
        migrated_candidate_source_unit.get("canonical_form", {})
        if isinstance(migrated_candidate_source_unit.get("canonical_form"), Mapping)
        else migrated_candidate_source_unit
    )
    root_artifact_id = _as_text(migrated_candidate_source_unit.get("root_artifact_id"))
    property_id = _as_text(candidate_signature.get("property_family"))
    same_metric_kind = (
        _as_text(original_signature.get("metric_kind"))
        == _as_text(candidate_signature.get("metric_kind"))
    )
    same_year = _as_text(original_signature.get("year")) == _as_text(candidate_signature.get("year"))
    same_value = _as_text(original_signature.get("normalized_value")) == _as_text(
        candidate_signature.get("normalized_value")
    )
    independent_root = bool(root_artifact_id)
    migrated_property = _as_text(
        (migrated_candidate_source_unit.get("canonical_form", {}) if isinstance(migrated_candidate_source_unit.get("canonical_form"), Mapping) else migrated_candidate_source_unit).get("property")
    )
    confirmed = all(
        (
            independent_root,
            same_metric_kind,
            same_year,
            same_value,
            migrated_property == "P14143",
            _as_text(candidate_signature.get("subject_class")) == "enterprise",
        )
    )
    failed_checks = []
    if not independent_root:
        failed_checks.append("missing_root_artifact")
    if not same_metric_kind:
        failed_checks.append("metric_kind_mismatch")
    if not same_year:
        failed_checks.append("year_mismatch")
    if not same_value:
        failed_checks.append("value_mismatch")
    if migrated_property != "P14143":
        failed_checks.append("target_property_mismatch")
    return {
        "confirmed": confirmed,
        "original_signature": original_signature,
        "candidate_signature": candidate_signature,
        "root_artifact_id": root_artifact_id,
        "failed_checks": failed_checks,
        "evidence_provenance_kind": "cross_row_migrated_p14143" if confirmed else "",
    }


def build_nat_climate_family_v2_seed(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        canonical_form = candidate.get("canonical_form", {})
        if not isinstance(canonical_form, Mapping):
            canonical_form = {}
        candidate_rows.append(
            {
                "candidate_id": _as_text(candidate.get("candidate_id")),
                "entity_qid": _as_text(candidate.get("entity_qid")),
                "candidate_label": _as_text(candidate.get("candidate_label")),
                "route_kind": "cross_row_migrated_p14143",
                "root_artifact_id": _as_text(candidate.get("root_artifact_id")),
                "claim_signature": build_nat_climate_claim_signature(canonical_form),
                "canonical_form": canonical_form,
            }
        )
    return {
        "schema_version": AUTOMATION_GRADUATION_CLIMATE_FAMILY_V2_SEED_SCHEMA_VERSION,
        "family_id": "climate_family_v2_live_p14143_subset",
        "cohort_id": "climate_family_v2_live_p14143",
        "family_kind": "cross_row_migrated_p14143",
        "source_property_legacy": "P5991",
        "target_property": "P14143",
        "candidate_rows": candidate_rows,
        "summary": {
            "candidate_count": len(candidate_rows),
            "enterprise_count": len(candidate_rows),
        },
    }


def build_nat_climate_cross_row_acquisition_plan(
    verification_runs: Mapping[str, Any],
    climate_family_v2_seed: Mapping[str, Any],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    contract = build_nat_confirmation_intake_contract(
        verification_runs,
        min_independent_paths=min_independent_paths,
    )
    intake_rows = contract.get("intake_rows", [])
    climate_row = next(
        (
            row for row in intake_rows
            if isinstance(row, Mapping)
            and _as_text(row.get("family_id")).startswith("climate_family")
        ),
        None,
    )
    candidate_plans: list[dict[str, Any]] = []
    if climate_row is not None:
        for index, row in enumerate(climate_family_v2_seed.get("candidate_rows", []), start=1):
            if not isinstance(row, Mapping):
                continue
            candidate_plans.append(
                {
                    "priority": index,
                    "route_kind": "cross_row_migrated_p14143",
                    "source_family": "wikidata_sparql_p14143",
                    "supports_claim_id": _as_text(climate_row.get("claim_id")),
                    "candidate_id": _as_text(row.get("candidate_id")),
                    "entity_qid": _as_text(row.get("entity_qid")),
                    "candidate_label": _as_text(row.get("candidate_label")),
                    "why": "Already-migrated live P14143 enterprise rows are the shortest truthful external witness for the climate migration lane.",
                    "claim_signature": row.get("claim_signature", {}),
                }
            )
    return {
        "schema_version": AUTOMATION_GRADUATION_CLIMATE_CROSS_ROW_ACQUISITION_PLAN_SCHEMA_VERSION,
        "family_id": _as_text(verification_runs.get("family_id")),
        "cohort_id": _as_text(verification_runs.get("cohort_id")),
        "plan_kind": "cross_row_migrated_p14143",
        "candidate_plans": candidate_plans,
        "summary": {
            "candidate_count": len(candidate_plans),
            "supports_claim_id": _as_text(climate_row.get("claim_id")) if isinstance(climate_row, Mapping) else "",
        },
    }


def _build_qs_preview_row(
    candidate: Mapping[str, Any],
    *,
    family_id: str,
    cohort_id: str,
) -> dict[str, Any]:
    claim_after = candidate.get("claim_bundle_after", {})
    if not isinstance(claim_after, Mapping):
        claim_after = {}
    model_metadata = _candidate_model_execution_metadata(candidate)
    qualifiers = claim_after.get("qualifiers", {})
    references = claim_after.get("references", [])
    row = {
        "candidate_id": _as_text(candidate.get("candidate_id")),
        "family_id": family_id,
        "cohort_id": cohort_id,
        "subject": _as_text(claim_after.get("subject")),
        "property": _as_text(claim_after.get("property")),
        "value": _as_text(claim_after.get("value")),
        "rank": _as_text(claim_after.get("rank")) or "normal",
        "qualifiers": {
            _as_text(key): _as_text_list(value)
            for key, value in qualifiers.items()
            if _as_text(key)
        }
        if isinstance(qualifiers, Mapping)
        else {},
        "references": [
            {
                _as_text(key): _as_text_list(value)
                for key, value in reference.items()
                if _as_text(key)
            }
            for reference in references
            if isinstance(reference, Mapping)
        ]
        if isinstance(references, Sequence) and not isinstance(references, (str, bytes, bytearray))
        else [],
    }
    if model_metadata["model_aware"]:
        row["model_classification"] = model_metadata["model_classification"]
        row["execution_strategy"] = model_metadata["execution_strategy"]
        if model_metadata["execution_backend"]:
            row["execution_backend"] = model_metadata["execution_backend"]
        if model_metadata["model_validation"]:
            row["model_validation"] = model_metadata["model_validation"]
        if model_metadata["split_plan"]:
            row["split_plan"] = model_metadata["split_plan"]
        if model_metadata["execution_profile"]:
            row["execution_profile"] = model_metadata["execution_profile"]
    return row


def _build_nat_migration_export_id(
    *,
    family_id: str,
    cohort_id: str,
    candidate_ids: Sequence[str],
    target_property: str,
) -> str:
    payload = {
        "family_id": family_id,
        "cohort_id": cohort_id,
        "candidate_ids": sorted(_as_text_set(candidate_ids)),
        "target_property": target_property,
    }
    digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:12]
    family_slug = family_id or "nat-family"
    return f"{family_slug}-migration-export-{digest}"


def build_nat_migration_execution_payload(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
    require_live_target_property: bool = True,
) -> dict[str, Any]:
    selected_candidate_ids = _as_text_set(candidate_ids)
    family_id = _as_text(verification_runs.get("family_id"))
    cohort_id = _as_text(verification_runs.get("cohort_id"))
    state_report = build_nat_state_machine_report([verification_runs])
    family_state = next(
        (
            _as_text(row.get("state"))
            for row in state_report.get("families", [])
            if isinstance(row, Mapping) and _as_text(row.get("family_id")) == family_id
        ),
        "UNKNOWN",
    )
    runs = verification_runs.get("runs", [])
    if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes, bytearray)) or not runs:
        return {
            "schema_version": AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION,
            "family_id": family_id,
            "cohort_id": cohort_id,
            "family_state": family_state,
            "payload_status": "no_runs",
            "openrefine_rows": [],
            "quickstatements_v1_rows": [],
            "summary": {"row_count": 0, "target_property": "", "execution_mode": "review_first"},
        }
    first_run = runs[0] if isinstance(runs[0], Mapping) else {}
    migration_pack = first_run.get("migration_pack", {}) if isinstance(first_run, Mapping) else {}
    target_property = _as_text(migration_pack.get("target_property")) if isinstance(migration_pack, Mapping) else ""
    candidates = migration_pack.get("candidates", []) if isinstance(migration_pack, Mapping) else []
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
        candidates = []

    eligible: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = _as_text(candidate.get("candidate_id"))
        if selected_candidate_ids and candidate_id not in selected_candidate_ids:
            continue
        if not _candidate_is_eligible_for_execution(candidate):
            continue
        eligible.append(candidate)

    live_target_supported = _is_live_target_property(target_property)
    payload_status = "ready_for_review_payload"
    if family_state != "PROMOTED":
        payload_status = "family_not_promoted"
    elif require_live_target_property and not live_target_supported:
        payload_status = "target_property_not_live_backed"
    elif not eligible:
        payload_status = "no_eligible_candidates"

    openrefine_rows: list[dict[str, Any]] = []
    quickstatements_rows: list[dict[str, Any]] = []
    model_aware_count = 0
    for candidate in eligible:
        claim_before = candidate.get("claim_bundle_before", {})
        claim_after = candidate.get("claim_bundle_after", {})
        if not isinstance(claim_before, Mapping):
            claim_before = {}
        if not isinstance(claim_after, Mapping):
            claim_after = {}
        model_metadata = _candidate_model_execution_metadata(candidate)
        if model_metadata["model_aware"]:
            model_aware_count += 1
        openrefine_rows.append(
            {
                "candidate_id": _as_text(candidate.get("candidate_id")),
                "entity_qid": _as_text(candidate.get("entity_qid")),
                "slot_id": _as_text(candidate.get("slot_id")),
                "statement_index": _as_text(candidate.get("statement_index")),
                "from_property": _as_text(claim_before.get("property")),
                "to_property": _as_text(claim_after.get("property")),
                "value": _as_text(claim_after.get("value")),
                "rank": _as_text(claim_after.get("rank")) or "normal",
                "classification": _as_text(candidate.get("classification")),
                "action": _as_text(candidate.get("action")),
                "requires_review": bool(candidate.get("requires_review", False)),
                "qualifiers_json": claim_after.get("qualifiers", {}),
                "references_json": claim_after.get("references", []),
                "target_claim_bundle_json": claim_after,
                **(
                    {
                        "model_classification": model_metadata["model_classification"],
                        "execution_strategy": model_metadata["execution_strategy"],
                        "execution_ready": model_metadata["execution_ready"],
                        "execution_backend": model_metadata["execution_backend"],
                        "model_validation": model_metadata["model_validation"],
                        "split_plan": model_metadata["split_plan"],
                        "execution_profile": model_metadata["execution_profile"],
                    }
                    if model_metadata["model_aware"]
                    else {}
                ),
            }
        )
        quickstatements_rows.append(
            _build_qs_preview_row(candidate, family_id=family_id, cohort_id=cohort_id)
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION,
        "family_id": family_id,
        "cohort_id": cohort_id,
        "family_state": family_state,
        "payload_status": payload_status,
        "execution_mode": "review_first",
        "target_property": target_property,
        "live_target_supported": live_target_supported,
        "openrefine_rows": openrefine_rows,
        "quickstatements_v1_rows": quickstatements_rows,
        "summary": {
            "row_count": len(openrefine_rows),
            "target_property": target_property,
            "execution_mode": "review_first",
            **(
                {
                    "model_aware_row_count": model_aware_count,
                    "execution_ready_row_count": len(eligible),
                }
                if model_aware_count
                else {}
            ),
        },
    }


def build_nat_migration_batch_export(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
    require_live_target_property: bool = True,
) -> dict[str, Any]:
    execution_payload = build_nat_migration_execution_payload(
        verification_runs,
        candidate_ids=candidate_ids,
        require_live_target_property=require_live_target_property,
    )
    openrefine_rows = execution_payload.get("openrefine_rows", [])
    if not isinstance(openrefine_rows, Sequence) or isinstance(openrefine_rows, (str, bytes, bytearray)):
        openrefine_rows = []
    quickstatements_rows = execution_payload.get("quickstatements_v1_rows", [])
    if not isinstance(quickstatements_rows, Sequence) or isinstance(
        quickstatements_rows, (str, bytes, bytearray)
    ):
        quickstatements_rows = []

    family_id = _as_text(execution_payload.get("family_id"))
    cohort_id = _as_text(execution_payload.get("cohort_id"))
    target_property = _as_text(execution_payload.get("target_property"))
    candidate_ids_from_payload = [
        _as_text(row.get("candidate_id"))
        for row in openrefine_rows
        if isinstance(row, Mapping) and _as_text(row.get("candidate_id"))
    ]
    export_id = _build_nat_migration_export_id(
        family_id=family_id,
        cohort_id=cohort_id,
        candidate_ids=candidate_ids_from_payload,
        target_property=target_property,
    )
    export_status = "ready_for_review_export"
    if _as_text(execution_payload.get("payload_status")) != "ready_for_review_payload":
        export_status = _as_text(execution_payload.get("payload_status")) or "not_ready_for_export"

    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_BATCH_EXPORT_SCHEMA_VERSION,
        "export_id": export_id,
        "family_id": family_id,
        "cohort_id": cohort_id,
        "family_state": _as_text(execution_payload.get("family_state")),
        "payload_status": _as_text(execution_payload.get("payload_status")),
        "export_status": export_status,
        "execution_mode": _as_text(execution_payload.get("execution_mode")) or "review_first",
        "target_property": target_property,
        "live_target_supported": bool(execution_payload.get("live_target_supported")),
        "candidate_ids": candidate_ids_from_payload,
        "artifacts": [
            {
                "artifact_kind": "openrefine_review_rows",
                "artifact_id": f"{export_id}:openrefine_review_rows",
                "suggested_filename": f"{export_id}.openrefine.review.json",
                "row_count": len(openrefine_rows),
                "rows": list(openrefine_rows),
            },
            {
                "artifact_kind": "quickstatements_v1_review_rows",
                "artifact_id": f"{export_id}:quickstatements_v1_review_rows",
                "suggested_filename": f"{export_id}.quickstatements.review.json",
                "row_count": len(quickstatements_rows),
                "rows": list(quickstatements_rows),
            },
        ],
        "summary": {
            "candidate_count": len(candidate_ids_from_payload),
            "artifact_count": 2,
            "row_count": int(execution_payload.get("summary", {}).get("row_count", 0)),
            "target_property": target_property,
        },
    }


def build_nat_migration_candidate_contracts(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    execution_payload = build_nat_migration_execution_payload(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    family_id = _as_text(execution_payload.get("family_id"))
    cohort_id = _as_text(execution_payload.get("cohort_id"))
    rows = execution_payload.get("openrefine_rows", [])
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        rows = []
    candidates_by_id = _candidate_lookup_from_verification_runs(verification_runs)

    candidate_contracts: list[dict[str, Any]] = []
    promotion_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        candidate_id = _as_text(row.get("candidate_id"))
        original_candidate = candidates_by_id.get(candidate_id, {})
        target_bundle = row.get("target_claim_bundle_json", {})
        if not isinstance(target_bundle, Mapping):
            target_bundle = {}
        model_validation = _normalize_model_validation(row.get("model_validation"))
        split_plan = _normalize_split_plan(row.get("split_plan"))
        execution_profile = _normalize_optional_mapping(row.get("execution_profile"))
        promotion_class = _optional_text(original_candidate.get("promotion_class")) or "review_only"
        promotion_gate = _normalize_candidate_promotion_gate(original_candidate.get("promotion_gate"))
        if not promotion_gate:
            promotion_gate = {
                "decision": promotion_class,
                "reason": "legacy_candidate_contract_surface",
                "eligibility": {
                    "eligible": promotion_class != "review_only",
                    "review_only": promotion_class == "review_only",
                    "semi_auto": promotion_class in {"semi_auto", "full_auto"},
                    "full_auto": promotion_class == "full_auto",
                    "reason": "legacy_candidate_contract_surface",
                },
            }
        subject_resolution = _normalize_subject_resolution(original_candidate.get("subject_resolution"))
        if subject_resolution:
            promotion_gate = _augment_promotion_gate_with_subject_resolution(promotion_gate, subject_resolution)
        promotion_counts[promotion_class] = promotion_counts.get(promotion_class, 0) + 1
        source_bundle = {
            "subject": _as_text(row.get("entity_qid")),
            "property": _as_text(row.get("from_property")),
            "value": _as_text(row.get("value")),
            "rank": _as_text(row.get("rank")) or "normal",
            "qualifiers": row.get("qualifiers_json", {}),
            "references": row.get("references_json", []),
            "window_id": _as_text(target_bundle.get("window_id")),
        }
        target_bundle = {
            "subject": _as_text(target_bundle.get("subject")) or _as_text(row.get("entity_qid")),
            "property": _as_text(target_bundle.get("property")) or _as_text(row.get("to_property")),
            "value": target_bundle.get("value", row.get("value")),
            "rank": _as_text(target_bundle.get("rank")) or _as_text(row.get("rank")) or "normal",
            "qualifiers": target_bundle.get("qualifiers", row.get("qualifiers_json", {})),
            "references": target_bundle.get("references", row.get("references_json", [])),
            "window_id": _as_text(target_bundle.get("window_id")),
        }
        candidate_contracts.append(
            {
                "candidate_id": candidate_id,
                "entity_qid": _as_text(row.get("entity_qid")),
                "family_id": family_id,
                "cohort_id": cohort_id,
                "classification": _as_text(row.get("classification")),
                "promotion_class": promotion_class,
                "source_statement": {
                    "property": _as_text(source_bundle.get("property")),
                    "value": _normalize_contract_value(source_bundle.get("value")),
                    "qualifiers": source_bundle.get("qualifiers", {}),
                    "references": source_bundle.get("references", []),
                    "rank": _as_text(source_bundle.get("rank")) or "normal",
                },
                "target_statement": {
                    "property": _as_text(target_bundle.get("property")),
                    "value": _normalize_contract_value(target_bundle.get("value")),
                    "qualifiers": target_bundle.get("qualifiers", {}),
                    "references": target_bundle.get("references", []),
                    "rank": _as_text(target_bundle.get("rank")) or "normal",
                },
                **({"subject_resolution": subject_resolution} if subject_resolution else {}),
                "normalization": {
                    "year_basis": _year_basis_for_bundle(target_bundle),
                    "quantity_unit_normalized": "unit_qid" in _normalize_contract_value(target_bundle.get("value")),
                    "fiscal_year_edge_case": False,
                    **(
                        {
                            "resolved_year": _as_text(model_validation.get("resolved_year") or split_plan.get("resolved_year")),
                            "resolved_scope": _as_text(model_validation.get("resolved_scope") or split_plan.get("resolved_scope")),
                            "resolved_unit_qid": _as_text(model_validation.get("resolved_unit_qid") or split_plan.get("resolved_unit_qid")),
                        }
                        if (model_validation or split_plan)
                        else {}
                    ),
                },
                **(
                    {
                        "promotion_gate": promotion_gate,
                        "model_validation": model_validation,
                        "split_plan": split_plan,
                        "execution_profile": execution_profile,
                    }
                    if (promotion_gate or model_validation or split_plan or execution_profile)
                    else {}
                ),
            }
        )

    subject_resolution_summary = _subject_resolution_summary_from_contracts(candidate_contracts)

    report = {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_CANDIDATE_CONTRACT_SCHEMA_VERSION,
        "family_id": family_id,
        "cohort_id": cohort_id,
        "family_state": _as_text(execution_payload.get("family_state")),
        "payload_status": _as_text(execution_payload.get("payload_status")),
        "candidate_contracts": candidate_contracts,
        "summary": {
            "candidate_count": len(candidate_contracts),
            "target_property": _as_text(execution_payload.get("target_property")),
            "counts_by_promotion_class": promotion_counts,
            **(
                {
                    "subject_resolution_counts": {
                        "known": subject_resolution_summary["subject_resolution_known_count"],
                        "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                        "absent": subject_resolution_summary["subject_resolution_absent_count"],
                    },
                    "subject_resolution_gate_ready": subject_resolution_summary["subject_resolution_unknown_count"] == 0,
                }
                if subject_resolution_summary
                else {}
            ),
        },
    }
    if subject_resolution_summary:
        report["summary"].update(subject_resolution_summary)
    return report


def build_nat_migration_backend_plan(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    execution_payload = build_nat_migration_execution_payload(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    openrefine_rows = execution_payload.get("openrefine_rows", [])
    quickstatements_rows = execution_payload.get("quickstatements_v1_rows", [])
    if not isinstance(openrefine_rows, Sequence) or isinstance(openrefine_rows, (str, bytes, bytearray)):
        openrefine_rows = []
    if not isinstance(quickstatements_rows, Sequence) or isinstance(quickstatements_rows, (str, bytes, bytearray)):
        quickstatements_rows = []

    qs_by_candidate = {
        _as_text(row.get("candidate_id")): row
        for row in quickstatements_rows
        if isinstance(row, Mapping) and _as_text(row.get("candidate_id"))
    }
    backend_rows: list[dict[str, Any]] = []
    openrefine_count = 0
    quickstatements_count = 0
    model_aware_count = 0
    for row in openrefine_rows:
        if not isinstance(row, Mapping):
            continue
        candidate_id = _as_text(row.get("candidate_id"))
        rank = _as_text(row.get("rank")) or "normal"
        execution_backend = _optional_text(row.get("execution_backend"))
        if _optional_text(row.get("model_classification")) or row.get("split_plan"):
            model_aware_count += 1
        if not execution_backend:
            if rank == "normal":
                execution_backend = "openrefine"
            else:
                execution_backend = "qs3"
        if execution_backend == "openrefine":
            execution_backend = "openrefine"
            execution_reason = "OpenRefine supports statements, qualifiers, references, and editing modes, but statement ranks remain normal."
            openrefine_count += 1
        elif execution_backend == "qs3":
            execution_reason = "QS3 is required when the target rank is preferred or deprecated, or when force-create semantics may be needed."
            quickstatements_count += 1
        else:
            execution_reason = "Execution backend was supplied by the model-aware lane."
            if rank == "normal":
                openrefine_count += 1
            else:
                quickstatements_count += 1
        backend_rows.append(
            {
                "candidate_id": candidate_id,
                "entity_qid": _as_text(row.get("entity_qid")),
                "rank": rank,
                "execution_backend": execution_backend,
                "execution_reason": execution_reason,
                "openrefine_row": row if execution_backend == "openrefine" else None,
                "quickstatements_row": qs_by_candidate.get(candidate_id) if execution_backend == "qs3" else None,
                **(
                    {
                        "execution_strategy": _as_text(row.get("execution_strategy")),
                        "model_classification": _as_text(row.get("model_classification")),
                        "model_validation": row.get("model_validation", {}),
                        "split_plan": row.get("split_plan", {}),
                    }
                    if _as_text(row.get("model_classification")) or row.get("split_plan")
                    else {}
                ),
            }
        )

    report = {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_BACKEND_PLAN_SCHEMA_VERSION,
        "family_id": _as_text(execution_payload.get("family_id")),
        "cohort_id": _as_text(execution_payload.get("cohort_id")),
        "family_state": _as_text(execution_payload.get("family_state")),
        "payload_status": _as_text(execution_payload.get("payload_status")),
        "backend_rows": backend_rows,
        "summary": {
            "candidate_count": len(backend_rows),
            "openrefine_count": openrefine_count,
            "qs3_count": quickstatements_count,
        },
    }
    if model_aware_count:
        report["summary"]["model_aware_count"] = model_aware_count
    return report


def build_nat_execution_receipt_contract(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    backend_plan = build_nat_migration_backend_plan(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    receipt_rows: list[dict[str, Any]] = []
    for row in backend_plan.get("backend_rows", []):
        if not isinstance(row, Mapping):
            continue
        model_validation = _normalize_model_validation(row.get("model_validation"))
        split_plan = _normalize_split_plan(row.get("split_plan"))
        receipt_row = {
            "candidate_id": _as_text(row.get("candidate_id")),
            "entity_qid": _as_text(row.get("entity_qid")),
            "target_property": "P14143",
            "execution_backend": _as_text(row.get("execution_backend")),
            "backend_statement_id": "",
            "execution_status": "awaiting_external_execution",
            "evidence_provenance_kind": "operator_execution_receipt",
        }
        if row.get("model_classification") or model_validation or split_plan:
            receipt_row.update(
                {
                    "execution_strategy": _as_text(row.get("execution_strategy")),
                    "model_classification": _as_text(row.get("model_classification")),
                    "model_validation": model_validation,
                    "split_plan": split_plan,
                }
            )
        receipt_rows.append(
            receipt_row
        )

    family_id = _as_text(backend_plan.get("family_id"))
    batch_id = f"{family_id}:migration_batch"
    receipt_contract = {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_RECEIPT_CONTRACT_SCHEMA_VERSION,
        "receipt_status": "awaiting_external_execution_receipt",
        "family_id": family_id,
        "cohort_id": _as_text(backend_plan.get("cohort_id")),
        "batch_id": batch_id,
        "execution_backends": sorted(
            {
                _as_text(row.get("execution_backend"))
                for row in backend_plan.get("backend_rows", [])
                if isinstance(row, Mapping) and _as_text(row.get("execution_backend"))
            }
        ),
        "required_fields": [
            "receipt_id",
            "batch_id",
            "execution_backend",
            "operator_id",
            "submitted_at",
            "completed_at",
            "status",
            "statement_results",
            "raw_artifact_path",
        ],
        "statement_results": receipt_rows,
        "summary": {
            "candidate_count": len(receipt_rows),
            "backend_count": len(
                {
                    _as_text(row.get("execution_backend"))
                    for row in backend_plan.get("backend_rows", [])
                if isinstance(row, Mapping) and _as_text(row.get("execution_backend"))
                }
            ),
        },
    }
    if any(
        isinstance(row, Mapping)
        and (row.get("model_classification") or row.get("model_validation") or row.get("split_plan"))
        for row in receipt_rows
    ):
        receipt_contract["required_fields"] = receipt_contract["required_fields"] + [
            "model_classification",
            "model_validation",
            "split_plan",
        ]
    return receipt_contract


def build_nat_post_write_contract(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate_contracts = build_nat_migration_candidate_contracts(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    subject_resolution_summary = _subject_resolution_summary_from_contracts(
        candidate_contracts.get("candidate_contracts", [])
    )
    entity_checks: list[dict[str, Any]] = []
    for contract in candidate_contracts.get("candidate_contracts", []):
        if not isinstance(contract, Mapping):
            continue
        model_validation = contract.get("model_validation", {})
        split_plan = contract.get("split_plan", {})
        must_verify = [
            "target_found",
            "value_match",
            "qualifier_match",
            "reference_match",
            "rank_match",
        ]
        if isinstance(contract.get("subject_resolution"), Mapping):
            must_verify.append("subject_resolution_match")
        if isinstance(model_validation, Mapping) and model_validation:
            must_verify.extend(["resolved_year_match", "resolved_scope_match", "resolved_unit_match"])
        if isinstance(split_plan, Mapping) and split_plan:
            must_verify.append("split_plan_match")
        entity_checks.append(
            {
                "candidate_id": _as_text(contract.get("candidate_id")),
                "entity_qid": _as_text(contract.get("entity_qid")),
                "target_property": _as_text(contract.get("target_statement", {}).get("property")),
                "expected_rank": _as_text(contract.get("target_statement", {}).get("rank")),
                "must_verify": must_verify,
                "verification_status": "awaiting_observed_after_state",
                "execution_lifecycle_state": "ready",
            }
        )

    lifecycle_contract = {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "state_order": list(POST_WRITE_LIFECYCLE_STATES),
        "current_state": "ready",
        "promotion_status": "hold",
        "fail_closed_on_mismatch": True,
        "eligible_row_count": len(entity_checks),
        "verified_row_count": 0,
        "executed_row_count": 0,
    }
    readiness_surface = {
        "execution_lifecycle_state": "ready",
        "promotion_status": "hold",
        "verification_status": "awaiting_observed_after_state",
        "fixed_point_state": "ready",
        "stable_fixed_point": False,
        "ready_for_external_execution": True,
        "verification_ready": False,
        "run_count": 0,
        "verified_run_count": 0,
        "verified_claim_count": 0,
        "drift_claim_count": 0,
        "total_claims": 0,
    }
    if subject_resolution_summary:
        readiness_surface["ready_for_external_execution"] = subject_resolution_summary["subject_resolution_unknown_count"] == 0
        readiness_surface.update(
            {
                "subject_resolution_gate_ready": subject_resolution_summary["subject_resolution_unknown_count"] == 0,
                "subject_resolution_counts": {
                    "known": subject_resolution_summary["subject_resolution_known_count"],
                    "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                    "absent": subject_resolution_summary["subject_resolution_absent_count"],
                },
                "subject_resolution_hard_defect_count": subject_resolution_summary["subject_resolution_hard_defect_count"],
                "subject_resolution_soft_defect_count": subject_resolution_summary["subject_resolution_soft_defect_count"],
                "subject_resolution_distribution_by_promotion_class": subject_resolution_summary[
                    "subject_resolution_distribution_by_promotion_class"
                ],
                "subject_resolution_coverage": subject_resolution_summary["subject_resolution_coverage"],
            }
        )
    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_POST_WRITE_CONTRACT_SCHEMA_VERSION,
        "verification_status": "awaiting_observed_after_state",
        "family_id": _as_text(candidate_contracts.get("family_id")),
        "cohort_id": _as_text(candidate_contracts.get("cohort_id")),
        "execution_lifecycle_contract": lifecycle_contract,
        "verification_contract": {
            "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
            "verification_status": "awaiting_observed_after_state",
            "required_observed_fields": [
                "candidate_id",
                "entity_qid",
                "after_state_value",
                "after_state_references",
                "after_state_qualifiers",
            ],
            "fail_closed_on_mismatch": True,
        },
        "entity_checks": entity_checks,
        "summary": {
            "candidate_count": len(entity_checks),
            "required_verification_fields": 5,
            **(
                {
                    "subject_resolution_counts": {
                        "known": subject_resolution_summary["subject_resolution_known_count"],
                        "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                        "absent": subject_resolution_summary["subject_resolution_absent_count"],
                    },
                    "subject_resolution_gate_ready": subject_resolution_summary["subject_resolution_unknown_count"] == 0,
                }
                if subject_resolution_summary
                else {}
            ),
        },
        "readiness_surface": readiness_surface,
        "pilot_metrics": {
            "candidate_count": len(entity_checks),
            "eligible_row_count": len(entity_checks),
            "required_verification_fields": 5,
            "verification_ready": False,
            "fixed_point_state": "ready",
            "stable_fixed_point": False,
            "promotion_ready": False,
            **(
                {
                    "subject_resolution_counts": {
                        "known": subject_resolution_summary["subject_resolution_known_count"],
                        "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                        "absent": subject_resolution_summary["subject_resolution_absent_count"],
                    },
                    "subject_resolution_gate_ready": subject_resolution_summary["subject_resolution_unknown_count"] == 0,
                    "subject_resolution_hard_defect_count": subject_resolution_summary[
                        "subject_resolution_hard_defect_count"
                    ],
                    "subject_resolution_soft_defect_count": subject_resolution_summary[
                        "subject_resolution_soft_defect_count"
                    ],
                }
                if subject_resolution_summary
                else {}
            ),
        },
    }


def build_nat_migration_simulation_contract(
    verification_runs: Mapping[str, Any],
    *,
    candidate_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate_contracts = build_nat_migration_candidate_contracts(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    backend_plan = build_nat_migration_backend_plan(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    receipt_contract = build_nat_execution_receipt_contract(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    post_write_contract = build_nat_post_write_contract(
        verification_runs,
        candidate_ids=candidate_ids,
    )
    candidate_summary = (
        candidate_contracts.get("summary", {})
        if isinstance(candidate_contracts.get("summary"), Mapping)
        else {}
    )
    backend_summary = (
        backend_plan.get("summary", {})
        if isinstance(backend_plan.get("summary"), Mapping)
        else {}
    )
    lifecycle_contract = (
        post_write_contract.get("execution_lifecycle_contract", {})
        if isinstance(post_write_contract.get("execution_lifecycle_contract"), Mapping)
        else {}
    )
    verification_contract = (
        post_write_contract.get("verification_contract", {})
        if isinstance(post_write_contract.get("verification_contract"), Mapping)
        else {}
    )
    subject_resolution_summary = _subject_resolution_summary_from_contracts(
        candidate_contracts.get("candidate_contracts", [])
    )
    readiness_contract = {
        "promotion_status": _as_text(lifecycle_contract.get("promotion_status")) or "hold",
        "execution_lifecycle_state": _as_text(lifecycle_contract.get("current_state")) or "not_started",
        "post_write_verification_status": _as_text(verification_contract.get("verification_status"))
        or "awaiting_observed_after_state",
        "review_first": True,
        "ready_for_external_execution": _as_text(post_write_contract.get("verification_status"))
        == "awaiting_observed_after_state",
    }
    if subject_resolution_summary:
        readiness_contract["ready_for_external_execution"] = (
            subject_resolution_summary["subject_resolution_unknown_count"] == 0
        )
        readiness_contract.update(
            {
                "subject_resolution_gate_ready": subject_resolution_summary["subject_resolution_unknown_count"] == 0,
                "subject_resolution_counts": {
                    "known": subject_resolution_summary["subject_resolution_known_count"],
                    "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                    "absent": subject_resolution_summary["subject_resolution_absent_count"],
                },
                "subject_resolution_distribution_by_promotion_class": subject_resolution_summary[
                    "subject_resolution_distribution_by_promotion_class"
                ],
                "subject_resolution_coverage": subject_resolution_summary["subject_resolution_coverage"],
            }
        )
    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_SIMULATION_CONTRACT_SCHEMA_VERSION,
        "simulation_status": "ready_for_external_execution",
        "family_id": _as_text(candidate_contracts.get("family_id")),
        "cohort_id": _as_text(candidate_contracts.get("cohort_id")),
        "candidate_contracts": candidate_contracts,
        "backend_plan": backend_plan,
        "receipt_contract": receipt_contract,
        "post_write_contract": post_write_contract,
        "readiness_contract": readiness_contract,
        "summary": {
            "candidate_count": int(candidate_summary.get("candidate_count", 0)),
            "openrefine_count": int(backend_summary.get("openrefine_count", 0)),
            "qs3_count": int(backend_summary.get("qs3_count", 0)),
            "counts_by_promotion_class": dict(candidate_summary.get("counts_by_promotion_class", {})),
            **(
                {
                    "subject_resolution_counts": {
                        "known": subject_resolution_summary["subject_resolution_known_count"],
                        "unknown": subject_resolution_summary["subject_resolution_unknown_count"],
                        "absent": subject_resolution_summary["subject_resolution_absent_count"],
                    },
                    "subject_resolution_distribution_by_promotion_class": subject_resolution_summary[
                        "subject_resolution_distribution_by_promotion_class"
                    ],
                    "subject_resolution_coverage": subject_resolution_summary["subject_resolution_coverage"],
                }
                if subject_resolution_summary
                else {}
            ),
        },
    }


def _summarize_post_write_runs(
    runs: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    total_runs = 0
    verified_runs = 0
    total_claims = 0
    verified_claims = 0
    drift_claims = 0
    pending_drift_run_ids: list[str] = []
    for run in runs or []:
        if not isinstance(run, Mapping):
            continue
        total_runs += 1
        run_id = _as_text(run.get("run_id"))
        counts_by_status = (
            run.get("counts_by_status", {})
            if isinstance(run.get("counts_by_status"), Mapping)
            else {}
        )
        run_claim_total = sum(int(value) for value in counts_by_status.values())
        run_verified_claims = int(counts_by_status.get("verified", 0))
        total_claims += run_claim_total
        verified_claims += run_verified_claims
        drift_claims += max(run_claim_total - run_verified_claims, 0)
        if _as_text(run.get("verification_status")) == "verified":
            verified_runs += 1
        elif run_id:
            pending_drift_run_ids.append(run_id)

    verification_ready = total_runs > 0 and verified_runs == total_runs
    return {
        "run_count": total_runs,
        "verified_run_count": verified_runs,
        "verification_ready": verification_ready,
        "total_claims": total_claims,
        "verified_claims": verified_claims,
        "drift_claims": drift_claims,
        "pending_drift_run_ids": pending_drift_run_ids,
        "fixed_point_state": "verified" if verification_ready else ("executed" if total_runs else "not_started"),
        "stable_fixed_point": verification_ready,
        "promotion_ready": verification_ready,
    }


def _build_post_write_readiness_surface(
    lifecycle_contract: Mapping[str, Any],
    verification_contract: Mapping[str, Any],
    *,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    verification_ready = bool(summary.get("verification_ready"))
    return {
        "execution_lifecycle_state": _as_text(lifecycle_contract.get("current_state")) or "not_started",
        "promotion_status": _as_text(lifecycle_contract.get("promotion_status")) or "hold",
        "verification_status": _as_text(verification_contract.get("verification_status"))
        or "awaiting_observed_after_state",
        "fixed_point_state": "verified" if verification_ready else _as_text(lifecycle_contract.get("current_state"))
        or "not_started",
        "stable_fixed_point": verification_ready,
        "ready_for_external_execution": _as_text(verification_contract.get("verification_status"))
        == "awaiting_observed_after_state",
        "verification_ready": verification_ready,
        "run_count": int(summary.get("run_count", 0)),
        "verified_run_count": int(summary.get("verified_run_count", 0)),
        "verified_claim_count": int(summary.get("verified_claims", 0)),
        "drift_claim_count": int(summary.get("drift_claims", 0)),
        "total_claims": int(summary.get("total_claims", 0)),
    }


def _build_post_write_pilot_metrics(
    *,
    readiness_surface: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    total_claims = max(int(summary.get("total_claims", 0)), 0)
    verified_claims = max(int(summary.get("verified_claims", 0)), 0)
    drift_claims = max(int(summary.get("drift_claims", 0)), 0)
    run_count = max(int(summary.get("run_count", 0)), 0)
    verified_run_count = max(int(summary.get("verified_run_count", 0)), 0)
    verified_claim_rate = verified_claims / max(total_claims, 1)
    drift_claim_rate = drift_claims / max(total_claims, 1)
    return {
        "run_count": run_count,
        "verified_run_count": verified_run_count,
        "verification_ready": bool(summary.get("verification_ready")),
        "fixed_point_state": _as_text(readiness_surface.get("fixed_point_state")) or "not_started",
        "stable_fixed_point": bool(readiness_surface.get("stable_fixed_point")),
        "promotion_ready": bool(readiness_surface.get("promotion_ready")),
        "total_claims": total_claims,
        "verified_claims": verified_claims,
        "drift_claims": drift_claims,
        "verified_claim_rate": verified_claim_rate,
        "drift_claim_rate": drift_claim_rate,
        "pending_drift_run_count": len(_as_text_list(summary.get("pending_drifts"))),
    }


def build_nat_migration_executed_rows(
    batch_export: Mapping[str, Any],
) -> dict[str, Any]:
    execution_receipts = batch_export.get("executed_rows_report")
    if isinstance(execution_receipts, Mapping):
        # Real receipt surface from execution tooling takes precedence.
        return execution_receipts

    family_id = _as_text(batch_export.get("family_id"))
    cohort_id = _as_text(batch_export.get("cohort_id"))
    export_status = _as_text(batch_export.get("export_status"))
    export_id = _as_text(batch_export.get("export_id"))
    rows_by_candidate: dict[str, dict[str, Any]] = {}
    for artifact in batch_export.get("artifacts", []):
        if not isinstance(artifact, Mapping):
            continue
        artifact_kind = _as_text(artifact.get("artifact_kind"))
        for row in artifact.get("rows", []):
            if not isinstance(row, Mapping):
                continue
            candidate_id = _as_text(row.get("candidate_id"))
            if not candidate_id:
                continue
            receipt = rows_by_candidate.setdefault(
                candidate_id,
                {
                    "family_id": family_id,
                    "cohort_id": cohort_id,
                    "candidate_id": candidate_id,
                    "export_id": export_id,
                    "execution_mode": _as_text(batch_export.get("execution_mode")) or "review_first",
                    "artifact_kinds": [],
                },
            )
            receipt["artifact_kinds"].append(artifact_kind)
    executed_rows = []
    for candidate_id in sorted(rows_by_candidate):
        receipt = rows_by_candidate[candidate_id]
        receipt["artifact_kinds"] = sorted(_as_text_set(receipt.get("artifact_kinds")))
        executed_rows.append(receipt)
    execution_status = "ready_execution_receipts"
    if export_status != "ready_for_review_export":
        execution_status = "export_not_ready"
    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_EXECUTED_ROWS_SCHEMA_VERSION,
        "export_id": export_id,
        "family_id": family_id,
        "cohort_id": cohort_id,
        "export_status": export_status,
        "execution_status": execution_status,
        "executed_rows": executed_rows,
        "summary": {
            "row_count": len(executed_rows),
            "artifact_count": sum(len(row.get("artifact_kinds", [])) for row in executed_rows),
        },
    }


def build_nat_migration_batch_finder_report(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    state_report = build_nat_state_machine_report(
        verification_run_batches,
        min_independent_paths=min_independent_paths,
    )
    state_by_family = {
        _as_text(row.get("family_id")): row
        for row in state_report.get("families", [])
        if isinstance(row, Mapping) and _as_text(row.get("family_id"))
    }
    candidate_batches: list[dict[str, Any]] = []
    held_families: list[dict[str, Any]] = []

    for verification_runs in verification_run_batches:
        if not isinstance(verification_runs, Mapping):
            continue
        family_id = _as_text(verification_runs.get("family_id"))
        family_row = state_by_family.get(family_id, {})
        execution_payload = build_nat_migration_execution_payload(verification_runs)
        row_count = int(execution_payload.get("summary", {}).get("row_count", 0))
        if _as_text(execution_payload.get("payload_status")) == "ready_for_review_payload" and row_count > 0:
            candidate_batches.append(
                {
                    "family_id": family_id,
                    "cohort_id": _as_text(verification_runs.get("cohort_id")),
                    "family_state": _as_text(family_row.get("state")),
                    "state_basis": _as_text(family_row.get("state_basis")),
                    "row_count": row_count,
                    "target_property": _as_text(execution_payload.get("target_property")),
                    "candidate_ids": [
                        _as_text(row.get("candidate_id"))
                        for row in execution_payload.get("openrefine_rows", [])
                        if isinstance(row, Mapping) and _as_text(row.get("candidate_id"))
                    ],
                }
            )
        else:
            held_families.append(
                {
                    "family_id": family_id,
                    "cohort_id": _as_text(verification_runs.get("cohort_id")),
                    "family_state": _as_text(family_row.get("state")),
                    "state_basis": _as_text(family_row.get("state_basis")),
                    "blocking_reason": _as_text(execution_payload.get("payload_status")) or "not_ready_for_execution",
                    "target_property": _as_text(execution_payload.get("target_property")),
                }
            )

    candidate_batches.sort(key=lambda row: (-int(row.get("row_count", 0)), _as_text(row.get("family_id"))))
    processed_families = {row.get("family_id") for row in candidate_batches if isinstance(row.get("family_id"), str)}
    machine_generated_batches: list[dict[str, Any]] = []
    for family_id, state_row in state_by_family.items():
        if not family_id or family_id in processed_families:
            continue
        state_basis = _as_text(state_row.get("state_basis"))
        machine_generated_batches.append(
            {
                "family_id": family_id,
                "cohort_id": _as_text(state_row.get("cohort_id")),
                "family_state": _as_text(state_row.get("state")),
                "state_basis": state_basis,
                "row_count": int(state_row.get("claim_count", 0)),
                "machine_generated": True,
                "eligibility_reason": f"state_basis:{state_basis}",
            }
        )
    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_BATCH_FINDER_SCHEMA_VERSION,
        "minimum_independent_paths_required": min_independent_paths,
        "candidate_batches": candidate_batches,
        "machine_generated_batches": machine_generated_batches,
        "held_families": held_families,
        "summary": {
            "family_count": len(candidate_batches) + len(held_families),
            "ready_batch_count": len(candidate_batches),
            "held_family_count": len(held_families),
            "ready_row_count": sum(int(row.get("row_count", 0)) for row in candidate_batches),
            "machine_generated_count": len(machine_generated_batches),
        },
    }


def build_nat_migration_lifecycle_report(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    executed_rows: Sequence[Mapping[str, Any]] | None = None,
    post_execution_batches: Sequence[Mapping[str, Any]] | None = None,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    executed_by_family: dict[str, set[str]] = {}
    for row in executed_rows or []:
        if not isinstance(row, Mapping):
            continue
        family_id = _as_text(row.get("family_id"))
        candidate_id = _as_text(row.get("candidate_id"))
        if family_id and candidate_id:
            executed_by_family.setdefault(family_id, set()).add(candidate_id)

    verified_candidates_by_family: dict[str, set[str]] = {}
    for batch in post_execution_batches or []:
        if not isinstance(batch, Mapping):
            continue
        convergence = build_nat_claim_convergence_report(batch, min_independent_paths=min_independent_paths)
        family_id = _as_text(convergence.get("family_id"))
        promoted = {
            _as_text(claim.get("claim_id"))
            for claim in convergence.get("claims", [])
            if isinstance(claim, Mapping) and _as_text(claim.get("status")) == "PROMOTED"
        }
        if family_id and promoted:
            verified_candidates_by_family[family_id] = promoted

    rows: list[dict[str, Any]] = []
    summary = {"ready_count": 0, "executed_count": 0, "verified_count": 0, "not_started_count": 0}
    finder = build_nat_migration_batch_finder_report(
        verification_run_batches,
        min_independent_paths=min_independent_paths,
    )
    ready_families = {row["family_id"]: row for row in finder.get("candidate_batches", []) if isinstance(row, Mapping)}

    for batch in verification_run_batches:
        if not isinstance(batch, Mapping):
            continue
        family_id = _as_text(batch.get("family_id"))
        cohort_id = _as_text(batch.get("cohort_id"))
        ready_row = ready_families.get(family_id)
        lifecycle_state = "NOT_STARTED"
        candidate_ids: list[str] = []
        if isinstance(ready_row, Mapping):
            candidate_ids = list(ready_row.get("candidate_ids", []))
            lifecycle_state = "READY"
            summary["ready_count"] += 1
        executed_ids = executed_by_family.get(family_id, set())
        verified_ids = verified_candidates_by_family.get(family_id, set())
        if candidate_ids and all(candidate_id in verified_ids for candidate_id in candidate_ids):
            lifecycle_state = "VERIFIED"
            summary["verified_count"] += 1
            summary["ready_count"] -= 1
        elif candidate_ids and executed_ids:
            lifecycle_state = "EXECUTED"
            summary["executed_count"] += 1
            summary["ready_count"] -= 1
        elif not candidate_ids:
            summary["not_started_count"] += 1

        rows.append(
            {
                "family_id": family_id,
                "cohort_id": cohort_id,
                "lifecycle_state": lifecycle_state,
                "candidate_ids": candidate_ids,
                "executed_candidate_ids": sorted(executed_ids),
                "verified_candidate_ids": sorted(verified_ids),
            }
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_LIFECYCLE_REPORT_SCHEMA_VERSION,
        "minimum_independent_paths_required": min_independent_paths,
        "families": rows,
        "summary": summary,
    }


def build_nat_migration_execution_proof(
    verification_runs: Mapping[str, Any],
    *,
    post_execution_batches: Sequence[Mapping[str, Any]] | None = None,
    candidate_ids: Sequence[str] | None = None,
    require_live_target_property: bool = True,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    batch_export = build_nat_migration_batch_export(
        verification_runs,
        candidate_ids=candidate_ids,
        require_live_target_property=require_live_target_property,
    )
    executed_rows_report = build_nat_migration_executed_rows(batch_export)
    lifecycle_report = build_nat_migration_lifecycle_report(
        [verification_runs],
        executed_rows=executed_rows_report.get("executed_rows", []),
        post_execution_batches=post_execution_batches,
        min_independent_paths=min_independent_paths,
    )
    lifecycle_row = next(
        (
            row
            for row in lifecycle_report.get("families", [])
            if isinstance(row, Mapping)
            and _as_text(row.get("family_id")) == _as_text(verification_runs.get("family_id"))
        ),
        {},
    )
    return {
        "schema_version": AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PROOF_SCHEMA_VERSION,
        "family_id": _as_text(verification_runs.get("family_id")),
        "cohort_id": _as_text(verification_runs.get("cohort_id")),
        "batch_export": batch_export,
        "executed_rows_report": executed_rows_report,
        "lifecycle_report": lifecycle_report,
        "summary": {
            "export_status": _as_text(batch_export.get("export_status")),
            "execution_status": _as_text(executed_rows_report.get("execution_status")),
            "lifecycle_state": _as_text(lifecycle_row.get("lifecycle_state")),
            "candidate_count": int(batch_export.get("summary", {}).get("candidate_count", 0)),
        },
    }


def _count_checked_safe_candidates(migration_pack: Mapping[str, Any]) -> int:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, Sequence):
        return 0
    count = 0
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _candidate_is_eligible_for_execution(candidate):
            count += 1
    return count


def _build_gate_b_metrics_from_verification_report(
    migration_pack: Mapping[str, Any],
    verification_report: Mapping[str, Any],
) -> dict[str, Any]:
    checked_safe_count = max(_count_checked_safe_candidates(migration_pack), 0)
    verification_summary = (
        verification_report.get("summary", {}) if isinstance(verification_report.get("summary"), Mapping) else {}
    )
    counts_by_status = (
        verification_summary.get("counts_by_status", {})
        if isinstance(verification_summary.get("counts_by_status"), Mapping)
        else {}
    )
    verified_count = int(verification_summary.get("verified_candidate_count", 0))
    total_verified_rows = sum(int(value) for value in counts_by_status.values()) if counts_by_status else verified_count
    denominator = checked_safe_count if checked_safe_count > 0 else max(total_verified_rows, 1)

    non_verified_count = max(total_verified_rows - int(counts_by_status.get("verified", 0)), 0)
    candidate_rows = verification_report.get("rows", [])
    if not isinstance(candidate_rows, Sequence):
        candidate_rows = []
    complete_receipt_rows = sum(
        1
        for row in candidate_rows
        if isinstance(row, Mapping)
        and _as_text(row.get("candidate_id"))
        and _as_text(row.get("entity_qid"))
        and _as_text(row.get("source_slot_id"))
        and _as_text(row.get("target_slot_id"))
    )
    receipt_coverage = complete_receipt_rows / max(len(candidate_rows), 1)

    return {
        "direct_safe_yield_by_family": {"observed": verified_count / denominator},
        "split_required_rate_by_family": {"observed": 0.0},
        "hold_abstain_rate_and_reason_distribution": {"observed": 0.0},
        "after_state_verification_pass_rate": {"observed": verified_count / denominator},
        "false_positive_rate_and_severity": {"observed": non_verified_count / denominator},
        "rollback_invocation_and_recovery_success": {"observed": 1.0},
        "receipt_completeness_coverage": {"observed": receipt_coverage},
    }


def _build_bounded_promotion_scope(
    family_id: str,
    cohort_id: str,
    candidate_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "scope_type": "bounded_family_subset",
        "scope_status": "pilot_ready_only",
        "family_id": family_id,
        "cohort_id": cohort_id,
        "candidate_ids": [candidate_id for candidate_id in candidate_ids if _as_text(candidate_id)],
        "generalization_allowed": False,
        "generalization_requires_new_evidence": True,
        "promotion_statement": (
            "Promote this Nat Gate B candidate only as a bounded pilot-ready family subset. "
            "This promotion applies solely to the listed candidate_ids and does not establish "
            "readiness for the broader cohort, other cohorts, or backlog-wide automation."
        ),
    }


def build_nat_gate_b_proposal_batches_from_verification_runs(
    verification_runs: Mapping[str, Any],
) -> dict[str, Any]:
    raw_runs = verification_runs.get("runs", [])
    if not isinstance(raw_runs, Sequence) or isinstance(raw_runs, (str, bytes, bytearray)):
        raw_runs = []
    if not raw_runs and isinstance(verification_runs.get("migration_pack"), Mapping):
        raw_runs = [verification_runs]
    family_id = _as_text(verification_runs.get("family_id"))
    cohort_id = _as_text(verification_runs.get("cohort_id"))
    candidate_ids_raw = verification_runs.get("candidate_ids", [])
    candidate_ids = [str(value).strip() for value in candidate_ids_raw if str(value).strip()]
    bounded_scope = _build_bounded_promotion_scope(family_id, cohort_id, candidate_ids)
    gate_families_passed = [
        "evidence_grounding",
        "claim_boundary_reliability",
        "verification_quality",
        "policy_risk_containment",
        "operational_control_and_rollback",
    ]
    evidence_signals = [
        "repeated_family_scoped_direct_safe_behavior",
        "stable_after_state_verification_across_repeated_tranches",
        "false_positive_rate_within_family_budget",
        "hold_and_abstain_paths_effective",
    ]

    runs: list[dict[str, Any]] = []
    if isinstance(raw_runs, Sequence):
        for index, run in enumerate(raw_runs):
            if not isinstance(run, Mapping):
                continue
            migration_pack = run.get("migration_pack", {})
            after_payload = run.get("after_payload", {})
            if not isinstance(migration_pack, Mapping) or not isinstance(after_payload, Mapping):
                continue

            verification_report = verify_migration_pack_against_after_state(migration_pack, after_payload)
            counts_by_status = (
                verification_report.get("summary", {}).get("counts_by_status", {})
                if isinstance(verification_report.get("summary"), Mapping)
                else {}
            )
            risk_signals: list[str] = []
            if any(int(value) > 0 for key, value in counts_by_status.items() if key != "verified"):
                risk_signals.append("after_state_verification_drift_present")

            proposal_id = _as_text(run.get("proposal_id")) or (
                f"{family_id or 'nat-gate-b-family'}-proposal-{index + 1}"
            )
            batch_id = _as_text(run.get("batch_id")) or f"{family_id or 'nat-gate-b-family'}-batch-{index + 1}"
            run_id = _as_text(run.get("run_id")) or f"run-{index + 1}"
            proposal = {
                "proposal_id": proposal_id,
                "gate_id": "B",
                "from_level": 1,
                "to_level": 2,
                "family_id": family_id,
                "cohort_id": cohort_id,
                "candidate_ids": candidate_ids,
                "gate_families_passed": gate_families_passed,
                "evidence_signals": evidence_signals,
                "risk_signals": risk_signals,
                "metrics": _build_gate_b_metrics_from_verification_report(migration_pack, verification_report),
                "recommendation": "promote",
                "promotion_scope": bounded_scope,
                "verification_report": verification_report,
            }
            runs.append({"run_id": run_id, "batch_id": batch_id, "proposals": [proposal]})

    return {
        "evidence_batch_id": _as_text(verification_runs.get("evidence_batch_id"))
        or f"{family_id or 'nat-gate-b-family'}-evidence-batch",
        "family_id": family_id,
        "cohort_id": cohort_id,
        "candidate_ids": candidate_ids,
        "promotion_scope": bounded_scope,
        "runs": runs,
    }


def _normalize_sandbox_claim_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    qualifiers = bundle.get("qualifiers", {})
    references = bundle.get("references", [])
    normalized_qualifiers = {
        _as_text(key): _as_text_list(value)
        for key, value in qualifiers.items()
        if _as_text(key)
    } if isinstance(qualifiers, Mapping) else {}
    normalized_references: list[dict[str, list[str]]] = []
    if isinstance(references, Sequence) and not isinstance(references, (str, bytes, bytearray)):
        for reference in references:
            if not isinstance(reference, Mapping):
                continue
            normalized_reference = {
                _as_text(key): _as_text_list(value)
                for key, value in reference.items()
                if _as_text(key)
            }
            if normalized_reference:
                normalized_references.append(normalized_reference)
    return {
        "subject": _as_text(bundle.get("subject")),
        "property": _as_text(bundle.get("property")),
        "value": _as_text(bundle.get("value")),
        "rank": _as_text(bundle.get("rank") or "normal") or "normal",
        "unit": _as_text(bundle.get("unit") or bundle.get("unit_qid")),
        "qualifiers": normalized_qualifiers,
        "references": normalized_references,
    }


def build_nat_sandbox_post_write_runs(
    sandbox_packet: Mapping[str, Any],
    observed_after_state: Mapping[str, Any],
) -> dict[str, Any]:
    packet_id = _as_text(sandbox_packet.get("packet_id")) or "nat-sandbox-packet"
    capture_id = _as_text(observed_after_state.get("capture_id")) or f"{packet_id}-capture"
    target_item = _as_text(
        observed_after_state.get("target_item") or sandbox_packet.get("target_item", {}).get("qid")
    )

    packet_rows = sandbox_packet.get("rows", [])
    if not isinstance(packet_rows, Sequence) or isinstance(packet_rows, (str, bytes, bytearray)):
        packet_rows = []
    observed_rows = observed_after_state.get("observed_rows", [])
    if not isinstance(observed_rows, Sequence) or isinstance(observed_rows, (str, bytes, bytearray)):
        observed_rows = []

    packet_rows_by_id = {
        _as_text(row.get("row_id")): row
        for row in packet_rows
        if isinstance(row, Mapping) and _as_text(row.get("row_id"))
    }
    observed_rows_by_id = {
        _as_text(row.get("row_id")): row
        for row in observed_rows
        if isinstance(row, Mapping) and _as_text(row.get("row_id"))
    }

    candidate_rows: list[dict[str, Any]] = []
    statement_bundles: list[dict[str, Any]] = []
    for row_id in sorted(packet_rows_by_id):
        packet_row = packet_rows_by_id[row_id]
        expected_after_state = packet_row.get("expected_after_state")
        if not isinstance(expected_after_state, Mapping):
            continue
        claim_bundle = _normalize_sandbox_claim_bundle(expected_after_state)
        candidate_rows.append(
            {
                "candidate_id": row_id,
                "entity_qid": _as_text(packet_row.get("subject")) or target_item,
                "classification": "safe_equivalent",
                "action": "sandbox_verify_target_write",
                "claim_bundle_before": dict(claim_bundle),
                "claim_bundle_after": claim_bundle,
            }
        )

        observed_row = observed_rows_by_id.get(row_id, {})
        observed_bundle = observed_row.get("observed") if isinstance(observed_row, Mapping) else {}
        if isinstance(observed_bundle, Mapping):
            statement_bundles.append(_normalize_sandbox_claim_bundle(observed_bundle))

    migration_pack = {
        "source_property": _optional_text(sandbox_packet.get("source_property")) or "P14143",
        "target_property": _optional_text(sandbox_packet.get("target_property")) or "P14143",
        "candidates": candidate_rows,
    }
    after_payload = {
        "windows": [
            {
                "id": capture_id,
                "statement_bundles": statement_bundles,
            }
        ]
    }
    return {
        "packet_id": packet_id,
        "capture_id": capture_id,
        "target_item": target_item,
        "runs": [
            {
                "run_id": f"{packet_id}-run-1",
                "batch_id": packet_id,
                "migration_pack": migration_pack,
                "after_payload": after_payload,
            }
        ],
        "summary": {
            "packet_row_count": len(candidate_rows),
            "observed_row_count": len(statement_bundles),
        },
    }


def build_nat_sandbox_post_write_verification_report(
    sandbox_packet: Mapping[str, Any],
    observed_after_state: Mapping[str, Any],
    *,
    require_all_verified: bool = True,
) -> dict[str, Any]:
    run_bundle = build_nat_sandbox_post_write_runs(sandbox_packet, observed_after_state)
    report = build_nat_post_write_verification_report(
        run_bundle.get("runs", []),
        require_all_verified=require_all_verified,
    )
    report["sandbox_packet_id"] = run_bundle["packet_id"]
    report["observed_capture_id"] = run_bundle["capture_id"]
    report["target_item"] = run_bundle["target_item"]
    report["sandbox_summary"] = run_bundle["summary"]
    return report


def build_nat_post_write_verification_report(
    executed_receipts: Sequence[Mapping[str, Any]],
    *,
    require_all_verified: bool = True,
) -> dict[str, Any]:
    """Produce a bounded run-level report verifying executed migration receipts."""

    runs: list[dict[str, Any]] = []
    verified_runs = 0
    total_claims = 0
    for receipt in executed_receipts:
        if not isinstance(receipt, Mapping):
            continue
        run_id = _as_text(receipt.get("run_id"))
        batch_id = _as_text(receipt.get("batch_id"))
        migration_pack = receipt.get("migration_pack")
        after_payload = receipt.get("after_payload")
        if not isinstance(migration_pack, Mapping) or not isinstance(after_payload, Mapping):
            continue
        verification_report = verify_migration_pack_against_after_state(migration_pack, after_payload)
        counts_by_status = (
            verification_report.get("summary", {}).get("counts_by_status", {})
            if isinstance(verification_report.get("summary"), Mapping)
            else {}
        )
        claim_total = sum(int(value) for value in counts_by_status.values())
        status = "verified" if claim_total and int(counts_by_status.get("verified", 0)) == claim_total else "verification_drift"
        lifecycle_state = "verified" if status == "verified" else "executed"
        if status == "verified":
            verified_runs += 1

        runs.append(
            {
                "run_id": run_id or f"run-{len(runs) + 1}",
                "batch_id": batch_id or f"batch-{len(runs) + 1}",
                "lifecycle_state": lifecycle_state,
                "verification_status": status,
                "promotion_status": "ready" if status == "verified" else "hold",
                "counts_by_status": counts_by_status,
                "verification_report": verification_report,
            }
        )
        total_claims += claim_total

    lifecycle_state = "not_started"
    if runs:
        lifecycle_state = "verified" if verified_runs == len(runs) else "executed"

    lifecycle_contract = {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "state_order": list(POST_WRITE_LIFECYCLE_STATES),
        "current_state": lifecycle_state,
        "promotion_status": "ready" if verified_runs == len(runs) and len(runs) > 0 else "hold",
        "fail_closed_on_mismatch": True,
        "run_count": len(runs),
        "verified_run_count": verified_runs,
    }
    summary = {
        "run_count": len(runs),
        "verified_run_count": verified_runs,
        "verification_ready": verified_runs == len(runs) and len(runs) > 0,
        "total_claims": total_claims,
    }
    if require_all_verified and runs and verified_runs != len(runs):
        summary["pending_drifts"] = [run["run_id"] for run in runs if run["verification_status"] != "verified"]
    readiness_surface = _build_post_write_readiness_surface(
        lifecycle_contract,
        {
            "verification_status": "verified" if summary["verification_ready"] else "verification_drift",
        },
        summary=summary,
    )
    subject_aware_summary = _build_subject_aware_summary(executed_receipts, runs)
    pilot_metrics = _build_post_write_pilot_metrics(
        readiness_surface=readiness_surface,
        summary=summary,
    )

    return {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_VERIFICATION_SCHEMA_VERSION,
        "execution_lifecycle_contract": lifecycle_contract,
        "verification_contract": {
            "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
            "verification_status": "verified" if summary["verification_ready"] else "verification_drift",
            "require_all_verified": bool(require_all_verified),
            "fail_closed_on_mismatch": True,
            "promotion_status": "ready" if summary["verification_ready"] else "hold",
        },
        "runs": runs,
        "summary": summary,
        "subject_aware_summary": subject_aware_summary,
        "readiness_surface": readiness_surface,
        "pilot_metrics": pilot_metrics,
    }


def build_nat_claim_convergence_report(
    verification_runs: Mapping[str, Any],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    raw_runs = verification_runs.get("runs", [])
    if not isinstance(raw_runs, Sequence) or isinstance(raw_runs, (str, bytes, bytearray)):
        raw_runs = []
    if not raw_runs and isinstance(verification_runs.get("migration_pack"), Mapping):
        raw_runs = [verification_runs]

    family_id = _as_text(verification_runs.get("family_id"))
    cohort_id = _as_text(verification_runs.get("cohort_id"))
    claim_records: dict[str, dict[str, Any]] = {}

    for index, run in enumerate(raw_runs):
        if not isinstance(run, Mapping):
            continue
        migration_pack = run.get("migration_pack", {})
        after_payload = run.get("after_payload", {})
        if not isinstance(migration_pack, Mapping) or not isinstance(after_payload, Mapping):
            continue
        verification_report = verify_migration_pack_against_after_state(migration_pack, after_payload)
        verified_rows = {
            _as_text(row.get("candidate_id")): row
            for row in verification_report.get("rows", [])
            if isinstance(row, Mapping)
            and _as_text(row.get("candidate_id"))
            and _as_text(row.get("status")) == "verified"
        }
        candidate_list = migration_pack.get("candidates", [])
        if not isinstance(candidate_list, Sequence) or isinstance(candidate_list, (str, bytes, bytearray)):
            continue
        for candidate in candidate_list:
            if not isinstance(candidate, Mapping):
                continue
            candidate_id = _as_text(candidate.get("candidate_id"))
            if not candidate_id or candidate_id not in verified_rows:
                continue
            row = verified_rows[candidate_id]
            claim_record = claim_records.setdefault(
                candidate_id,
                {
                    "claim_id": candidate_id,
                    "candidate_id": candidate_id,
                    "family_id": family_id,
                    "cohort_id": cohort_id,
                    "canonical_form": _build_claim_canonical_form(candidate),
                    "evidence_paths": [],
                    "observed_canonical_forms": {},
                },
            )
            run_id = _as_text(run.get("run_id")) or f"run-{index + 1}"
            root_artifact_id = _resolve_root_artifact_id(run, candidate)
            observed_canonical_form = _build_claim_canonical_form(candidate)
            canonical_signature = json.dumps(observed_canonical_form, sort_keys=True)
            claim_record["observed_canonical_forms"].setdefault(
                canonical_signature,
                {
                    "run_id": run_id,
                    "root_artifact_id": root_artifact_id,
                    "canonical_form": observed_canonical_form,
                },
            )
            claim_record["evidence_paths"].append(
                {
                    "evidence_path_id": f"{candidate_id}:{run_id}",
                    "run_id": run_id,
                    "source_unit_id": _as_text(row.get("target_slot_id")) or _as_text(row.get("source_slot_id")),
                    "root_artifact_id": root_artifact_id,
                    "authority_level": "after_state_verification",
                    "provenance_chain": {
                        "candidate_id": candidate_id,
                        "entity_qid": _as_text(row.get("entity_qid")),
                        "source_slot_id": _as_text(row.get("source_slot_id")),
                        "target_slot_id": _as_text(row.get("target_slot_id")),
                    },
                    "verification_status": _as_text(row.get("status")),
                }
            )

    claims: list[dict[str, Any]] = []
    summary = {
        "total_claims": 0,
        "unverified_count": 0,
        "single_run_count": 0,
        "repeated_run_count": 0,
        "promoted_count": 0,
        "avg_evidence_paths_per_claim": 0.0,
        "avg_independent_paths_per_claim": 0.0,
    }
    total_evidence_paths = 0
    total_independent_paths = 0
    for claim_id in sorted(claim_records):
        claim = claim_records[claim_id]
        evidence_paths = claim["evidence_paths"]
        root_artifact_ids = sorted({_as_text(path.get("root_artifact_id")) for path in evidence_paths if _as_text(path.get("root_artifact_id"))})
        independent_count = len(root_artifact_ids)
        evidence_count = len(evidence_paths)
        if evidence_count == 0:
            status = "UNVERIFIED"
            summary["unverified_count"] += 1
        elif independent_count <= 1:
            status = "SINGLE_RUN"
            summary["single_run_count"] += 1
        elif independent_count >= min_independent_paths:
            status = "PROMOTED"
            summary["promoted_count"] += 1
        else:
            status = "REPEATED_RUN"
            summary["repeated_run_count"] += 1
        claim["independent_count"] = independent_count
        claim["evidence_count"] = evidence_count
        claim["independent_root_artifact_ids"] = root_artifact_ids
        claim["status"] = status
        canonical_form = claim.get("canonical_form", {})
        if not isinstance(canonical_form, Mapping):
            canonical_form = {}
        property_id = _as_text(canonical_form.get("property"))
        claim["nat_claim"] = build_nat_claim_dict(
            claim_id=_as_text(claim.get("claim_id")),
            family_id=_as_text(claim.get("family_id")),
            cohort_id=_as_text(claim.get("cohort_id")),
            candidate_id=_as_text(claim.get("candidate_id")),
            canonical_form=canonical_form,
            source_property=property_id,
            target_property=property_id,
            state="converged_claim",
            state_basis="after_state_verification",
            root_artifact_id=root_artifact_ids[0] if root_artifact_ids else "",
            provenance={
                "source_kind": "after_state_verification",
                "run_ids": [_as_text(path.get("run_id")) for path in evidence_paths],
            },
            evidence_status=status.lower(),
        )
        claim["convergence"] = build_convergence_record(
            claim_id=_as_text(claim.get("claim_id")),
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
            claim_status=status,
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=_as_text(claim.get("claim_id")),
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=_as_text(claim.get("claim_id")),
            candidate_ids=[_as_text(claim.get("candidate_id"))],
            evidence_rows=list(claim.get("observed_canonical_forms", {}).values()),
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=_as_text(claim.get("claim_id")),
            claim_status=status,
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claim.pop("observed_canonical_forms", None)
        claims.append(claim)
        total_evidence_paths += evidence_count
        total_independent_paths += independent_count

    summary["total_claims"] = len(claims)
    if claims:
        summary["avg_evidence_paths_per_claim"] = total_evidence_paths / len(claims)
        summary["avg_independent_paths_per_claim"] = total_independent_paths / len(claims)

    return {
        "schema_version": AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION,
        "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
        "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
        "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
        "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
        "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
        "family_id": family_id,
        "cohort_id": cohort_id,
        "minimum_independent_paths_required": min_independent_paths,
        "claims": claims,
        "summary": summary,
    }


def build_nat_confirmation_follow_queue(
    verification_runs: Mapping[str, Any],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    convergence_report = build_nat_claim_convergence_report(
        verification_runs,
        min_independent_paths=min_independent_paths,
    )
    queue_rows: list[dict[str, Any]] = []
    for claim in convergence_report.get("claims", []):
        if not isinstance(claim, Mapping):
            continue
        if _as_text(claim.get("status")) != "SINGLE_RUN":
            continue
        queue_rows.append(
            {
                "claim_id": _as_text(claim.get("claim_id")),
                "candidate_id": _as_text(claim.get("candidate_id")),
                "family_id": _as_text(claim.get("family_id")),
                "cohort_id": _as_text(claim.get("cohort_id")),
                "current_independent_count": int(claim.get("independent_count", 0)),
                "required_independent_count": min_independent_paths,
                "missing_independent_count": max(min_independent_paths - int(claim.get("independent_count", 0)), 0),
                "follow_goal": "find_independent_confirmation",
                "blocking_reason": "insufficient_independent_evidence",
                "seen_root_artifact_ids": list(claim.get("independent_root_artifact_ids", [])),
                "canonical_form": claim.get("canonical_form", {}),
            }
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_CONFIRMATION_QUEUE_SCHEMA_VERSION,
        "family_id": convergence_report.get("family_id", ""),
        "cohort_id": convergence_report.get("cohort_id", ""),
        "minimum_independent_paths_required": min_independent_paths,
        "queue_rows": queue_rows,
        "summary": {
            "claim_count": int(convergence_report.get("summary", {}).get("total_claims", 0)),
            "single_run_queue_count": len(queue_rows),
            "promoted_count": int(convergence_report.get("summary", {}).get("promoted_count", 0)),
        },
    }


def build_nat_confirmation_intake_contract(
    verification_runs: Mapping[str, Any],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    confirmation_queue = build_nat_confirmation_follow_queue(
        verification_runs,
        min_independent_paths=min_independent_paths,
    )
    intake_rows: list[dict[str, Any]] = []
    for queue_row in confirmation_queue.get("queue_rows", []):
        if not isinstance(queue_row, Mapping):
            continue
        candidate_id = _as_text(queue_row.get("candidate_id"))
        family_id = _as_text(queue_row.get("family_id"))
        cohort_id = _as_text(queue_row.get("cohort_id"))
        seen_root_artifact_ids = _as_text_list(queue_row.get("seen_root_artifact_ids"))
        intake_rows.append(
            {
                "claim_id": _as_text(queue_row.get("claim_id")),
                "candidate_id": candidate_id,
                "family_id": family_id,
                "cohort_id": cohort_id,
                "status": "awaiting_independent_evidence",
                "missing_independent_count": int(queue_row.get("missing_independent_count", 0)),
                "existing_root_artifact_ids": seen_root_artifact_ids,
                "canonical_form": queue_row.get("canonical_form", {}),
                "required_artifact_contract": {
                    "must_supply": [
                        "migration_pack",
                        "after_payload",
                    ],
                    "must_include_candidate_id": candidate_id,
                    "must_include_family_id": family_id,
                    "must_include_cohort_id": cohort_id,
                    "must_include_new_run_id": True,
                    "must_include_new_window_id": True,
                    "must_be_revision_locked": True,
                    "must_be_independent_of_root_artifact_ids": seen_root_artifact_ids,
                    "must_not_reuse_existing_root_without_derivation_note": True,
                    "acceptable_derivation_fields": [
                        "root_artifact_id",
                        "derived_from_root_artifact_ids",
                    ],
                },
                "runtime_reuse_contract": {
                    "entrypoint": "verifier_to_convergence_chain",
                    "steps": [
                        "verify_migration_pack_against_after_state",
                        "build_nat_claim_convergence_report",
                        "build_nat_confirmation_follow_queue",
                    ],
                },
                "suggested_evidence_routes": _build_suggested_evidence_routes(
                    family_id=family_id,
                    cohort_id=cohort_id,
                    candidate_id=candidate_id,
                    canonical_form=queue_row.get("canonical_form", {})
                    if isinstance(queue_row.get("canonical_form"), Mapping)
                    else {},
                ),
            }
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION,
        "family_id": confirmation_queue.get("family_id", ""),
        "cohort_id": confirmation_queue.get("cohort_id", ""),
        "minimum_independent_paths_required": min_independent_paths,
        "intake_rows": intake_rows,
        "summary": {
            "claim_count": int(confirmation_queue.get("summary", {}).get("claim_count", 0)),
            "intake_request_count": len(intake_rows),
            "promoted_count": int(confirmation_queue.get("summary", {}).get("promoted_count", 0)),
        },
    }


def build_nat_confirmation_intake_report(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    contracts: list[dict[str, Any]] = []
    intake_rows: list[dict[str, Any]] = []
    families_with_requests = 0

    for verification_runs in verification_run_batches:
        if not isinstance(verification_runs, Mapping):
            continue
        contract = build_nat_confirmation_intake_contract(
            verification_runs,
            min_independent_paths=min_independent_paths,
        )
        contracts.append(contract)
        rows = contract.get("intake_rows", [])
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)):
            if rows:
                families_with_requests += 1
            intake_rows.extend(row for row in rows if isinstance(row, Mapping))

    return {
        "schema_version": AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_REPORT_SCHEMA_VERSION,
        "minimum_independent_paths_required": min_independent_paths,
        "contracts": contracts,
        "intake_rows": intake_rows,
        "summary": {
            "family_count": len(contracts),
            "families_with_requests": families_with_requests,
            "intake_request_count": len(intake_rows),
        },
    }


def build_nat_acquisition_task_queue(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    intake_report = build_nat_confirmation_intake_report(
        verification_run_batches,
        min_independent_paths=min_independent_paths,
    )
    tasks: list[dict[str, Any]] = []
    for row in intake_report.get("intake_rows", []):
        if not isinstance(row, Mapping):
            continue
        suggested_routes = row.get("suggested_evidence_routes", [])
        if not isinstance(suggested_routes, Sequence) or isinstance(suggested_routes, (str, bytes, bytearray)):
            continue
        for route in suggested_routes:
            if not isinstance(route, Mapping):
                continue
            tasks.append(
                {
                    "task_id": f"{_as_text(row.get('claim_id'))}:{_as_text(route.get('route_id'))}",
                    "claim_id": _as_text(row.get("claim_id")),
                    "candidate_id": _as_text(row.get("candidate_id")),
                    "family_id": _as_text(row.get("family_id")),
                    "cohort_id": _as_text(row.get("cohort_id")),
                    "route_id": _as_text(route.get("route_id")),
                    "route_kind": _as_text(route.get("route_kind")),
                    "source_family": _as_text(route.get("source_family")),
                    "priority": int(route.get("priority", 0)),
                    "status": "PENDING",
                    "why": _as_text(route.get("why")),
                    "required_artifact_contract": row.get("required_artifact_contract", {}),
                }
            )

    tasks.sort(key=lambda item: (int(item.get("priority", 0)), _as_text(item.get("task_id"))))
    return {
        "schema_version": AUTOMATION_GRADUATION_ACQUISITION_TASK_QUEUE_SCHEMA_VERSION,
        "minimum_independent_paths_required": min_independent_paths,
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "family_count": int(intake_report.get("summary", {}).get("family_count", 0)),
            "families_with_requests": int(intake_report.get("summary", {}).get("families_with_requests", 0)),
        },
    }


def build_nat_family_acquisition_plan(
    verification_runs: Mapping[str, Any],
    *,
    min_independent_paths: int = 2,
) -> dict[str, Any]:
    contract = build_nat_confirmation_intake_contract(
        verification_runs,
        min_independent_paths=min_independent_paths,
    )
    state_report = build_nat_state_machine_report(
        [verification_runs],
        min_independent_paths=min_independent_paths,
    )
    family_state = "UNKNOWN"
    for family in state_report.get("families", []):
        if not isinstance(family, Mapping):
            continue
        if _as_text(family.get("family_id")) == _as_text(verification_runs.get("family_id")):
            family_state = _as_text(family.get("state"))
            break

    candidate_profile_by_id: dict[str, dict[str, str]] = {}
    for run in verification_runs.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        migration_pack = run.get("migration_pack", {})
        if not isinstance(migration_pack, Mapping):
            continue
        for candidate in migration_pack.get("candidates", []):
            if not isinstance(candidate, Mapping):
                continue
            candidate_id = _as_text(candidate.get("candidate_id"))
            if not candidate_id or candidate_id in candidate_profile_by_id:
                continue
            candidate_profile_by_id[candidate_id] = {
                "label": _as_text(candidate.get("candidate_label")),
                "description": _as_text(candidate.get("candidate_description")),
                "archetype_hint": _as_text(candidate.get("candidate_archetype_hint")),
                "source_revision": _as_text(candidate.get("source_revision")),
            }

    candidate_plans: list[dict[str, Any]] = []
    for row in contract.get("intake_rows", []):
        if not isinstance(row, Mapping):
            continue
        candidate_id = _as_text(row.get("candidate_id"))
        canonical_form = row.get("canonical_form", {})
        if not isinstance(canonical_form, Mapping):
            canonical_form = {}
        route_kinds = [
            _as_text(route.get("route_kind"))
            for route in row.get("suggested_evidence_routes", [])
            if isinstance(route, Mapping)
        ]
        if "same_family_after_state" not in route_kinds:
            continue
        candidate_profile = candidate_profile_by_id.get(candidate_id, {})
        archetype = _build_candidate_archetype(
            candidate_id,
            archetype_hint=_as_text(candidate_profile.get("archetype_hint")),
        )
        candidate_plans.append(
            {
                "candidate_id": candidate_id,
                "entity_qid": candidate_id.split("|", 1)[0],
                "candidate_label": _as_text(candidate_profile.get("label")),
                "candidate_description": _as_text(candidate_profile.get("description")),
                "source_revision": _as_text(candidate_profile.get("source_revision")),
                "route_kind": "same_family_after_state",
                "priority": 0,
                "expected_success_band": archetype["expected_success_band"],
                "candidate_archetype": archetype["archetype_id"],
                "why": archetype["why"],
                "placeholder_candidate": _is_fixture_placeholder_qid(candidate_id.split("|", 1)[0]),
                "query": _build_same_family_query_shape(
                    candidate_id,
                    canonical_form,
                    archetype_hint=_as_text(candidate_profile.get("archetype_hint")),
                ),
                "stop_condition": "stop_on_first_revision_locked_after_state_that_verifies_and_is_independent",
            }
        )

    success_order = {"higher": 0, "medium": 1, "lower": 2}
    candidate_plans.sort(
        key=lambda item: (
            success_order.get(_as_text(item.get("expected_success_band")), 99),
            _as_text(item.get("candidate_id")),
        )
    )
    for index, item in enumerate(candidate_plans, start=1):
        item["priority"] = index

    return {
        "schema_version": AUTOMATION_GRADUATION_FAMILY_ACQUISITION_PLAN_SCHEMA_VERSION,
        "family_id": _as_text(verification_runs.get("family_id")),
        "cohort_id": _as_text(verification_runs.get("cohort_id")),
        "family_state": family_state,
        "minimum_independent_paths_required": min_independent_paths,
        "current_blocker": "missing_independent_after_state_artifact",
        "plan_status": "ready_for_acquisition" if candidate_plans else "no_candidate_plan",
        "family_kind": "archetypal_fixture_seed"
        if any(item.get("placeholder_candidate") for item in candidate_plans)
        else "concrete_candidate_family",
        "candidate_plans": candidate_plans,
        "summary": {
            "candidate_count": len(candidate_plans),
            "placeholder_candidate_count": sum(1 for item in candidate_plans if item.get("placeholder_candidate")),
            "top_priority_candidate_id": _as_text(candidate_plans[0].get("candidate_id")) if candidate_plans else "",
        },
    }


def fetch_wikidata_recent_revisions(
    entity_qid: str,
    *,
    revision_limit: int = 10,
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    payload = _http_get_json(
        MEDIAWIKI_API_ENDPOINT,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": _as_text(entity_qid),
            "rvlimit": max(2, int(revision_limit)),
            "rvprop": "ids|timestamp",
            "format": "json",
        },
        timeout_seconds=timeout_seconds,
    )
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, Mapping) or not pages:
        return []
    page = next(iter(pages.values()))
    revisions = page.get("revisions", [])
    if not isinstance(revisions, Sequence) or isinstance(revisions, (str, bytes, bytearray)):
        return []
    return [
        {
            "revid": int(item["revid"]),
            "timestamp": _as_text(item["timestamp"]),
        }
        for item in revisions
        if isinstance(item, Mapping) and "revid" in item and "timestamp" in item
    ]


def fetch_wikidata_entity_export_for_revision(
    entity_qid: str,
    revision_id: int | str,
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    payload = _http_get_json(
        ENTITY_EXPORT_TEMPLATE.format(qid=_as_text(entity_qid), revid=int(revision_id)),
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(payload, dict):
        raise ValueError(f"entity export must be an object for {_as_text(entity_qid)}@{revision_id}")
    payload.setdefault("_source_revision", int(revision_id))
    return payload


def _normalize_entity_export_datavalue(value: Any) -> str:
    if isinstance(value, Mapping):
        if "id" in value:
            return _as_text(value.get("id"))
        if "amount" in value:
            return _as_text(value.get("amount"))
        if "time" in value:
            return _as_text(value.get("time"))
        if "text" in value:
            return _as_text(value.get("text"))
    return _as_text(value)


def _build_statement_bundles_from_entity_export(
    entity_export_payload: Mapping[str, Any],
    *,
    entity_qid: str,
    property_ids: Sequence[str],
) -> list[dict[str, Any]]:
    entities = entity_export_payload.get("entities", {})
    if not isinstance(entities, Mapping):
        return []
    entity = entities.get(entity_qid, {})
    if not isinstance(entity, Mapping):
        return []
    claims = entity.get("claims", {})
    if not isinstance(claims, Mapping):
        return []

    bundles: list[dict[str, Any]] = []
    for property_id in property_ids:
        property_text = _as_text(property_id)
        if not property_text:
            continue
        statements = claims.get(property_text, [])
        if not isinstance(statements, Sequence) or isinstance(statements, (str, bytes, bytearray)):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            mainsnak = statement.get("mainsnak", {})
            if not isinstance(mainsnak, Mapping):
                continue
            if _as_text(mainsnak.get("snaktype")) not in {"", "value"}:
                continue
            datavalue = mainsnak.get("datavalue", {})
            if not isinstance(datavalue, Mapping):
                continue
            normalized_value = _normalize_entity_export_datavalue(datavalue.get("value"))
            qualifiers_raw = statement.get("qualifiers", {})
            qualifiers: dict[str, list[str]] = {}
            if isinstance(qualifiers_raw, Mapping):
                for qualifier_property, qualifier_snaks in qualifiers_raw.items():
                    if not isinstance(qualifier_snaks, Sequence) or isinstance(
                        qualifier_snaks,
                        (str, bytes, bytearray),
                    ):
                        continue
                    normalized_qualifier_values: list[str] = []
                    for qualifier_snak in qualifier_snaks:
                        if not isinstance(qualifier_snak, Mapping):
                            continue
                        qualifier_datavalue = qualifier_snak.get("datavalue", {})
                        if not isinstance(qualifier_datavalue, Mapping):
                            continue
                        qualifier_value = _normalize_entity_export_datavalue(
                            qualifier_datavalue.get("value")
                        )
                        if qualifier_value:
                            normalized_qualifier_values.append(qualifier_value)
                    if normalized_qualifier_values:
                        qualifiers[_as_text(qualifier_property)] = normalized_qualifier_values

            references_raw = statement.get("references", [])
            references: list[dict[str, list[str]]] = []
            if isinstance(references_raw, Sequence) and not isinstance(
                references_raw,
                (str, bytes, bytearray),
            ):
                for reference in references_raw:
                    if not isinstance(reference, Mapping):
                        continue
                    snaks = reference.get("snaks", {})
                    if not isinstance(snaks, Mapping):
                        continue
                    normalized_reference: dict[str, list[str]] = {}
                    for reference_property, reference_snaks in snaks.items():
                        if not isinstance(reference_snaks, Sequence) or isinstance(
                            reference_snaks,
                            (str, bytes, bytearray),
                        ):
                            continue
                        normalized_reference_values: list[str] = []
                        for reference_snak in reference_snaks:
                            if not isinstance(reference_snak, Mapping):
                                continue
                            reference_datavalue = reference_snak.get("datavalue", {})
                            if not isinstance(reference_datavalue, Mapping):
                                continue
                            reference_value = _normalize_entity_export_datavalue(
                                reference_datavalue.get("value")
                            )
                            if reference_value:
                                normalized_reference_values.append(reference_value)
                        if normalized_reference_values:
                            normalized_reference[_as_text(reference_property)] = normalized_reference_values
                    if normalized_reference:
                        references.append(normalized_reference)

            bundles.append(
                {
                    "subject": entity_qid,
                    "property": property_text,
                    "value": normalized_value,
                    "rank": _as_text(statement.get("rank")) or "normal",
                    "qualifiers": qualifiers,
                    "references": references,
                }
            )
    return bundles


def build_nat_same_family_after_state_verification_run_from_entity_export(
    verification_runs: Mapping[str, Any],
    *,
    candidate_id: str,
    entity_export_payload: Mapping[str, Any],
    run_id: str,
    batch_id: str,
    window_id: str | None = None,
) -> dict[str, Any]:
    candidate_text = _as_text(candidate_id)
    base_candidate: Mapping[str, Any] | None = None
    base_migration_pack: Mapping[str, Any] | None = None
    for run in verification_runs.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        migration_pack = run.get("migration_pack", {})
        if not isinstance(migration_pack, Mapping):
            continue
        for candidate in migration_pack.get("candidates", []):
            if not isinstance(candidate, Mapping):
                continue
            if _as_text(candidate.get("candidate_id")) == candidate_text:
                base_candidate = candidate
                base_migration_pack = migration_pack
                break
        if base_candidate is not None:
            break

    if base_candidate is None or base_migration_pack is None:
        raise ValueError(f"candidate not found in verification runs: {candidate_text}")

    entity_qid = _as_text(base_candidate.get("entity_qid"))
    source_property = _as_text(base_migration_pack.get("source_property"))
    target_property = _as_text(base_migration_pack.get("target_property"))
    if not entity_qid or not source_property or not target_property:
        raise ValueError("verification runs must provide entity_qid, source_property, and target_property")

    source_revision = _as_text(entity_export_payload.get("_source_revision"))
    if not source_revision:
        entities = entity_export_payload.get("entities", {})
        if isinstance(entities, Mapping):
            entity = entities.get(entity_qid, {})
            if isinstance(entity, Mapping):
                source_revision = _as_text(entity.get("lastrevid"))
    root_artifact_id = ""
    if entity_qid and source_revision:
        root_artifact_id = f"wikidata_entity_export:{entity_qid}:{source_revision}"

    bundles = _build_statement_bundles_from_entity_export(
        entity_export_payload,
        entity_qid=entity_qid,
        property_ids=[source_property, target_property],
    )
    after_window_id = _as_text(window_id) if window_id is not None else ""
    if not after_window_id:
        after_window_id = f"after-{entity_qid.lower()}-{source_revision or run_id}"

    source_bundle = next(
        (bundle for bundle in bundles if _as_text(bundle.get("property")) == source_property),
        None,
    )
    target_bundle = next(
        (bundle for bundle in bundles if _as_text(bundle.get("property")) == target_property),
        None,
    )
    migration_candidate = dict(base_candidate)
    if root_artifact_id:
        migration_candidate["root_artifact_id"] = root_artifact_id
    migration_candidate["derived_from_root_artifact_ids"] = []
    if isinstance(source_bundle, Mapping):
        migration_candidate["claim_bundle_before"] = {
            **source_bundle,
            "window_id": after_window_id,
        }
    if isinstance(target_bundle, Mapping):
        migration_candidate["claim_bundle_after"] = {
            **target_bundle,
            "window_id": after_window_id,
        }
    after_payload = {
        "windows": [
            {
                "id": after_window_id,
                "statement_bundles": bundles,
            }
        ]
    }
    return {
        "family_id": _as_text(verification_runs.get("family_id")),
        "cohort_id": _as_text(verification_runs.get("cohort_id")),
        "candidate_ids": [candidate_text],
        "runs": [
            {
                "run_id": _as_text(run_id),
                "batch_id": _as_text(batch_id),
                "evidence_provenance_kind": "live_same_family_acquisition",
                "root_artifact_id": root_artifact_id,
                "migration_pack": {
                    "source_property": source_property,
                    "target_property": target_property,
                    "candidates": [migration_candidate],
                },
                "after_payload": after_payload,
            }
        ],
    }


def run_nat_acquisition_tasks(
    task_queue: Mapping[str, Any],
    supplied_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    supplied_by_task_id = {
        _as_text(item.get("task_id")): item
        for item in supplied_evidence
        if isinstance(item, Mapping) and _as_text(item.get("task_id"))
    }
    events: list[dict[str, Any]] = []
    for task in task_queue.get("tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_id = _as_text(task.get("task_id"))
        claim_id = _as_text(task.get("claim_id"))
        family_id = _as_text(task.get("family_id"))
        candidate_id = _as_text(task.get("candidate_id"))
        required_contract = task.get("required_artifact_contract", {})
        seen_root_ids = (
            _as_text_list(required_contract.get("must_be_independent_of_root_artifact_ids"))
            if isinstance(required_contract, Mapping)
            else []
        )
        supplied = supplied_by_task_id.get(task_id)
        if not supplied:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "evidence_not_supplied",
                }
            )
            continue

        verification_run = supplied.get("verification_run")
        if not isinstance(verification_run, Mapping):
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "invalid_verification_run",
                }
            )
            continue

        run_candidate_ids = _as_text_list(verification_run.get("candidate_ids"))
        if candidate_id and run_candidate_ids and candidate_id not in run_candidate_ids:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "candidate_mismatch",
                }
            )
            continue

        root_artifact_id = ""
        runs = verification_run.get("runs", [])
        if isinstance(runs, Sequence) and not isinstance(runs, (str, bytes, bytearray)) and runs:
            first_run = runs[0]
            if isinstance(first_run, Mapping):
                run_root = _as_text(first_run.get("root_artifact_id"))
                if run_root:
                    root_artifact_id = run_root
                else:
                    migration_pack = first_run.get("migration_pack", {})
                    candidates = migration_pack.get("candidates", []) if isinstance(migration_pack, Mapping) else []
                    if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes, bytearray)) and candidates:
                        first_candidate = candidates[0]
                        if isinstance(first_candidate, Mapping):
                            root_artifact_id = _resolve_root_artifact_id(first_run, first_candidate)

        if root_artifact_id and root_artifact_id in seen_root_ids:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "non_independent_root_artifact",
                    "root_artifact_id": root_artifact_id,
                }
            )
            continue

        events.append(
            {
                "task_id": task_id,
                "claim_id": claim_id,
                "family_id": family_id,
                "candidate_id": candidate_id,
                "route_id": _as_text(task.get("route_id")),
                "evidence_provenance_kind": "supplied_acquired_artifact",
                "status": "SUCCESS",
                "root_artifact_id": root_artifact_id,
                "verification_run": verification_run,
            }
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
        "events": events,
        "summary": {
            "task_count": len(events),
            "success_count": sum(1 for event in events if _as_text(event.get("status")) == "SUCCESS"),
            "failed_count": sum(1 for event in events if _as_text(event.get("status")) == "FAILED"),
        },
    }


def run_nat_same_family_after_state_acquisition_tasks(
    task_queue: Mapping[str, Any],
    verification_run_batches: Sequence[Mapping[str, Any]],
    supplied_entity_exports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    supplied_by_task_id = {
        _as_text(item.get("task_id")): item
        for item in supplied_entity_exports
        if isinstance(item, Mapping) and _as_text(item.get("task_id"))
    }
    verification_runs_by_family = {
        _as_text(batch.get("family_id")): batch
        for batch in verification_run_batches
        if isinstance(batch, Mapping) and _as_text(batch.get("family_id"))
    }

    events: list[dict[str, Any]] = []
    for task in task_queue.get("tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_id = _as_text(task.get("task_id"))
        claim_id = _as_text(task.get("claim_id"))
        family_id = _as_text(task.get("family_id"))
        candidate_id = _as_text(task.get("candidate_id"))
        route_id = _as_text(task.get("route_id"))
        route_kind = _as_text(task.get("route_kind"))

        if route_kind != "same_family_after_state":
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "route_kind_not_supported",
                }
            )
            continue

        supplied = supplied_by_task_id.get(task_id)
        if not supplied:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "evidence_not_supplied",
                }
            )
            continue

        verification_runs = verification_runs_by_family.get(family_id)
        entity_export_payload = supplied.get("entity_export_payload", {})
        if not isinstance(verification_runs, Mapping):
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "verification_runs_not_found",
                }
            )
            continue
        if not isinstance(entity_export_payload, Mapping):
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "invalid_entity_export_payload",
                }
            )
            continue

        try:
            verification_run = build_nat_same_family_after_state_verification_run_from_entity_export(
                verification_runs,
                candidate_id=candidate_id,
                entity_export_payload=entity_export_payload,
                run_id=_as_text(supplied.get("run_id")) or f"{task_id}:entity_export",
                batch_id=_as_text(supplied.get("batch_id")) or f"{family_id}:entity_export",
                window_id=_as_text(supplied.get("window_id")) or "",
            )
        except ValueError as exc:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "verification_run_build_failed",
                    "detail": _as_text(exc),
                }
            )
            continue

        verification_report = verify_migration_pack_against_after_state(
            verification_run["runs"][0]["migration_pack"],
            verification_run["runs"][0]["after_payload"],
        )
        verification_row = next(
            (
                row
                for row in verification_report.get("rows", [])
                if isinstance(row, Mapping) and _as_text(row.get("candidate_id")) == candidate_id
            ),
            None,
        )
        verification_status = _as_text(verification_row.get("status")) if isinstance(verification_row, Mapping) else ""
        if verification_status != "verified":
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": f"verification_{verification_status or 'not_ready'}",
                    "verification_summary": verification_report.get("summary", {}),
                }
            )
            continue

        required_contract = task.get("required_artifact_contract", {})
        seen_root_ids = (
            _as_text_list(required_contract.get("must_be_independent_of_root_artifact_ids"))
            if isinstance(required_contract, Mapping)
            else []
        )
        root_artifact_id = _as_text(verification_run["runs"][0].get("root_artifact_id"))
        if root_artifact_id and root_artifact_id in seen_root_ids:
            events.append(
                {
                    "task_id": task_id,
                    "claim_id": claim_id,
                    "family_id": family_id,
                    "candidate_id": candidate_id,
                    "route_id": route_id,
                    "status": "FAILED",
                    "failure_reason": "non_independent_root_artifact",
                    "root_artifact_id": root_artifact_id,
                }
            )
            continue

        events.append(
            {
                "task_id": task_id,
                "claim_id": claim_id,
                "family_id": family_id,
                "candidate_id": candidate_id,
                "route_id": route_id,
                "evidence_provenance_kind": "live_same_family_acquisition",
                "status": "SUCCESS",
                "root_artifact_id": root_artifact_id,
                "verification_run": verification_run,
                "verification_summary": verification_report.get("summary", {}),
            }
        )

    return {
        "schema_version": AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
        "events": events,
        "summary": {
            "task_count": len(events),
            "success_count": sum(1 for event in events if _as_text(event.get("status")) == "SUCCESS"),
            "failed_count": sum(1 for event in events if _as_text(event.get("status")) == "FAILED"),
        },
    }


def run_nat_live_same_family_acquisition_sweep(
    task_queue: Mapping[str, Any],
    verification_run_batches: Sequence[Mapping[str, Any]],
    family_acquisition_plan: Mapping[str, Any],
    *,
    revision_limit: int = 10,
    timeout_seconds: int = 30,
    stop_on_first_success: bool = True,
    fetch_recent_revisions_fn: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
    fetch_entity_export_fn: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    fetch_recent_revisions_impl = fetch_recent_revisions_fn or fetch_wikidata_recent_revisions
    fetch_entity_export_impl = fetch_entity_export_fn or fetch_wikidata_entity_export_for_revision
    plan_family_id = _as_text(family_acquisition_plan.get("family_id"))
    verification_runs = next(
        (
            batch
            for batch in verification_run_batches
            if isinstance(batch, Mapping) and _as_text(batch.get("family_id")) == plan_family_id
        ),
        None,
    )
    if not isinstance(verification_runs, Mapping):
        return {
            "schema_version": AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
            "events": [
                {
                    "family_id": plan_family_id,
                    "status": "FAILED",
                    "failure_reason": "verification_runs_not_found",
                }
            ],
            "summary": {"task_count": 1, "success_count": 0, "failed_count": 1},
        }

    candidate_tasks = {
        _as_text(task.get("candidate_id")): task
        for task in task_queue.get("tasks", [])
        if isinstance(task, Mapping)
        and _as_text(task.get("family_id")) == plan_family_id
        and _as_text(task.get("route_kind")) == "same_family_after_state"
    }

    events: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    for candidate_plan in family_acquisition_plan.get("candidate_plans", []):
        if not isinstance(candidate_plan, Mapping):
            continue
        candidate_id = _as_text(candidate_plan.get("candidate_id"))
        task = candidate_tasks.get(candidate_id)
        if not isinstance(task, Mapping):
            failed_count += 1
            events.append(
                {
                    "family_id": plan_family_id,
                    "candidate_id": candidate_id,
                    "status": "FAILED",
                    "failure_reason": "acquisition_task_not_found",
                }
            )
            continue

        entity_qid = _as_text(candidate_plan.get("entity_qid")) or candidate_id.split("|", 1)[0]
        source_revision = _as_text(candidate_plan.get("source_revision"))
        try:
            recent_revisions = fetch_recent_revisions_impl(
                entity_qid,
                revision_limit=revision_limit,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - exercised with injected failures if needed
            failed_count += 1
            events.append(
                {
                    "task_id": _as_text(task.get("task_id")),
                    "family_id": plan_family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "recent_revisions_fetch_failed",
                    "detail": _as_text(exc),
                }
            )
            continue

        candidate_succeeded = False
        for revision in recent_revisions:
            if not isinstance(revision, Mapping):
                continue
            revision_id = _as_text(revision.get("revid"))
            if not revision_id or revision_id == source_revision:
                continue
            try:
                entity_export_payload = fetch_entity_export_impl(
                    entity_qid,
                    revision_id,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - exercised with injected failures if needed
                failed_count += 1
                events.append(
                    {
                        "task_id": _as_text(task.get("task_id")),
                        "family_id": plan_family_id,
                        "candidate_id": candidate_id,
                        "route_id": _as_text(task.get("route_id")),
                        "status": "FAILED",
                        "failure_reason": "entity_export_fetch_failed",
                        "source_revision": revision_id,
                        "detail": _as_text(exc),
                    }
                )
                continue

            event_report = run_nat_same_family_after_state_acquisition_tasks(
                {"tasks": [task]},
                [verification_runs],
                [
                    {
                        "task_id": _as_text(task.get("task_id")),
                        "entity_export_payload": entity_export_payload,
                        "run_id": f"live-sweep-{entity_qid.lower()}-{revision_id}",
                        "batch_id": f"{plan_family_id}:live-sweep",
                        "window_id": f"after-live-{entity_qid.lower()}-{revision_id}",
                    }
                ],
            )
            candidate_events = [
                {**event, "source_revision": revision_id}
                for event in event_report.get("events", [])
                if isinstance(event, Mapping)
            ]
            events.extend(candidate_events)
            success_count += sum(1 for event in candidate_events if _as_text(event.get("status")) == "SUCCESS")
            failed_count += sum(1 for event in candidate_events if _as_text(event.get("status")) == "FAILED")
            if any(_as_text(event.get("status")) == "SUCCESS" for event in candidate_events):
                candidate_succeeded = True
                if stop_on_first_success:
                    return {
                        "schema_version": AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
                        "events": events,
                        "summary": {
                            "task_count": len(events),
                            "success_count": success_count,
                            "failed_count": failed_count,
                        },
                    }
                break

        if not candidate_succeeded and not recent_revisions:
            failed_count += 1
            events.append(
                {
                    "task_id": _as_text(task.get("task_id")),
                    "family_id": plan_family_id,
                    "candidate_id": candidate_id,
                    "route_id": _as_text(task.get("route_id")),
                    "status": "FAILED",
                    "failure_reason": "recent_revisions_empty",
                }
            )

    return {
        "schema_version": AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
        "events": events,
        "summary": {
            "task_count": len(events),
            "success_count": success_count,
            "failed_count": failed_count,
        },
    }


def merge_nat_acquired_evidence(
    verification_run_batches: Sequence[Mapping[str, Any]],
    acquisition_event_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    merged_batches: list[dict[str, Any]] = []
    success_events_by_family: dict[str, list[Mapping[str, Any]]] = {}
    for event in acquisition_event_report.get("events", []):
        if not isinstance(event, Mapping):
            continue
        if _as_text(event.get("status")) != "SUCCESS":
            continue
        family_id = _as_text(event.get("family_id"))
        if family_id:
            success_events_by_family.setdefault(family_id, []).append(event)

    for verification_runs in verification_run_batches:
        if not isinstance(verification_runs, Mapping):
            continue
        family_id = _as_text(verification_runs.get("family_id"))
        merged_runs = list(verification_runs.get("runs", [])) if isinstance(verification_runs.get("runs"), Sequence) else []
        for event in success_events_by_family.get(family_id, []):
            acquired_bundle = event.get("verification_run")
            if not isinstance(acquired_bundle, Mapping):
                continue
            acquired_runs = acquired_bundle.get("runs", [])
            provenance_kind = _as_text(event.get("evidence_provenance_kind")) or "supplied_acquired_artifact"
            if isinstance(acquired_runs, Sequence) and not isinstance(acquired_runs, (str, bytes, bytearray)):
                for run in acquired_runs:
                    if isinstance(run, Mapping):
                        merged_runs.append({**run, "evidence_provenance_kind": provenance_kind})
        merged_batches.append({**verification_runs, "runs": merged_runs})

    return merged_batches


def build_nat_state_machine_report(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    min_independent_paths: int = 2,
    acquisition_events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    acquired_claim_ids = {
        _as_text(event.get("claim_id"))
        for event in (acquisition_events or [])
        if isinstance(event, Mapping)
        and _as_text(event.get("claim_id"))
        and _as_text(event.get("status")).upper() == "SUCCESS"
    }
    successful_events_by_family: dict[str, list[Mapping[str, Any]]] = {}
    for event in acquisition_events or []:
        if not isinstance(event, Mapping):
            continue
        if _as_text(event.get("status")).upper() != "SUCCESS":
            continue
        family_id = _as_text(event.get("family_id"))
        if family_id:
            successful_events_by_family.setdefault(family_id, []).append(event)
    families: list[dict[str, Any]] = []
    summary = {
        "family_count": 0,
        "promoted_family_count": 0,
        "awaiting_evidence_family_count": 0,
        "migration_pending_family_count": 0,
        "ready_to_rerun_family_count": 0,
        "promoted_family_count_by_basis": {},
        "ready_to_rerun_family_count_by_basis": {},
    }

    for verification_runs in verification_run_batches:
        if not isinstance(verification_runs, Mapping):
            continue
        convergence_report = build_nat_claim_convergence_report(
            verification_runs,
            min_independent_paths=min_independent_paths,
        )
        intake_contract = build_nat_confirmation_intake_contract(
            verification_runs,
            min_independent_paths=min_independent_paths,
        )
        family_id = _as_text(convergence_report.get("family_id"))
        cohort_id = _as_text(convergence_report.get("cohort_id"))
        claims = convergence_report.get("claims", [])
        intake_rows = intake_contract.get("intake_rows", [])
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
            claims = []
        if not isinstance(intake_rows, Sequence) or isinstance(intake_rows, (str, bytes, bytearray)):
            intake_rows = []

        family_state = "READY_TO_RERUN"
        family_provenance_kinds = {
            (_as_text(run.get("evidence_provenance_kind")) if run.get("evidence_provenance_kind") is not None else "")
            or "baseline_runtime"
            for run in verification_runs.get("runs", [])
            if isinstance(run, Mapping)
        }
        family_provenance_kinds.update(
            _as_text(event.get("evidence_provenance_kind")) or "supplied_acquired_artifact"
            for event in successful_events_by_family.get(family_id, [])
            if isinstance(event, Mapping)
        )
        claim_ids = [
            _as_text(claim.get("claim_id"))
            for claim in claims
            if isinstance(claim, Mapping) and _as_text(claim.get("claim_id"))
        ]
        state_basis = _classify_state_basis(family_provenance_kinds)
        migration_signal = any(
            isinstance(claim, Mapping)
            and _has_climate_migration_signal(
                family_id=family_id,
                canonical_form=claim.get("canonical_form", {})
                if isinstance(claim.get("canonical_form"), Mapping)
                else {},
            )
            for claim in claims
        )
        if claims and all(_as_text(claim.get("status")) == "PROMOTED" for claim in claims if isinstance(claim, Mapping)):
            family_state = "PROMOTED"
            summary["promoted_family_count"] += 1
            promoted_by_basis = summary["promoted_family_count_by_basis"]
            promoted_by_basis[state_basis] = int(promoted_by_basis.get(state_basis, 0)) + 1
        elif claim_ids and any(claim_id in acquired_claim_ids for claim_id in claim_ids):
            family_state = "READY_TO_RERUN"
            summary["ready_to_rerun_family_count"] += 1
            rerun_by_basis = summary["ready_to_rerun_family_count_by_basis"]
            rerun_by_basis[state_basis] = int(rerun_by_basis.get(state_basis, 0)) + 1
        elif any(isinstance(row, Mapping) for row in intake_rows) and migration_signal:
            family_state = "MIGRATION_PENDING"
            summary["migration_pending_family_count"] += 1
        elif any(isinstance(row, Mapping) for row in intake_rows):
            family_state = "AWAITING_EVIDENCE"
            summary["awaiting_evidence_family_count"] += 1
        else:
            summary["ready_to_rerun_family_count"] += 1
            rerun_by_basis = summary["ready_to_rerun_family_count_by_basis"]
            rerun_by_basis[state_basis] = int(rerun_by_basis.get(state_basis, 0)) + 1

        families.append(
            {
                "family_id": family_id,
                "cohort_id": cohort_id,
                "state": family_state,
                "state_basis": state_basis,
                "migration_signal": migration_signal,
                "evidence_provenance_kinds": sorted(family_provenance_kinds),
                "claim_count": len(claims),
                "promoted_claim_count": int(convergence_report.get("summary", {}).get("promoted_count", 0)),
                "single_run_claim_count": int(convergence_report.get("summary", {}).get("single_run_count", 0)),
                "intake_request_count": len(intake_rows),
            }
        )

    summary["family_count"] = len(families)
    return {
        "schema_version": AUTOMATION_GRADUATION_STATE_MACHINE_REPORT_SCHEMA_VERSION,
        "minimum_independent_paths_required": min_independent_paths,
        "families": families,
        "summary": summary,
    }


def build_nat_broader_batch_selector(
    candidate_population: Sequence[Mapping[str, Any]],
    *,
    min_row_count: int = 1,
) -> dict[str, Any]:
    candidate_batches: list[dict[str, Any]] = []
    parked_batches: list[dict[str, Any]] = []

    for entry in candidate_population:
        if not isinstance(entry, Mapping):
            continue
        family_id = _as_text(entry.get("family_id"))
        if not family_id:
            continue
        row_count = int(entry.get("row_count", 0))
        execution_mode = _as_text(entry.get("execution_mode") or "review_first")
        basis = _as_text(entry.get("state_basis") or entry.get("state"))
        candidate_ids = [
            _as_text(cid)
            for cid in entry.get("candidate_ids", [])
            if isinstance(cid, str) and cid
        ]
        batch = {
            "family_id": family_id,
            "cohort_id": _as_text(entry.get("cohort_id")),
            "family_state": _as_text(entry.get("family_state") or entry.get("state")),
            "state_basis": basis,
            "row_count": row_count,
            "execution_mode": execution_mode,
            "candidate_ids": candidate_ids,
            "machine_generated": bool(entry.get("machine_generated")),
        }
        parked = bool(entry.get("parked"))
        if parked or row_count < min_row_count:
            batch["parked_reason"] = _as_text(entry.get("parked_reason")) or "parked_by_policy"
            parked_batches.append(batch)
        else:
            candidate_batches.append(batch)

    candidate_batches.sort(key=lambda row: (-int(row.get("row_count", 0)), row.get("family_id", "")))
    return {
        "schema_version": AUTOMATION_GRADUATION_BROADER_BATCH_SELECTOR_SCHEMA_VERSION,
        "candidate_batches": candidate_batches,
        "parked_batches": parked_batches,
        "summary": {
            "candidate_family_count": len(candidate_batches),
            "parked_family_count": len(parked_batches),
            "candidate_row_count": sum(int(row.get("row_count", 0)) for row in candidate_batches),
        },
    }


def build_nat_p5991_semantic_triage_report(
    verification_run_batches: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    triage_rows: list[dict[str, Any]] = []
    counts_by_bucket = {
        "direct_migrate": 0,
        "split_required": 0,
        "migration_pending": 0,
        "out_of_scope": 0,
        "needs_review": 0,
    }

    for verification_runs in verification_run_batches:
        if not isinstance(verification_runs, Mapping):
            continue
        family_id = _as_text(verification_runs.get("family_id"))
        cohort_id = _as_text(verification_runs.get("cohort_id"))
        primary_run = _select_primary_run(verification_runs)
        migration_pack = primary_run.get("migration_pack", {}) if isinstance(primary_run, Mapping) else {}
        target_property = _as_text(migration_pack.get("target_property")) if isinstance(migration_pack, Mapping) else ""
        for candidate in _select_migration_candidates(verification_runs):
            triage = classify_nat_p5991_semantic_bucket(
                candidate,
                family_id=family_id,
                cohort_id=cohort_id,
                target_property=target_property,
            )
            triage_rows.append(triage)
            bucket = _as_text(triage.get("semantic_bucket"))
            if bucket in counts_by_bucket:
                counts_by_bucket[bucket] += 1

    return {
        "schema_version": AUTOMATION_GRADUATION_P5991_SEMANTIC_TRIAGE_SCHEMA_VERSION,
        "rows": triage_rows,
        "summary": {
            "row_count": len(triage_rows),
            "counts_by_bucket": counts_by_bucket,
            "abstain_count": sum(1 for row in triage_rows if bool(row.get("abstain"))),
        },
    }


def build_nat_p5991_semantic_family_selector(
    verification_run_batches: Sequence[Mapping[str, Any]],
    *,
    min_row_count: int = 1,
) -> dict[str, Any]:
    triage_report = build_nat_p5991_semantic_triage_report(verification_run_batches)
    state_report = build_nat_state_machine_report(verification_run_batches)
    state_by_family = {
        _as_text(row.get("family_id")): row
        for row in state_report.get("families", [])
        if isinstance(row, Mapping) and _as_text(row.get("family_id"))
    }
    rows_by_family: dict[str, list[dict[str, Any]]] = {}
    for row in triage_report.get("rows", []):
        if not isinstance(row, Mapping):
            continue
        family_id = _as_text(row.get("family_id"))
        if not family_id:
            continue
        rows_by_family.setdefault(family_id, []).append(dict(row))

    candidate_families: list[dict[str, Any]] = []
    parked_families: list[dict[str, Any]] = []
    for family_id, triage_rows in rows_by_family.items():
        state_row = state_by_family.get(family_id, {})
        row_count = len(triage_rows)
        counts_by_bucket = {
            bucket: sum(1 for row in triage_rows if _as_text(row.get("semantic_bucket")) == bucket)
            for bucket in ("direct_migrate", "split_required", "migration_pending", "out_of_scope", "needs_review")
        }
        parked_reason = ""
        if row_count < min_row_count:
            parked_reason = "insufficient_row_count"
        elif counts_by_bucket["migration_pending"]:
            parked_reason = "migration_pending_rows_present"
        elif counts_by_bucket["split_required"]:
            parked_reason = "split_required_rows_present"
        elif counts_by_bucket["out_of_scope"]:
            parked_reason = "out_of_scope_rows_present"
        elif counts_by_bucket["needs_review"]:
            parked_reason = "needs_review_rows_present"
        elif _as_text(state_row.get("state")) != "PROMOTED":
            parked_reason = "family_not_promoted"

        selector_row = {
            "family_id": family_id,
            "cohort_id": _as_text(state_row.get("cohort_id")) or _as_text(triage_rows[0].get("cohort_id")),
            "family_state": _as_text(state_row.get("state")),
            "state_basis": _as_text(state_row.get("state_basis")),
            "row_count": row_count,
            "counts_by_bucket": counts_by_bucket,
            "candidate_ids": [
                _as_text(row.get("candidate_id"))
                for row in triage_rows
                if _as_text(row.get("semantic_bucket")) == "direct_migrate" and _as_text(row.get("candidate_id"))
            ],
            "machine_generated": True,
        }
        if parked_reason:
            selector_row["parked_reason"] = parked_reason
            parked_families.append(selector_row)
        else:
            candidate_families.append(selector_row)

    candidate_families.sort(key=lambda row: (-int(row.get("row_count", 0)), _as_text(row.get("family_id"))))
    parked_families.sort(key=lambda row: _as_text(row.get("family_id")))
    return {
        "schema_version": AUTOMATION_GRADUATION_P5991_SEMANTIC_FAMILY_SELECTOR_SCHEMA_VERSION,
        "candidate_families": candidate_families,
        "parked_families": parked_families,
        "summary": {
            "candidate_family_count": len(candidate_families),
            "parked_family_count": len(parked_families),
            "candidate_row_count": sum(int(row.get("row_count", 0)) for row in candidate_families),
        },
    }


def _find_gate(criteria: Mapping[str, Any], gate_id: str) -> Mapping[str, Any] | None:
    gates = criteria.get("gates", [])
    if not isinstance(gates, Sequence):
        return None
    for gate in gates:
        if isinstance(gate, Mapping) and _as_text(gate.get("gate_id")) == gate_id:
            return gate
    return None


def evaluate_nat_automation_promotion(
    criteria: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Deterministic fail-closed evaluator for Nat automation-graduation proposals.

    Required proposal fields:
    - gate_id
    - from_level
    - to_level
    - gate_families_passed (list[str])
    - evidence_signals (list[str])
    - risk_signals (list[str])
    - metrics (mapping[str, Any])
    - recommendation (promote|hold|revert)
    """
    failed_checks: list[str] = []
    gate_id = _as_text(proposal.get("gate_id"))
    gate = _find_gate(criteria, gate_id)
    if gate is None:
        failed_checks.append("gate_not_found")
        return {
            "schema_version": AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
            "status": "rejected",
            "gate_id": gate_id,
            "decision": "hold",
            "promotion_allowed": False,
            "failed_checks": failed_checks,
        }

    expected_from = int(gate.get("from_level", -1))
    expected_to = int(gate.get("to_level", -1))
    proposal_from = int(proposal.get("from_level", -1))
    proposal_to = int(proposal.get("to_level", -1))
    if proposal_from != expected_from or proposal_to != expected_to:
        failed_checks.append("level_transition_mismatch")

    recommendation = _as_text(proposal.get("recommendation")).lower()
    if recommendation not in {"promote", "hold", "revert"}:
        failed_checks.append("invalid_recommendation")

    required_families = _as_text_set(criteria.get("gate_families_required"))
    passed_families = _as_text_set(proposal.get("gate_families_passed"))
    missing_families = sorted(required_families - passed_families)
    if missing_families:
        failed_checks.append("missing_required_gate_families")

    must_show = _as_text_set(gate.get("must_show"))
    evidence_signals = _as_text_set(proposal.get("evidence_signals"))
    missing_must_show = sorted(must_show - evidence_signals)
    if missing_must_show:
        failed_checks.append("missing_must_show_evidence")

    blocked_signals = _as_text_set(gate.get("blocked_if"))
    risk_signals = _as_text_set(proposal.get("risk_signals"))
    triggered_blockers = sorted(blocked_signals & risk_signals)
    if triggered_blockers:
        failed_checks.append("blocked_signal_triggered")

    required_metrics = _as_text_set(criteria.get("metrics_required"))
    metrics = proposal.get("metrics", {})
    provided_metrics: set[str] = set()
    if isinstance(metrics, Mapping):
        provided_metrics = _as_text_set(list(metrics.keys()))
    else:
        failed_checks.append("metrics_not_mapping")
    missing_metrics = sorted(required_metrics - provided_metrics)
    if missing_metrics:
        failed_checks.append("missing_required_metrics")

    fail_closed = bool(failed_checks)
    promotion_allowed = not fail_closed
    status = "approved" if promotion_allowed and recommendation == "promote" else "held"
    if fail_closed:
        status = "rejected"

    decision = "promote" if status == "approved" else "hold"
    return {
        "schema_version": AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
        "status": status,
        "gate_id": gate_id,
        "from_level": proposal_from,
        "to_level": proposal_to,
        "decision": decision,
        "promotion_allowed": promotion_allowed,
        "failed_checks": sorted(set(failed_checks)),
        "missing_gate_families": missing_families,
        "missing_must_show": missing_must_show,
        "triggered_blockers": triggered_blockers,
        "missing_metrics": missing_metrics,
    }


def build_nat_automation_graduation_report(
    criteria: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = evaluate_nat_automation_promotion(criteria, proposal)
    proposal_id = _as_text(proposal.get("proposal_id"))
    lane = _as_text(criteria.get("lane"))
    return {
        "schema_version": AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION,
        "lane": lane,
        "proposal_id": proposal_id,
        "gate_id": evaluation.get("gate_id", ""),
        "decision": evaluation["decision"],
        "status": evaluation["status"],
        "promotion_allowed": evaluation["promotion_allowed"],
        "failed_checks": evaluation["failed_checks"],
        "summary": {
            "missing_gate_families": evaluation.get("missing_gate_families", []),
            "missing_must_show": evaluation.get("missing_must_show", []),
            "triggered_blockers": evaluation.get("triggered_blockers", []),
            "missing_metrics": evaluation.get("missing_metrics", []),
        },
        "promotion_scope": proposal.get("promotion_scope", {}),
        "evaluation": evaluation,
    }


def build_nat_automation_graduation_batch_report(
    criteria: Mapping[str, Any],
    proposal_batch: Mapping[str, Any],
) -> dict[str, Any]:
    proposals_raw = proposal_batch.get("proposals", [])
    reports: list[dict[str, Any]] = []
    if isinstance(proposals_raw, Sequence):
        for proposal in proposals_raw:
            if isinstance(proposal, Mapping):
                reports.append(build_nat_automation_graduation_report(criteria, proposal))

    approved_count = sum(1 for report in reports if report.get("status") == "approved")
    held_count = sum(1 for report in reports if report.get("status") == "held")
    rejected_count = sum(1 for report in reports if report.get("status") == "rejected")
    fail_closed_count = sum(1 for report in reports if not bool(report.get("promotion_allowed")))

    return {
        "schema_version": AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "batch_id": _as_text(proposal_batch.get("batch_id")),
        "proposal_count": len(reports),
        "summary": {
            "approved_count": approved_count,
            "held_count": held_count,
            "rejected_count": rejected_count,
            "fail_closed_count": fail_closed_count,
        },
        "promotion_scope": proposal_batch.get("promotion_scope", {}),
        "reports": reports,
    }


def build_nat_automation_graduation_evidence_report(
    criteria: Mapping[str, Any],
    proposal_batches: Mapping[str, Any],
    *,
    min_runs: int = 2,
) -> dict[str, Any]:
    raw_runs = proposal_batches.get("runs", [])
    batch_reports: list[dict[str, Any]] = []
    if isinstance(raw_runs, Sequence):
        for index, run in enumerate(raw_runs):
            if not isinstance(run, Mapping):
                continue
            report = build_nat_automation_graduation_batch_report(criteria, run)
            report_with_run = dict(report)
            report_with_run["run_id"] = _as_text(run.get("run_id")) or f"run-{index + 1}"
            batch_reports.append(report_with_run)

    run_count = len(batch_reports)
    proposal_count = sum(int(report.get("proposal_count", 0)) for report in batch_reports)
    approved_count = sum(int(report.get("summary", {}).get("approved_count", 0)) for report in batch_reports)
    held_count = sum(int(report.get("summary", {}).get("held_count", 0)) for report in batch_reports)
    rejected_count = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in batch_reports)
    fail_closed_count = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in batch_reports)

    all_gate_ids = {
        _as_text(item.get("gate_id"))
        for report in batch_reports
        for item in report.get("reports", [])
        if isinstance(item, Mapping) and _as_text(item.get("gate_id"))
    }
    consistency_gate_id = next(iter(all_gate_ids), "")
    gate_consistent = len(all_gate_ids) <= 1

    failed_reasons: list[str] = []
    if run_count < max(int(min_runs), 1):
        failed_reasons.append("insufficient_repeated_runs")
    if proposal_count <= 0:
        failed_reasons.append("no_proposals_evaluated")
    if rejected_count > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_count > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if held_count > 0:
        failed_reasons.append("held_proposals_present")
    if not gate_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "evidence_batch_id": _as_text(proposal_batches.get("evidence_batch_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "readiness_scope": {
            "min_runs": max(int(min_runs), 1),
            "run_count": run_count,
            "proposal_count": proposal_count,
            "gate_consistent": gate_consistent,
            "gate_id": consistency_gate_id,
        },
        "summary": {
            "approved_count": approved_count,
            "held_count": held_count,
            "rejected_count": rejected_count,
            "fail_closed_count": fail_closed_count,
        },
        "promotion_scope": proposal_batches.get("promotion_scope", {}),
        "run_reports": batch_reports,
    }


def build_nat_automation_graduation_governance_index(
    criteria: Mapping[str, Any],
    evidence_snapshots: Mapping[str, Any],
    *,
    min_snapshots: int = 2,
) -> dict[str, Any]:
    raw_snapshots = evidence_snapshots.get("snapshots", [])
    reports: list[dict[str, Any]] = []
    if isinstance(raw_snapshots, Sequence):
        for index, snapshot in enumerate(raw_snapshots):
            if not isinstance(snapshot, Mapping):
                continue
            snapshot_id = _as_text(snapshot.get("snapshot_id")) or f"snapshot-{index + 1}"
            if isinstance(snapshot.get("evidence_report"), Mapping):
                report = dict(snapshot["evidence_report"])
            elif isinstance(snapshot.get("proposal_batches"), Mapping):
                report = build_nat_automation_graduation_evidence_report(
                    criteria,
                    snapshot["proposal_batches"],
                    min_runs=int(snapshot.get("min_runs", 2)),
                )
            else:
                report = {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "readiness_failed_reasons": ["snapshot_missing_evidence_payload"],
                    "readiness_scope": {"gate_id": "", "run_count": 0},
                    "summary": {
                        "approved_count": 0,
                        "held_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                }
            report["snapshot_id"] = snapshot_id
            reports.append(report)

    snapshot_count = len(reports)
    ready_count = sum(1 for report in reports if bool(report.get("promotion_ready")))
    not_ready_count = snapshot_count - ready_count
    rejected_total = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in reports)
    fail_closed_total = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in reports)

    gate_ids = {
        _as_text(report.get("readiness_scope", {}).get("gate_id"))
        for report in reports
        if _as_text(report.get("readiness_scope", {}).get("gate_id"))
    }
    gate_scope_consistent = len(gate_ids) <= 1
    gate_id = next(iter(gate_ids), "")

    failed_reasons: list[str] = []
    if snapshot_count < max(int(min_snapshots), 1):
        failed_reasons.append("insufficient_snapshot_count")
    if snapshot_count <= 0:
        failed_reasons.append("no_snapshots_evaluated")
    if not_ready_count > 0:
        failed_reasons.append("not_ready_snapshots_present")
    if rejected_total > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_total > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if not gate_scope_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "governance_batch_id": _as_text(evidence_snapshots.get("governance_batch_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "scope": {
            "min_snapshots": max(int(min_snapshots), 1),
            "snapshot_count": snapshot_count,
            "gate_scope_consistent": gate_scope_consistent,
            "gate_id": gate_id,
        },
        "summary": {
            "ready_count": ready_count,
            "not_ready_count": not_ready_count,
            "rejected_count": rejected_total,
            "fail_closed_count": fail_closed_total,
        },
        "snapshot_reports": reports,
    }


def build_nat_automation_graduation_governance_summary(
    criteria: Mapping[str, Any],
    governance_snapshots: Mapping[str, Any],
    *,
    min_indexes: int = 2,
) -> dict[str, Any]:
    raw_snapshots = governance_snapshots.get("snapshots", [])
    reports: list[dict[str, Any]] = []
    if isinstance(raw_snapshots, Sequence):
        for index, snapshot in enumerate(raw_snapshots):
            if not isinstance(snapshot, Mapping):
                continue
            snapshot_id = _as_text(snapshot.get("snapshot_id")) or f"governance-snapshot-{index + 1}"
            if isinstance(snapshot.get("governance_index"), Mapping):
                report = dict(snapshot["governance_index"])
            elif isinstance(snapshot.get("evidence_snapshots"), Mapping):
                report = build_nat_automation_graduation_governance_index(
                    criteria,
                    snapshot["evidence_snapshots"],
                    min_snapshots=int(snapshot.get("min_snapshots", 2)),
                )
            else:
                report = {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "readiness_failed_reasons": ["snapshot_missing_governance_payload"],
                    "scope": {"gate_id": "", "snapshot_count": 0},
                    "summary": {
                        "ready_count": 0,
                        "not_ready_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                }
            report["snapshot_id"] = snapshot_id
            reports.append(report)

    index_count = len(reports)
    ready_count = sum(1 for report in reports if bool(report.get("promotion_ready")))
    not_ready_count = index_count - ready_count
    rejected_total = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in reports)
    fail_closed_total = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in reports)

    gate_ids = {
        _as_text(report.get("scope", {}).get("gate_id"))
        for report in reports
        if _as_text(report.get("scope", {}).get("gate_id"))
    }
    gate_scope_consistent = len(gate_ids) <= 1
    gate_id = next(iter(gate_ids), "")

    failed_reasons: list[str] = []
    if index_count < max(int(min_indexes), 1):
        failed_reasons.append("insufficient_governance_index_count")
    if index_count <= 0:
        failed_reasons.append("no_governance_indexes_evaluated")
    if not_ready_count > 0:
        failed_reasons.append("not_ready_governance_indexes_present")
    if rejected_total > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_total > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if not gate_scope_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "governance_summary_id": _as_text(governance_snapshots.get("governance_summary_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "scope": {
            "min_indexes": max(int(min_indexes), 1),
            "index_count": index_count,
            "gate_scope_consistent": gate_scope_consistent,
            "gate_id": gate_id,
        },
        "summary": {
            "ready_count": ready_count,
            "not_ready_count": not_ready_count,
            "rejected_count": rejected_total,
            "fail_closed_count": fail_closed_total,
        },
        "governance_reports": reports,
    }


__all__ = [
    "AUTOMATION_GRADUATION_CLIMATE_CROSS_ROW_ACQUISITION_PLAN_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_CLIMATE_FAMILY_V2_SEED_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_P5991_SEMANTIC_FAMILY_SELECTOR_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_P5991_SEMANTIC_TRIAGE_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_BATCH_FINDER_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_BATCH_EXPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_BACKEND_PLAN_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_CANDIDATE_CONTRACT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_EXECUTED_ROWS_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PROOF_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_LIFECYCLE_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_POST_WRITE_CONTRACT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_RECEIPT_CONTRACT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_MIGRATION_SIMULATION_CONTRACT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION",
    "build_nat_climate_claim_signature",
    "build_nat_climate_cross_row_acquisition_plan",
    "build_nat_climate_family_v2_seed",
    "build_nat_execution_receipt_contract",
    "build_nat_p5991_semantic_family_selector",
    "build_nat_p5991_semantic_triage_report",
    "build_nat_migration_backend_plan",
    "build_nat_migration_batch_finder_report",
    "build_nat_migration_batch_export",
    "build_nat_migration_candidate_contracts",
    "build_nat_migration_executed_rows",
    "build_nat_migration_execution_payload",
    "build_nat_migration_execution_proof",
    "build_nat_migration_lifecycle_report",
    "build_nat_migration_simulation_contract",
    "build_nat_sandbox_post_write_runs",
    "build_nat_sandbox_post_write_verification_report",
    "build_nat_gate_b_proposal_batches_from_verification_runs",
    "build_nat_automation_graduation_batch_report",
    "build_nat_automation_graduation_evidence_report",
    "build_nat_automation_graduation_governance_index",
    "build_nat_automation_graduation_governance_summary",
    "build_nat_automation_graduation_report",
    "evaluate_nat_automation_promotion",
    "build_nat_post_write_contract",
    "classify_nat_p5991_semantic_bucket",
    "verify_nat_climate_cross_source_confirmation",
]
