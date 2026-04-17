from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


LEGAL_EDGE_ADMISSIBILITY_VERSION = "sl.legal_edge_admissibility.v1"

_DECISIONS = {"promote", "audit", "abstain"}
_VALID_WRAPPER_STATUSES = {"valid", "accepted", "verified", "promoted"}
_VALID_SECTION_GENRE_STATUSES = {"compatible", "conditional"}
_ALLOWED_RELATION_KINDS = {
    "supports",
    "cites",
    "refines",
    "binds",
    "applies",
    "contradicts",
    "overrules",
}
_RELATIONS_REQUIRING_SHARED_LINKAGE = {
    "supports",
    "cites",
    "refines",
    "binds",
    "applies",
}
_RELATIONS_REQUIRING_SHARED_CONTENT = {"refines", "contradicts", "overrules"}
_RELATIONS_REQUIRING_STATUS_CONFLICT = {"contradicts", "overrules"}
_RELATIONS_REQUIRING_WRAPPER_KIND_MATCH = {"binds"}

_ASSERTIVE_STATES = {"asserted", "admitted", "ruled"}
_DENIAL_STATES = {"denied"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


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


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            out.append(text)
    return out


def _ref_list(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in ("support_phi_ids", "content_refs", "span_refs", "refs", "id", "value"):
            refs.extend(_text_list(value.get(key)))
            scalar = _text(value.get(key))
            if scalar:
                refs.append(scalar)
        return [ref for ref in dict.fromkeys(refs)]
    if isinstance(value, (list, tuple, set)):
        refs: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                refs.extend(_ref_list(item))
            else:
                text = _text(item)
                if text:
                    refs.append(text)
        return [ref for ref in dict.fromkeys(refs)]
    text = _text(value)
    return [text] if text else []


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


def _record_from_payload(payload: Any) -> dict[str, Any]:
    record = _mapping(payload)
    if record:
        return record
    raise TypeError("payload must be a mapping or mapping-like object")


def _endpoint_payload(value: Any) -> dict[str, Any]:
    record = _record_from_payload(value)
    admissibility = _mapping(record.get("admissibility")) or record
    node = _mapping(admissibility.get("node")) or record
    wrapper = _mapping(
        node.get("authority_wrapper")
        or node.get("wrapper")
        or admissibility.get("authority_wrapper")
        or admissibility.get("wrapper")
    )
    return {
        "decision": _text(admissibility.get("decision") or admissibility.get("status") or admissibility.get("result")).casefold(),
        "status_states": _status_states(node.get("status"))
        | _status_states(admissibility.get("status"))
        | _status_states(admissibility.get("result")),
        "wrapper_kind": _text(wrapper.get("kind") or wrapper.get("wrapper_kind") or wrapper.get("authority_kind")),
        "wrapper_status": _text(wrapper.get("status") or wrapper.get("decision") or wrapper.get("validity")).casefold(),
        "section": _text(node.get("section") or admissibility.get("section")),
        "genre": _text(node.get("genre") or admissibility.get("genre")),
        "content_refs": set(_ref_list(node.get("content_refs") or admissibility.get("content_refs"))),
        "support_phi_ids": set(_text_list(node.get("support_phi_ids") or admissibility.get("support_phi_ids"))),
        "span_refs": set(_ref_list(node.get("span_refs") or admissibility.get("span_refs"))),
        "record": record,
    }


def _shared_linkage_refs(value: Any) -> set[str]:
    record = _mapping(value)
    if record:
        refs = set(_ref_list(record.get("support_phi_ids")))
        refs.update(_ref_list(record.get("content_refs")))
        refs.update(_ref_list(record.get("span_refs")))
        refs.update(_ref_list(record.get("refs")))
        refs.update(_ref_list(record.get("value")))
        if refs:
            return refs
        for key in ("support_phi_id", "content_ref", "span_ref", "ref", "id"):
            scalar = _text(record.get(key))
            if scalar:
                refs.add(scalar)
        return refs
    return set(_ref_list(value))


def _status_conflict(left_states: set[str], right_states: set[str]) -> bool:
    return bool(left_states & _DENIAL_STATES and right_states & _ASSERTIVE_STATES) or bool(
        right_states & _DENIAL_STATES and left_states & _ASSERTIVE_STATES
    )


def _section_genre_compatibility(record: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[str, list[str]]:
    witness = _mapping(record.get("section_genre_compatibility"))
    edge_section = _text(record.get("section") or witness.get("section") or witness.get("allowed_section"))
    edge_genre = _text(record.get("genre") or witness.get("genre") or witness.get("allowed_genre"))

    if witness:
        witness_status = _text(witness.get("status") or witness.get("decision") or witness.get("result")).casefold()
        if witness_status == "incompatible":
            return "abstain", ["section_genre_incompatible"]
        if witness_status and witness_status not in _VALID_SECTION_GENRE_STATUSES:
            return "abstain", [f"section_genre_status:{witness_status}"]
        if edge_section and source["section"] and edge_section != source["section"]:
            return "abstain", ["section_genre_incompatible"]
        if edge_section and target["section"] and edge_section != target["section"]:
            return "abstain", ["section_genre_incompatible"]
        if edge_genre and source["genre"] and edge_genre != source["genre"]:
            return "abstain", ["section_genre_incompatible"]
        if edge_genre and target["genre"] and edge_genre != target["genre"]:
            return "abstain", ["section_genre_incompatible"]
        if edge_section or edge_genre:
            return "promote", []
        return "audit", ["missing_section_genre_witness"]

    if not source["section"] or not target["section"] or not source["genre"] or not target["genre"]:
        return "audit", ["missing_section_genre_witness"]
    if source["section"] != target["section"] or source["genre"] != target["genre"]:
        return "abstain", ["section_genre_incompatible"]
    return "promote", []


def _wrapper_compatibility(record: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[str, list[str]]:
    if not source["wrapper_kind"] or not target["wrapper_kind"]:
        return "audit", ["missing_wrapper_witness"]
    if source["wrapper_status"] not in _VALID_WRAPPER_STATUSES or target["wrapper_status"] not in _VALID_WRAPPER_STATUSES:
        return "abstain", ["wrapper_status_incompatible"]
    if source["wrapper_kind"] == target["wrapper_kind"]:
        if record.get("relation_kind") in _RELATIONS_REQUIRING_WRAPPER_KIND_MATCH:
            return "promote", []
        return "promote", []
    if record.get("relation_kind") in _RELATIONS_REQUIRING_WRAPPER_KIND_MATCH:
        return "abstain", ["wrapper_kind_mismatch"]
    return "promote", []


def _shared_support_linkage(record: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[str, list[str]]:
    relation_kind = _text(record.get("relation_kind") or record.get("kind")).casefold()
    linkage_refs = _shared_linkage_refs(
        record.get("shared_support_linkage")
        or record.get("support_linkage")
        or record.get("shared_linkage")
    )
    if relation_kind not in _RELATIONS_REQUIRING_SHARED_LINKAGE:
        return "promote", []
    if not linkage_refs:
        return "audit", ["missing_shared_support_linkage"]

    endpoint_refs = source["content_refs"] | source["support_phi_ids"] | source["span_refs"] | target["content_refs"] | target["support_phi_ids"] | target["span_refs"]
    if linkage_refs & endpoint_refs:
        return "promote", []
    return "abstain", ["shared_support_linkage_incompatible"]


def _relation_compatibility(record: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[str, list[str]]:
    relation_kind = _text(record.get("relation_kind") or record.get("kind")).casefold()
    if not relation_kind:
        return "abstain", ["missing_relation_kind"]
    if relation_kind not in _ALLOWED_RELATION_KINDS:
        return "abstain", [f"unsupported_relation_kind:{relation_kind}"]

    if source["decision"] == "abstain" or target["decision"] == "abstain":
        return "abstain", ["endpoint_admissibility_abstain"]
    if source["decision"] not in _DECISIONS or target["decision"] not in _DECISIONS:
        return "abstain", ["endpoint_admissibility_invalid"]

    if relation_kind in _RELATIONS_REQUIRING_SHARED_CONTENT:
        shared_content = source["content_refs"] & target["content_refs"]
        if not shared_content:
            return "audit", ["missing_shared_content_identity"]

    if relation_kind in _RELATIONS_REQUIRING_STATUS_CONFLICT:
        if not _status_conflict(source["status_states"], target["status_states"]):
            return "abstain", ["status_conflict_required"]

    if relation_kind == "overrules":
        if source["wrapper_status"] not in {"verified", "promoted"}:
            return "abstain", ["source_wrapper_status_insufficient"]
        if target["wrapper_status"] not in {"valid", "accepted", "verified"}:
            return "abstain", ["target_wrapper_status_incompatible"]

    return "promote", []


def evaluate_legal_edge_admissibility(edge: Any) -> dict[str, Any]:
    record = _record_from_payload(edge)
    source = _endpoint_payload(record.get("source_node_admissibility") or record.get("source_node") or record.get("source"))
    target = _endpoint_payload(record.get("target_node_admissibility") or record.get("target_node") or record.get("target"))

    relation_status, relation_reasons = _relation_compatibility(record, source, target)
    wrapper_status, wrapper_reasons = _wrapper_compatibility(record, source, target)
    section_status, section_reasons = _section_genre_compatibility(record, source, target)
    linkage_status, linkage_reasons = _shared_support_linkage(record, source, target)

    hard_reasons: list[str] = []
    audit_reasons: list[str] = []
    if relation_status == "abstain":
        hard_reasons.extend(relation_reasons)
    elif relation_status == "audit":
        audit_reasons.extend(relation_reasons)

    if wrapper_status == "abstain":
        hard_reasons.extend(wrapper_reasons)
    elif wrapper_status == "audit":
        audit_reasons.extend(wrapper_reasons)

    if section_status == "abstain":
        hard_reasons.extend(section_reasons)
    elif section_status == "audit":
        audit_reasons.extend(section_reasons)

    if linkage_status == "abstain":
        hard_reasons.extend(linkage_reasons)
    elif linkage_status == "audit":
        audit_reasons.extend(linkage_reasons)

    if source["decision"] == "audit":
        audit_reasons.append("source_endpoint_audit")
    if target["decision"] == "audit":
        audit_reasons.append("target_endpoint_audit")

    if source["decision"] == "abstain":
        hard_reasons.append("source_endpoint_abstain")
    if target["decision"] == "abstain":
        hard_reasons.append("target_endpoint_abstain")

    if hard_reasons:
        decision = "abstain"
    elif audit_reasons:
        decision = "audit"
    else:
        decision = "promote"

    checks = {
        "relation_kind_supported": relation_status == "promote",
        "source_endpoint_admissible": source["decision"] in {"promote", "audit"},
        "target_endpoint_admissible": target["decision"] in {"promote", "audit"},
        "wrapper_compatible": wrapper_status == "promote",
        "section_genre_compatible": section_status == "promote",
        "shared_support_linkage_present": linkage_status == "promote",
    }

    return {
        "version": LEGAL_EDGE_ADMISSIBILITY_VERSION,
        "decision": decision,
        "reasons": hard_reasons or audit_reasons,
        "checks": checks,
        "edge": {
            "relation_kind": _text(record.get("relation_kind") or record.get("kind")).casefold(),
            "source_node_admissibility": source,
            "target_node_admissibility": target,
            "shared_support_linkage": sorted(_shared_linkage_refs(
                record.get("shared_support_linkage")
                or record.get("support_linkage")
                or record.get("shared_linkage")
            )),
            "section_genre_compatibility": _mapping(record.get("section_genre_compatibility")),
        },
    }


def gate_legal_edge_admissibility(edge: Any) -> dict[str, Any]:
    return evaluate_legal_edge_admissibility(edge)


__all__ = [
    "LEGAL_EDGE_ADMISSIBILITY_VERSION",
    "evaluate_legal_edge_admissibility",
    "gate_legal_edge_admissibility",
]
