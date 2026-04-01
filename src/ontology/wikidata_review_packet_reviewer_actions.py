from __future__ import annotations

from typing import Any, Mapping, Sequence


WIKIDATA_REVIEW_PACKET_REVIEWER_ACTIONS_SCHEMA_VERSION = (
    "sl.wikidata_review_packet.reviewer_actions.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_stringify(item).strip() for item in value if _stringify(item).strip()]


def _smallest_next_check(
    *,
    uncertainty_flags: Sequence[str],
    merged_split_axes: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    flags = set(_string_list(uncertainty_flags))
    if "reference_propagation_requires_review" in flags:
        return {
            "check_id": "check_reference_propagation",
            "rationale": "reference propagation is not exact and should be verified first",
        }
    if "qualifier_propagation_requires_review" in flags:
        return {
            "check_id": "check_qualifier_propagation",
            "rationale": "qualifier propagation is not exact and should be verified first",
        }
    if merged_split_axes:
        axis = merged_split_axes[0]
        return {
            "check_id": "confirm_first_split_axis",
            "rationale": (
                "split plan is axis-driven; confirm first axis "
                f"property={_stringify(axis.get('property'))} "
                f"cardinality={_stringify(axis.get('cardinality'))}"
            ).strip(),
        }
    if "page_open_questions" in flags:
        return {
            "check_id": "resolve_one_page_question",
            "rationale": "open page questions remain unresolved",
        }
    if "no_follow_receipts" in flags:
        return {
            "check_id": "establish_one_bounded_follow_receipt",
            "rationale": "packet has no follow receipt evidence yet",
        }
    return {
        "check_id": "spot_check_first_candidate",
        "rationale": "no higher-priority uncertainty flag was detected",
    }


def build_wikidata_review_packet_reviewer_actions(packet: Mapping[str, Any]) -> dict[str, Any]:
    split_review_context = packet.get("split_review_context")
    reviewer_view = packet.get("reviewer_view")
    if not isinstance(split_review_context, Mapping):
        raise ValueError("packet requires split_review_context")
    if not isinstance(reviewer_view, Mapping):
        raise ValueError("packet requires reviewer_view")

    uncertainty_flags = _string_list(reviewer_view.get("uncertainty_flags"))
    decision_focus = _string_list(reviewer_view.get("decision_focus"))
    likely_decision = (
        _stringify(reviewer_view.get("recommended_next_step")).strip()
        or _stringify(split_review_context.get("suggested_action")).strip()
        or "review_only"
    )

    merged_split_axes = [
        axis for axis in split_review_context.get("merged_split_axes", [])
        if isinstance(axis, Mapping)
    ]
    reasons: list[str] = []
    status = _stringify(split_review_context.get("status")).strip()
    if status:
        reasons.append(f"split_status={status}")
    if bool(split_review_context.get("review_required")):
        reasons.append("split_plan_requires_review")
    if merged_split_axes:
        reasons.append(f"split_axes_detected={len(merged_split_axes)}")
    if uncertainty_flags:
        reasons.extend(f"uncertainty={flag}" for flag in uncertainty_flags)

    return {
        "schema_version": WIKIDATA_REVIEW_PACKET_REVIEWER_ACTIONS_SCHEMA_VERSION,
        "packet_id": _stringify(packet.get("packet_id")).strip(),
        "review_entity_qid": _stringify(packet.get("review_entity_qid")).strip(),
        "likely_decision": likely_decision,
        "smallest_next_check": _smallest_next_check(
            uncertainty_flags=uncertainty_flags,
            merged_split_axes=merged_split_axes,
        ),
        "why_this_row_is_in_review": reasons,
        "decision_focus": decision_focus,
        "uncertainty_flags": uncertainty_flags,
        "can_execute_edits": False,
        "non_claims": [
            "review aid only",
            "does not execute edits",
            "does not resolve uncertainty automatically",
        ],
    }


__all__ = [
    "WIKIDATA_REVIEW_PACKET_REVIEWER_ACTIONS_SCHEMA_VERSION",
    "build_wikidata_review_packet_reviewer_actions",
]
