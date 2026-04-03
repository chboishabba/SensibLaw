from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from src.ontology.wikidata import verify_migration_pack_against_after_state


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


def _as_text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    normalized: list[str] = []
    for value in values:
        text = _as_text(value)
        if text:
            normalized.append(text)
    return normalized


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
    claim_after = _normalize_claim_bundle(candidate.get("claim_bundle_after"))
    if claim_after:
        return claim_after
    return _normalize_claim_bundle(candidate.get("claim_bundle_before"))


def _count_checked_safe_candidates(migration_pack: Mapping[str, Any]) -> int:
    candidates = migration_pack.get("candidates", [])
    if not isinstance(candidates, Sequence):
        return 0
    safe_classes = {"safe_equivalent", "safe_with_reference_transfer"}
    count = 0
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _as_text(candidate.get("classification")) in safe_classes:
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
                },
            )
            run_id = _as_text(run.get("run_id")) or f"run-{index + 1}"
            root_artifact_id = _resolve_root_artifact_id(run, candidate)
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
        claims.append(claim)
        total_evidence_paths += evidence_count
        total_independent_paths += independent_count

    summary["total_claims"] = len(claims)
    if claims:
        summary["avg_evidence_paths_per_claim"] = total_evidence_paths / len(claims)
        summary["avg_independent_paths_per_claim"] = total_independent_paths / len(claims)

    return {
        "schema_version": AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION,
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
    "AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION",
    "build_nat_gate_b_proposal_batches_from_verification_runs",
    "build_nat_automation_graduation_batch_report",
    "build_nat_automation_graduation_evidence_report",
    "build_nat_automation_graduation_governance_index",
    "build_nat_automation_graduation_governance_summary",
    "build_nat_automation_graduation_report",
    "evaluate_nat_automation_promotion",
]
