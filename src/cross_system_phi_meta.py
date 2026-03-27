from __future__ import annotations

from typing import Any, Mapping

SL_CROSS_SYSTEM_PHI_META_VERSION = "sl.cross_system_phi_meta.v1"

_RELATION_VALUES = {"exact", "refinement", "abstraction", "analogue", "incompatible", "none"}
_CONSTRAINT_STATUS_VALUES = {"compatible", "incompatible", "unknown", "conditional"}


def _record_type(record: Mapping[str, Any]) -> str:
    return f"{record['subject_kind']}->{record['object_kind']}"


def _record_roles(record: Mapping[str, Any]) -> list[str]:
    return [f"subject_{record['subject_kind']}", f"object_{record['object_kind']}"]


def _record_domain(record: Mapping[str, Any]) -> str | None:
    rule_type = str(record.get("rule_type") or "").strip()
    if rule_type == "review_relation":
        return "review"
    if rule_type in {"governance_action", "executive_action"}:
        return "governance"
    return None


def _record_authority_type(record: Mapping[str, Any]) -> str:
    rule_type = str(record.get("rule_type") or "").strip()
    predicate_key = str(record.get("predicate_key") or "").strip()
    subject_key = str(record.get("subject_key") or "").strip().lower()
    object_key = str(record.get("object_key") or "").strip().lower()

    if "court" in object_key or predicate_key in {"heard_by", "ruled_by", "challenged", "appealed"}:
        return "judicial"
    if "senate" in object_key or "congress" in object_key:
        return "legislative"
    if rule_type == "executive_action" or predicate_key in {"signed", "vetoed"} or "president" in subject_key or "bush" in subject_key:
        return "executive"
    if rule_type == "review_relation":
        return "judicial"
    if rule_type == "governance_action":
        return "governance"
    return "unknown"


def _lookup_alignment(left: str, right: str, alignments: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for row in alignments:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("left_type") or row.get("left_role") or row.get("left_authority") or "").strip() != left:
            continue
        if str(row.get("right_type") or row.get("right_role") or row.get("right_authority") or "").strip() != right:
            continue
        return row
    return None


def _best_role_score(left_roles: list[str], right_roles: list[str], alignments: list[Mapping[str, Any]]) -> float:
    if not left_roles or not right_roles:
        return 0.0
    scores: list[float] = []
    for left_role in left_roles:
        best = 0.0
        for right_role in right_roles:
            alignment = _lookup_alignment(left_role, right_role, alignments)
            if alignment is None:
                continue
            best = max(best, float(alignment.get("score") or 0.0))
        scores.append(best)
    return sum(scores) / len(scores) if scores else 0.0


def _best_role_witnesses(left_roles: list[str], right_roles: list[str], alignments: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    witnesses: list[dict[str, Any]] = []
    for left_role in left_roles:
        best_alignment: Mapping[str, Any] | None = None
        best_score = -1.0
        for right_role in right_roles:
            alignment = _lookup_alignment(left_role, right_role, alignments)
            if alignment is None:
                continue
            score = float(alignment.get("score") or 0.0)
            if score > best_score:
                best_alignment = alignment
                best_score = score
        if best_alignment is None:
            witnesses.append(
                {
                    "left_role": left_role,
                    "right_role": None,
                    "relation": "none",
                    "score": 0.0,
                }
            )
            continue
        witnesses.append(
            {
                "left_role": left_role,
                "right_role": str(best_alignment.get("right_role") or ""),
                "relation": str(best_alignment.get("relation") or ""),
                "score": float(best_alignment.get("score") or 0.0),
            }
        )
    return witnesses


def _scope_ok(left: Mapping[str, Any], right: Mapping[str, Any], scope_rules: Mapping[str, Any]) -> tuple[bool, str]:
    whitelist = scope_rules.get("domain_whitelist", [])
    if isinstance(whitelist, list) and whitelist:
        left_domain = _record_domain(left)
        right_domain = _record_domain(right)
        if left_domain not in whitelist or right_domain not in whitelist:
            return False, "domain_not_whitelisted"

    if bool(scope_rules.get("temporal_overlap_required")):
        left_temporal = left.get("temporal_scope")
        right_temporal = right.get("temporal_scope")
        if left_temporal is None or right_temporal is None or left_temporal != right_temporal:
            return False, "temporal_scope_mismatch"

    if bool(scope_rules.get("jurisdiction_overlap_required")):
        left_jurisdiction = left.get("jurisdiction_scope")
        right_jurisdiction = right.get("jurisdiction_scope")
        if left_jurisdiction is None or right_jurisdiction is None:
            return False, "jurisdiction_scope_missing"
        if left_jurisdiction != right_jurisdiction:
            return False, "jurisdiction_scope_mismatch"

    return True, "satisfied"


def _relation_summary(relation: str) -> str:
    if relation == "exact":
        return "exact alignment"
    if relation == "analogue":
        return "analogue alignment"
    if relation == "refinement":
        return "refinement alignment"
    if relation == "abstraction":
        return "abstraction alignment"
    if relation == "incompatible":
        return "incompatible alignment"
    return "no alignment"


def build_default_phi_meta_contract(*, left_system: str, right_system: str) -> dict[str, Any]:
    return {
        "meta_mapping_id": f"phi_meta.{left_system}.{right_system}.v1",
        "left_system": left_system,
        "right_system": right_system,
        "version": SL_CROSS_SYSTEM_PHI_META_VERSION,
        "type_alignments": [
            {"left_type": "actor->actor", "right_type": "actor->actor", "relation": "exact", "score": 1.0},
            {"left_type": "actor->legal_ref", "right_type": "actor->legal_ref", "relation": "exact", "score": 1.0},
            {"left_type": "legal_ref->actor", "right_type": "legal_ref->actor", "relation": "exact", "score": 1.0},
            {"left_type": "legal_ref->legal_ref", "right_type": "legal_ref->legal_ref", "relation": "exact", "score": 1.0},
        ],
        "role_alignments": [
            {"left_role": "subject_actor", "right_role": "subject_actor", "relation": "exact", "score": 1.0},
            {"left_role": "subject_legal_ref", "right_role": "subject_legal_ref", "relation": "exact", "score": 1.0},
            {"left_role": "object_actor", "right_role": "object_actor", "relation": "exact", "score": 1.0},
            {"left_role": "object_legal_ref", "right_role": "object_legal_ref", "relation": "exact", "score": 1.0},
        ],
        "authority_alignments": [
            {"left_authority": "judicial", "right_authority": "judicial", "relation": "exact", "score": 1.0},
            {"left_authority": "executive", "right_authority": "executive", "relation": "exact", "score": 1.0},
            {"left_authority": "legislative", "right_authority": "legislative", "relation": "exact", "score": 1.0},
            {"left_authority": "judicial", "right_authority": "executive", "relation": "analogue", "score": 0.62},
            {"left_authority": "executive", "right_authority": "judicial", "relation": "analogue", "score": 0.62},
            {"left_authority": "judicial", "right_authority": "legislative", "relation": "incompatible", "score": 0.15},
            {"left_authority": "legislative", "right_authority": "judicial", "relation": "incompatible", "score": 0.15},
        ],
        "constraint_compatibility": [
            {"left_constraint": "review_relation", "right_constraint": "review_relation", "status": "compatible"},
            {"left_constraint": "review_relation", "right_constraint": "executive_action", "status": "conditional"},
            {"left_constraint": "executive_action", "right_constraint": "review_relation", "status": "conditional"},
            {"left_constraint": "review_relation", "right_constraint": "governance_action", "status": "incompatible"},
            {"left_constraint": "governance_action", "right_constraint": "review_relation", "status": "incompatible"},
            {"left_constraint": "executive_action", "right_constraint": "governance_action", "status": "unknown"},
            {"left_constraint": "governance_action", "right_constraint": "executive_action", "status": "unknown"},
        ],
        "scope_rules": {
            "temporal_overlap_required": False,
            "jurisdiction_overlap_required": False,
            "domain_whitelist": ["review", "governance"],
        },
        "forbidden_pairs": [
            {
                "left_type": "divine_command",
                "right_type": "contractual_obligation",
                "reason": "authority model mismatch",
            }
        ],
        "thresholds": {
            "min_type_score": 0.7,
            "min_role_score": 0.7,
            "min_authority_score": 0.6,
            "min_total_score": 0.72,
        },
        "witness_policy": {
            "require_anchor_trace_on_both_sides": True,
            "require_promoted_inputs_only": True,
            "require_constraint_check": True,
        },
    }


def validate_phi_meta_contract_schema(contract: Mapping[str, Any]) -> None:
    if str(contract.get("version") or "").strip() != SL_CROSS_SYSTEM_PHI_META_VERSION:
        raise ValueError("unsupported phi meta contract version")
    for field in ("meta_mapping_id", "left_system", "right_system"):
        if not isinstance(contract.get(field), str) or not str(contract.get(field)).strip():
            raise ValueError(f"{field} is required")
    for field in ("type_alignments", "role_alignments", "authority_alignments", "constraint_compatibility", "forbidden_pairs"):
        if not isinstance(contract.get(field), list):
            raise ValueError(f"{field} must be a list")
    for alignment_field in ("type_alignments", "role_alignments", "authority_alignments"):
        for row in contract.get(alignment_field, []):
            relation = str(row.get("relation") or "").strip()
            if relation not in _RELATION_VALUES:
                raise ValueError(f"unsupported relation value in {alignment_field}: {relation}")
    for row in contract.get("constraint_compatibility", []):
        status = str(row.get("status") or "").strip()
        if status not in _CONSTRAINT_STATUS_VALUES:
            raise ValueError(f"unsupported constraint compatibility status: {status}")


def validate_phi_meta(
    *,
    left_record: Mapping[str, Any],
    right_record: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    validate_phi_meta_contract_schema(contract)
    violations: list[str] = []
    witness_requirements: list[str] = []
    witness_policy = contract.get("witness_policy", {})

    if bool(witness_policy.get("require_promoted_inputs_only")):
        if str(left_record.get("promotion_status") or "") != "promoted_true":
            violations.append("non_promoted_input_left")
        if str(right_record.get("promotion_status") or "") != "promoted_true":
            violations.append("non_promoted_input_right")

    if bool(witness_policy.get("require_anchor_trace_on_both_sides")):
        witness_requirements.extend(["anchor_trace_left", "anchor_trace_right"])
        if left_record.get("source_char_start") is None or left_record.get("source_char_end") is None:
            violations.append("missing_anchor_trace_left")
        if right_record.get("source_char_start") is None or right_record.get("source_char_end") is None:
            violations.append("missing_anchor_trace_right")

    if bool(witness_policy.get("require_constraint_check")):
        witness_requirements.append("constraint_check")

    left_type = _record_type(left_record)
    right_type = _record_type(right_record)
    for forbidden in contract.get("forbidden_pairs", []):
        if str(forbidden.get("left_type") or "").strip() == left_type and str(forbidden.get("right_type") or "").strip() == right_type:
            violations.append(
                f"forbidden_pair:{left_type}->{right_type}:{str(forbidden.get('reason') or '').strip() or 'forbidden'}"
            )

    type_alignment = _lookup_alignment(left_type, right_type, list(contract.get("type_alignments", [])))
    type_score = float(type_alignment.get("score") or 0.0) if type_alignment else 0.0
    if type_alignment is None:
        violations.append("missing_type_alignment")
    elif str(type_alignment.get("relation") or "").strip() in {"incompatible", "none"}:
        violations.append(f"type_relation_{str(type_alignment.get('relation') or '').strip()}")

    role_score = _best_role_score(_record_roles(left_record), _record_roles(right_record), list(contract.get("role_alignments", [])))
    role_witnesses = _best_role_witnesses(_record_roles(left_record), _record_roles(right_record), list(contract.get("role_alignments", [])))
    if role_score == 0.0:
        violations.append("missing_role_alignment")

    left_authority = _record_authority_type(left_record)
    right_authority = _record_authority_type(right_record)
    authority_alignment = _lookup_alignment(left_authority, right_authority, list(contract.get("authority_alignments", [])))
    authority_score = float(authority_alignment.get("score") or 0.0) if authority_alignment else 0.0
    if authority_alignment is None:
        violations.append("missing_authority_alignment")
    elif str(authority_alignment.get("relation") or "").strip() in {"incompatible", "none"}:
        violations.append(f"authority_relation_{str(authority_alignment.get('relation') or '').strip()}")

    constraint_status = "unknown"
    left_constraint = str(left_record.get("rule_type") or "").strip() or "unknown"
    right_constraint = str(right_record.get("rule_type") or "").strip() or "unknown"
    for row in contract.get("constraint_compatibility", []):
        if str(row.get("left_constraint") or "").strip() != left_constraint:
            continue
        if str(row.get("right_constraint") or "").strip() != right_constraint:
            continue
        constraint_status = str(row.get("status") or "").strip() or "unknown"
        break
    if constraint_status == "incompatible":
        violations.append("constraint_status_incompatible")
    elif constraint_status == "unknown":
        violations.append("constraint_status_unknown")

    scope_ok, scope_status = _scope_ok(left_record, right_record, contract.get("scope_rules", {}))
    if not scope_ok:
        violations.append(scope_status)

    thresholds = contract.get("thresholds", {})
    if type_score < float(thresholds.get("min_type_score", 0.7)):
        violations.append("type_score_below_threshold")
    if role_score < float(thresholds.get("min_role_score", 0.7)):
        violations.append("role_score_below_threshold")
    if authority_score < float(thresholds.get("min_authority_score", 0.6)):
        violations.append("authority_score_below_threshold")

    meta_score = 0.4 * type_score + 0.3 * role_score + 0.3 * authority_score
    if meta_score < float(thresholds.get("min_total_score", 0.72)):
        violations.append("meta_score_below_threshold")

    allowed = not violations and constraint_status in {"compatible", "conditional"}

    witness = {
        "type_alignment": {
            "left_type": left_type,
            "right_type": right_type,
            "relation": str(type_alignment.get("relation") or "none") if type_alignment else "none",
            "score": round(type_score, 4),
            "summary": _relation_summary(str(type_alignment.get("relation") or "none") if type_alignment else "none"),
        },
        "role_alignments": role_witnesses,
        "authority_alignment": {
            "left_authority": left_authority,
            "right_authority": right_authority,
            "relation": str(authority_alignment.get("relation") or "none") if authority_alignment else "none",
            "score": round(authority_score, 4),
            "summary": _relation_summary(str(authority_alignment.get("relation") or "none") if authority_alignment else "none"),
        },
        "constraint_check": {
            "left_constraint": left_constraint,
            "right_constraint": right_constraint,
            "status": constraint_status,
        },
        "scope_check": {
            "status": scope_status,
            "left_domain": _record_domain(left_record),
            "right_domain": _record_domain(right_record),
        },
    }

    return {
        "allowed": allowed,
        "meta_score": round(meta_score, 4),
        "type_score": round(type_score, 4),
        "role_score": round(role_score, 4),
        "authority_score": round(authority_score, 4),
        "constraint_status": constraint_status,
        "scope_status": scope_status,
        "violations": violations,
        "witness_requirements": witness_requirements,
        "left_type": left_type,
        "right_type": right_type,
        "left_authority": left_authority,
        "right_authority": right_authority,
        "witness": witness,
    }


__all__ = [
    "SL_CROSS_SYSTEM_PHI_META_VERSION",
    "build_default_phi_meta_contract",
    "validate_phi_meta",
    "validate_phi_meta_contract_schema",
]
