from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ACTION_POLICY_SCHEMA_VERSION = "sl.world_model_action_policy.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class ActionPolicyRecord:
    claim_id: str
    actionability: str
    policy_basis: dict[str, Any]
    schema_version: str = ACTION_POLICY_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "actionability": self.actionability,
            "policy_basis": dict(self.policy_basis),
        }


def build_action_policy_record(
    *,
    claim_id: str,
    claim_status: str,
    convergence: Mapping[str, Any],
    temporal: Mapping[str, Any],
    conflict_set: Mapping[str, Any],
) -> dict[str, Any]:
    claim_status_text = _as_text(claim_status)
    conflict_status = _as_text(conflict_set.get("resolution_status"))
    conflict_type = _as_text(conflict_set.get("conflict_type"))
    convergence_state = _as_text(convergence.get("convergence_state"))
    observed_at = _as_text(temporal.get("observed_at"))

    if conflict_status == "requires_review":
        actionability = "must_review"
    elif claim_status_text in {"REVIEW_ONLY", "REVIEW"}:
        actionability = "must_review"
    elif claim_status_text == "PROMOTED" and convergence_state == "GOVERNED":
        actionability = "can_act"
    elif claim_status_text == "REPEATED_RUN":
        actionability = "can_recommend"
    else:
        actionability = "must_abstain"

    record = ActionPolicyRecord(
        claim_id=_as_text(claim_id),
        actionability=actionability,
        policy_basis={
            "claim_status": claim_status_text,
            "convergence_state": convergence_state,
            "conflict_type": conflict_type,
            "conflict_resolution_status": conflict_status,
            "observed_at": observed_at,
            "requires_more_evidence": claim_status_text != "PROMOTED",
        },
    )
    return record.as_dict()
