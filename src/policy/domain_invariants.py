"""Governed, revisioned empirical invariants for domain-pressure workflows.

This module owns generic cohort admission and snapshot aggregation.  It does
not interpret a domain model, decide a review outcome, promote a candidate, or
perform an edit.  Profiles supply policy requirements and independently
reviewed contribution records.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence


DOMAIN_INVARIANT_SNAPSHOT_SCHEMA_VERSION = "sl.domain_invariant_snapshot.v0_1"
INVARIANT_CONTRIBUTION_RECEIPT_SCHEMA_VERSION = "sl.invariant_contribution_receipt.v0_1"
INVARIANT_REVISION_RECEIPT_SCHEMA_VERSION = "sl.invariant_revision_receipt.v0_1"
TRUSTED_CONFORMING_MEMBER_SCHEMA_VERSION = "sl.trusted_conforming_member.v0_1"

CONFIRMING_DISPOSITIONS = frozenset(
    {
        "confirmed_model_conformant",
        "confirmed_conformant_after_split",
        "confirmed_conformant_after_repair",
    }
)
OBSERVED_COVERAGE_STATE = "observed"
SELECTED_CANDIDATE_ONLY_SCOPE = "selected_candidate_only"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strings(values: Sequence[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _digest(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _feature_rows(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        feature = _text(value.get("feature"))
        observed_value = _text(value.get("value"))
        if not feature or not observed_value:
            raise ValueError(
                "invariant feature contributions require feature and value"
            )
        row = {
            "feature": feature,
            "value": observed_value,
            "evidence_refs": _strings(value.get("evidence_refs") or ()),
        }
        condition = _text(value.get("condition"))
        if condition:
            row["condition"] = condition
        rows.append(row)
    rows.sort(key=lambda row: (row["feature"], row.get("condition", ""), row["value"]))
    return rows


def _contribution_context(
    *,
    candidate_ref: str,
    conformance_context_ref: str | None,
    contribution_scope: str,
    dependency_group_ref: str | None,
) -> dict[str, str | None]:
    """Validate optional context required to interpret a bounded contribution.

    A candidate may be independently confirmed, or it may be confirmed only
    after inspecting a larger evidence context such as a statement family.
    The generic invariant carrier retains that distinction without assigning
    any source-family semantics itself.
    """

    context_ref = _text(conformance_context_ref)
    group_ref = _text(dependency_group_ref)
    scope = _text(contribution_scope) or SELECTED_CANDIDATE_ONLY_SCOPE
    if scope != SELECTED_CANDIDATE_ONLY_SCOPE:
        raise ValueError("trusted contribution scope must be selected_candidate_only")
    if bool(context_ref) != bool(group_ref):
        raise ValueError(
            "conformance_context_ref and dependency_group_ref must be supplied together"
        )
    if group_ref == _text(candidate_ref):
        raise ValueError(
            "dependency_group_ref must identify context, not the candidate"
        )
    return {
        "conformance_context_ref": context_ref or None,
        "contribution_scope": scope,
        "dependency_group_ref": group_ref or None,
    }


def build_trusted_conforming_member(
    *,
    candidate_ref: str,
    source_revision_ref: str,
    review_disposition: str,
    review_decision_ref: str,
    reviewer_authority_ref: str,
    coverage_state: str,
    feature_contributions: Sequence[Mapping[str, Any]],
    source_statement_refs: Sequence[str] = (),
    conformance_context_ref: str | None = None,
    contribution_scope: str = SELECTED_CANDIDATE_ONLY_SCOPE,
    dependency_group_ref: str | None = None,
) -> dict[str, Any]:
    """Validate an independently reviewed member eligible to train a cohort."""

    normalized_disposition = _text(review_disposition)
    if normalized_disposition not in CONFIRMING_DISPOSITIONS:
        raise ValueError("trusted cohort admission requires a confirmed disposition")
    if _text(coverage_state) != OBSERVED_COVERAGE_STATE:
        raise ValueError("trusted cohort admission requires observed coverage")
    required = {
        "candidate_ref": _text(candidate_ref),
        "source_revision_ref": _text(source_revision_ref),
        "review_decision_ref": _text(review_decision_ref),
        "reviewer_authority_ref": _text(reviewer_authority_ref),
    }
    missing = sorted(name for name, value in required.items() if not value)
    if missing:
        raise ValueError("trusted cohort admission requires " + ", ".join(missing))
    features = _feature_rows(feature_contributions)
    if not features:
        raise ValueError("trusted cohort admission requires feature contributions")
    return {
        "schema_version": TRUSTED_CONFORMING_MEMBER_SCHEMA_VERSION,
        **required,
        "review_disposition": normalized_disposition,
        "coverage_state": OBSERVED_COVERAGE_STATE,
        "source_statement_refs": _strings(source_statement_refs),
        "feature_contributions": features,
        **_contribution_context(
            candidate_ref=required["candidate_ref"],
            conformance_context_ref=conformance_context_ref,
            contribution_scope=contribution_scope,
            dependency_group_ref=dependency_group_ref,
        ),
        "authority": "review_confirmed_contribution_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


def build_invariant_contribution_receipt(
    member: Mapping[str, Any],
    *,
    domain_invariant_ref: str,
) -> dict[str, Any]:
    """Make admission to a named invariant independently reconstructable."""

    normalized_member = build_trusted_conforming_member(
        candidate_ref=_text(member.get("candidate_ref")),
        source_revision_ref=_text(member.get("source_revision_ref")),
        review_disposition=_text(member.get("review_disposition")),
        review_decision_ref=_text(member.get("review_decision_ref")),
        reviewer_authority_ref=_text(member.get("reviewer_authority_ref")),
        coverage_state=_text(member.get("coverage_state")),
        feature_contributions=member.get("feature_contributions") or (),
        source_statement_refs=member.get("source_statement_refs") or (),
        conformance_context_ref=_text(member.get("conformance_context_ref")) or None,
        contribution_scope=_text(member.get("contribution_scope")),
        dependency_group_ref=_text(member.get("dependency_group_ref")) or None,
    )
    payload = {
        "schema_version": INVARIANT_CONTRIBUTION_RECEIPT_SCHEMA_VERSION,
        "domain_invariant_ref": _text(domain_invariant_ref),
        "member": normalized_member,
        "admission": "accepted",
        "authority": "review_confirmed_contribution_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    if not payload["domain_invariant_ref"]:
        raise ValueError("invariant contribution receipt requires domain_invariant_ref")
    payload["receipt_id"] = "invariant-contribution:" + _digest(payload)
    return payload


def _empirical_features(receipts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    evidence: dict[tuple[str, str, str], set[str]] = {}
    members: dict[tuple[str, str, str], set[str]] = {}
    dependency_groups: dict[tuple[str, str, str], set[str]] = {}
    for receipt in receipts:
        member = receipt.get("member")
        if not isinstance(member, Mapping):
            continue
        candidate_ref = _text(member.get("candidate_ref"))
        dependency_group_ref = _text(member.get("dependency_group_ref"))
        for feature in member.get("feature_contributions", []):
            if not isinstance(feature, Mapping):
                continue
            key = (
                _text(feature.get("feature")),
                _text(feature.get("condition")),
                _text(feature.get("value")),
            )
            if not key[0] or not key[2]:
                continue
            counts[key] += 1
            evidence.setdefault(key, set()).update(
                _strings(feature.get("evidence_refs") or ())
            )
            if candidate_ref:
                members.setdefault(key, set()).add(candidate_ref)
            if dependency_group_ref:
                dependency_groups.setdefault(key, set()).add(dependency_group_ref)
    return [
        {
            "feature": feature,
            "value": value,
            **({"condition": condition} if condition else {}),
            "confirmed_member_count": counts[(feature, condition, value)],
            "confirmed_member_refs": sorted(
                members.get((feature, condition, value), set())
            ),
            "confirmed_dependency_group_count": len(
                dependency_groups.get((feature, condition, value), set())
            ),
            "confirmed_dependency_group_refs": sorted(
                dependency_groups.get((feature, condition, value), set())
            ),
            "evidence_refs": sorted(evidence.get((feature, condition, value), set())),
        }
        for feature, condition, value in sorted(counts)
    ]


def build_invariant_revision(
    *,
    domain_invariant_ref: str,
    policy_model_ref: str,
    policy_requirements: Sequence[Mapping[str, Any]],
    contribution_receipts: Sequence[Mapping[str, Any]],
    reviewer_authority_ref: str,
    previous_snapshot_ref: str | None = None,
    conditional_features: Sequence[Mapping[str, Any]] = (),
    exception_records: Sequence[Mapping[str, Any]] = (),
    noise_records: Sequence[Mapping[str, Any]] = (),
    coverage_requirements: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a deterministic snapshot from policy and admitted members only."""

    invariant_ref = _text(domain_invariant_ref)
    policy_ref = _text(policy_model_ref)
    authority_ref = _text(reviewer_authority_ref)
    if not invariant_ref or not policy_ref or not authority_ref:
        raise ValueError(
            "invariant revision requires domain_invariant_ref, policy_model_ref, and reviewer_authority_ref"
        )
    receipts = [
        build_invariant_contribution_receipt(
            receipt.get("member", receipt), domain_invariant_ref=invariant_ref
        )
        for receipt in contribution_receipts
        if isinstance(receipt, Mapping)
    ]
    receipts.sort(key=lambda receipt: receipt["receipt_id"])
    if not receipts:
        raise ValueError(
            "invariant revision requires at least one admitted contribution"
        )
    snapshot_seed = {
        "domain_invariant_ref": invariant_ref,
        "policy_model_ref": policy_ref,
        "previous_snapshot_ref": _text(previous_snapshot_ref) or None,
        "policy_requirements": deepcopy(list(policy_requirements)),
        "contribution_receipt_refs": [receipt["receipt_id"] for receipt in receipts],
        "empirical_features": _empirical_features(receipts),
        "conditional_features": deepcopy(list(conditional_features)),
        "exception_records": deepcopy(list(exception_records)),
        "noise_records": deepcopy(list(noise_records)),
        "coverage_requirements": _strings(coverage_requirements),
        "reviewer_authority_ref": authority_ref,
    }
    snapshot = {
        "schema_version": DOMAIN_INVARIANT_SNAPSHOT_SCHEMA_VERSION,
        **snapshot_seed,
        "snapshot_id": "domain-invariant:" + _digest(snapshot_seed),
        "trusted_member_refs": sorted(
            {
                _text(receipt["member"].get("candidate_ref"))
                for receipt in receipts
                if isinstance(receipt.get("member"), Mapping)
            }
        ),
        "authority": "review_governed_empirical_model",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    revision = {
        "schema_version": INVARIANT_REVISION_RECEIPT_SCHEMA_VERSION,
        "domain_invariant_ref": invariant_ref,
        "previous_snapshot_ref": _text(previous_snapshot_ref) or None,
        "new_snapshot_ref": snapshot["snapshot_id"],
        "contribution_receipt_refs": [receipt["receipt_id"] for receipt in receipts],
        "reviewer_authority_ref": authority_ref,
        "authority": "review_governed_empirical_model",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }
    revision["receipt_id"] = "invariant-revision:" + _digest(revision)
    return {
        "snapshot": snapshot,
        "contribution_receipts": receipts,
        "revision_receipt": revision,
    }


__all__ = [
    "CONFIRMING_DISPOSITIONS",
    "DOMAIN_INVARIANT_SNAPSHOT_SCHEMA_VERSION",
    "INVARIANT_CONTRIBUTION_RECEIPT_SCHEMA_VERSION",
    "INVARIANT_REVISION_RECEIPT_SCHEMA_VERSION",
    "TRUSTED_CONFORMING_MEMBER_SCHEMA_VERSION",
    "SELECTED_CANDIDATE_ONLY_SCOPE",
    "build_invariant_contribution_receipt",
    "build_invariant_revision",
    "build_trusted_conforming_member",
]
