from __future__ import annotations

from typing import Any, Mapping

try:  # Lane 1 may add this model later.
    from src.models.composed_candidate_node import ComposedCandidateNode as _ComposedCandidateNode  # type: ignore
except Exception:  # pragma: no cover - optional integration surface
    _ComposedCandidateNode = None

SL_COMPOSED_CANDIDATE_ADMISSIBILITY_VERSION = "sl.composed_candidate_admissibility.v1"

_DECISIONS = {"promote", "audit", "abstain"}
_VALID_SECTION_GENRE_STATUSES = {"compatible", "conditional"}
_VALID_WRAPPER_STATUSES = {"valid", "accepted", "verified", "promoted"}
_ASSERTIVE_STATES = {"asserted", "admitted", "ruled"}
_DENIAL_STATES = {"denied"}
_REQUIRED_FIELDS = (
    "kind",
    "predicate_family",
    "slots",
    "content_refs",
    "authority_wrapper",
    "status",
    "support_phi_ids",
    "span_refs",
    "provenance_receipts",
    "section",
    "genre",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            out.append(text)
    return out


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        candidate = to_dict()
        if isinstance(candidate, Mapping):
            return dict(candidate)
    if hasattr(value, "__dict__"):
        public = {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
        if public:
            return public
    return {}


def _record_from_candidate(candidate: Any) -> dict[str, Any]:
    record = _mapping(candidate)
    if record:
        return record

    if _ComposedCandidateNode is not None and isinstance(candidate, _ComposedCandidateNode):  # pragma: no branch
        return _mapping(candidate)

    record = {}
    for field in _REQUIRED_FIELDS:
        if hasattr(candidate, field):
            record[field] = getattr(candidate, field)
    if record:
        return record

    raise TypeError("candidate must be a mapping or composed-candidate-like object")


def _candidate_refs(value: Any) -> set[str]:
    return set(_text_list(value))


def _receipt_refs(receipts: list[dict[str, Any]], *keys: str) -> set[str]:
    refs: set[str] = set()
    for receipt in receipts:
        for key in keys:
            raw = receipt.get(key)
            if isinstance(raw, (list, tuple, set)):
                refs.update(_text_list(raw))
            else:
                text = _text(raw)
                if text:
                    refs.add(text)
    return refs


def _status_states(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        states = {
            _text(value.get("status")).casefold(),
            _text(value.get("decision")).casefold(),
            _text(value.get("result")).casefold(),
        }
        return {state for state in states if state}
    if isinstance(value, (list, tuple, set)):
        states: set[str] = set()
        for item in value:
            states.update(_status_states(item))
        return states
    text = _text(value).casefold()
    return {text} if text else set()


def _has_structural_status_conflict(value: Any) -> bool:
    states = _status_states(value)
    return bool(states & _DENIAL_STATES) and bool(states & _ASSERTIVE_STATES)


def _provenance_completeness(record: Mapping[str, Any]) -> tuple[bool, list[str]]:
    support_phi_ids = _text_list(record.get("support_phi_ids"))
    span_refs = _text_list(record.get("span_refs"))
    receipts = record.get("provenance_receipts")
    if not support_phi_ids or not span_refs or not isinstance(receipts, list) or not receipts:
        return False, ["provenance_incomplete"]

    receipt_maps = [_mapping(receipt) for receipt in receipts if _mapping(receipt)]
    if len(receipt_maps) != len(receipts):
        return False, ["provenance_incomplete"]

    covered_phi_ids = _receipt_refs(receipt_maps, "support_phi_id", "phi_id", "source_phi_id", "support_phi_ids")
    covered_span_refs = _receipt_refs(receipt_maps, "span_ref", "span_refs", "source_span_ref", "source_span_id")
    covered_content_refs = _receipt_refs(receipt_maps, "content_ref", "content_refs", "source_content_ref", "source_content_refs")

    missing_phi_ids = [ref for ref in support_phi_ids if ref not in covered_phi_ids]
    missing_span_refs = [ref for ref in span_refs if ref not in covered_span_refs]
    if missing_phi_ids or missing_span_refs:
        return False, [
            "provenance_incomplete",
            *[f"missing_support_phi_id:{ref}" for ref in missing_phi_ids],
            *[f"missing_span_ref:{ref}" for ref in missing_span_refs],
        ]

    content_refs = _candidate_refs(record.get("content_refs"))
    if content_refs:
        missing_content_refs = [ref for ref in content_refs if ref not in covered_content_refs]
        if missing_content_refs:
            return False, [f"missing_content_ref:{ref}" for ref in missing_content_refs] + ["provenance_incomplete"]

    return True, []


def _wrapper_validity(record: Mapping[str, Any]) -> tuple[bool, list[str]]:
    wrapper = _mapping(record.get("authority_wrapper"))
    if not wrapper:
        return False, ["wrapper_missing"]

    wrapper_kind = _text(wrapper.get("wrapper_kind") or wrapper.get("kind") or wrapper.get("authority_kind"))
    if not wrapper_kind:
        return False, ["wrapper_missing_kind"]

    claimed_kind = _text(
        wrapper.get("claimed_kind")
        or wrapper.get("node_kind")
        or wrapper.get("wrapped_kind")
        or wrapper.get("candidate_kind")
    )
    candidate_kind = _text(record.get("kind"))
    if not candidate_kind:
        return False, ["candidate_kind_missing"]
    if claimed_kind and claimed_kind != candidate_kind:
        return False, ["wrapper_kind_mismatch"]

    wrapper_status = _text(wrapper.get("status") or wrapper.get("decision") or wrapper.get("validity"))
    if wrapper_status and wrapper_status.casefold() not in _VALID_WRAPPER_STATUSES:
        return False, [f"wrapper_status:{wrapper_status}"]

    allowed_kinds = set(_text_list(wrapper.get("allowed_kinds") or wrapper.get("kinds")))
    blocked_kinds = set(_text_list(wrapper.get("blocked_kinds") or wrapper.get("forbidden_kinds")))
    if allowed_kinds and candidate_kind not in allowed_kinds:
        return False, ["wrapper_kind_not_allowed"]
    if candidate_kind in blocked_kinds:
        return False, ["wrapper_kind_blocked"]

    return True, []


def _slot_content_consistency(record: Mapping[str, Any]) -> tuple[bool, list[str]]:
    slots = _mapping(record.get("slots"))
    content_refs = _candidate_refs(record.get("content_refs"))
    if not slots or not content_refs:
        return False, ["slot_content_incomplete"]

    slot_content_refs: set[str] = set()
    for slot_name, slot_value in slots.items():
        if isinstance(slot_value, Mapping):
            refs = _text_list(slot_value.get("content_refs") or slot_value.get("content_ref"))
            refs.extend(_text_list(slot_value.get("span_refs") or slot_value.get("span_ref")))
            refs.extend(_text_list(slot_value.get("support_phi_ids") or slot_value.get("support_phi_id")))
            if not refs and _text(slot_value.get("value")) and _text(slot_value.get("text")):
                continue
            slot_content_refs.update(refs)
            if refs and any(ref not in content_refs for ref in refs if ref):
                return False, [f"slot_content_mismatch:{slot_name}"]
            continue

        if isinstance(slot_value, (list, tuple, set)):
            refs = _text_list(slot_value)
            slot_content_refs.update(refs)
            if any(ref not in content_refs for ref in refs):
                return False, [f"slot_content_mismatch:{slot_name}"]
            continue

        text = _text(slot_value)
        if text and text not in content_refs:
            # A scalar slot can still be valid if it names the actual content text.
            continue

    if slot_content_refs and any(ref not in content_refs for ref in slot_content_refs):
        return False, ["slot_content_inconsistent"]

    return True, []


def _section_genre_compatibility(record: Mapping[str, Any]) -> tuple[str, list[str]]:
    section = _text(record.get("section"))
    genre = _text(record.get("genre"))
    if not section or not genre:
        return "abstain", ["section_or_genre_missing"]

    explicit = _mapping(record.get("section_genre_compatibility"))
    if explicit:
        status = _text(explicit.get("status") or explicit.get("decision") or explicit.get("result")).casefold()
        if status in _VALID_SECTION_GENRE_STATUSES:
            expected_section = _text(explicit.get("section") or explicit.get("allowed_section") or explicit.get("section_name"))
            expected_genre = _text(explicit.get("genre") or explicit.get("allowed_genre") or explicit.get("genre_name"))
            if expected_section and expected_section != section:
                return "abstain", ["section_genre_incompatible"]
            if expected_genre and expected_genre != genre:
                return "abstain", ["section_genre_incompatible"]
            return "promote", []
        if status == "incompatible":
            return "abstain", ["section_genre_incompatible"]

    wrapper = _mapping(record.get("authority_wrapper"))
    allowed_sections = set(_text_list(record.get("allowed_sections") or wrapper.get("allowed_sections")))
    allowed_genres = set(_text_list(record.get("allowed_genres") or wrapper.get("allowed_genres")))
    disallowed_sections = set(_text_list(record.get("disallowed_sections") or wrapper.get("disallowed_sections")))
    disallowed_genres = set(_text_list(record.get("disallowed_genres") or wrapper.get("disallowed_genres")))
    allowed_pairs = record.get("allowed_section_genre_pairs") or wrapper.get("allowed_section_genre_pairs")

    if section in disallowed_sections or genre in disallowed_genres:
        return "abstain", ["section_genre_incompatible"]

    if allowed_sections and section not in allowed_sections:
        return "abstain", ["section_genre_incompatible"]
    if allowed_genres and genre not in allowed_genres:
        return "abstain", ["section_genre_incompatible"]

    if isinstance(allowed_pairs, list) and allowed_pairs:
        for pair in allowed_pairs:
            pair_map = _mapping(pair)
            if not pair_map:
                continue
            pair_section = _text(pair_map.get("section") or pair_map.get("allowed_section"))
            pair_genre = _text(pair_map.get("genre") or pair_map.get("allowed_genre"))
            if pair_section == section and pair_genre == genre:
                return "promote", []
        return "abstain", ["section_genre_incompatible"]

    return "audit", ["missing_section_genre_witness"]


def _accepted_constraints_check(record: Mapping[str, Any]) -> tuple[str, list[str]]:
    constraints = record.get("accepted_constraints")
    if not isinstance(constraints, list) or not constraints:
        return "audit", ["missing_accepted_constraint_witness"]

    for constraint in constraints:
        if _has_structural_status_conflict(constraint):
            return "abstain", ["accepted_constraint_contradiction:status_conflict"]

    return "promote", []


def evaluate_composed_candidate_admissibility(
    candidate: Any,
) -> dict[str, Any]:
    record = _record_from_candidate(candidate)
    hard_failures: list[str] = []
    audit_reasons: list[str] = []

    for field in _REQUIRED_FIELDS:
        if field not in record or record.get(field) in (None, "", [], {}, ()):
            hard_failures.append(f"missing_required_field:{field}")

    if hard_failures:
        return {
            "version": SL_COMPOSED_CANDIDATE_ADMISSIBILITY_VERSION,
            "decision": "abstain",
            "reasons": hard_failures,
            "checks": {
                "provenance_complete": False,
                "wrapper_valid": False,
                "slot_content_consistent": False,
                "section_genre_compatibility": False,
                "accepted_constraints_contradiction_free": False,
            },
            "node": record,
        }

    provenance_ok, provenance_reasons = _provenance_completeness(record)
    wrapper_ok, wrapper_reasons = _wrapper_validity(record)
    slot_ok, slot_reasons = _slot_content_consistency(record)
    section_genre_decision, section_genre_reasons = _section_genre_compatibility(record)
    constraints_decision, constraint_reasons = _accepted_constraints_check(record)

    reasons: list[str] = []
    if not provenance_ok:
        reasons.extend(provenance_reasons)
    if not wrapper_ok:
        reasons.extend(wrapper_reasons)
    if not slot_ok:
        reasons.extend(slot_reasons)
    if section_genre_decision == "abstain":
        reasons.extend(section_genre_reasons)
    if constraints_decision == "abstain":
        reasons.extend(constraint_reasons)

    if reasons:
        return {
            "version": SL_COMPOSED_CANDIDATE_ADMISSIBILITY_VERSION,
            "decision": "abstain",
            "reasons": reasons,
            "checks": {
                "provenance_complete": provenance_ok,
                "wrapper_valid": wrapper_ok,
                "slot_content_consistent": slot_ok,
                "section_genre_compatibility": section_genre_decision == "promote",
                "accepted_constraints_contradiction_free": constraints_decision == "promote",
            },
            "node": record,
        }

    if section_genre_decision == "audit":
        audit_reasons.extend(section_genre_reasons)
    if constraints_decision == "audit":
        audit_reasons.extend(constraint_reasons)

    decision = "promote"
    if audit_reasons:
        decision = "audit"

    if decision not in _DECISIONS:  # pragma: no cover - defensive normalization
        decision = "abstain"

    return {
        "version": SL_COMPOSED_CANDIDATE_ADMISSIBILITY_VERSION,
        "decision": decision,
        "reasons": audit_reasons,
        "checks": {
            "provenance_complete": provenance_ok,
            "wrapper_valid": wrapper_ok,
            "slot_content_consistent": slot_ok,
            "section_genre_compatibility": section_genre_decision == "promote",
            "accepted_constraints_contradiction_free": constraints_decision == "promote",
        },
        "node": record,
    }


def gate_composed_candidate_node(candidate: Any) -> dict[str, Any]:
    return evaluate_composed_candidate_admissibility(candidate)


__all__ = [
    "SL_COMPOSED_CANDIDATE_ADMISSIBILITY_VERSION",
    "evaluate_composed_candidate_admissibility",
    "gate_composed_candidate_node",
]
