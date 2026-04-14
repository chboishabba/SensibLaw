from __future__ import annotations

from typing import Any, Mapping, Sequence


CAMPAIGN_PLAN_SCHEMA_VERSION = "sl.wikidata_nat.live_follow_campaign_plan.v0_1"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [text for item in value if (text := _stringify(item).strip())]


def _target_ref(target: Mapping[str, Any]) -> str:
    for key in ("packet_id", "row_id", "statement_id", "candidate_id", "qid"):
        text = _stringify(target.get(key)).strip()
        if text:
            return text
    return "unknown_target"


def _target_kind(target: Mapping[str, Any]) -> str:
    if _stringify(target.get("packet_id")).strip():
        return "packet"
    if _stringify(target.get("statement_id")).strip():
        return "statement"
    if _stringify(target.get("candidate_id")).strip():
        return "candidate"
    if _stringify(target.get("row_id")).strip():
        return "row"
    return "qid"


def build_wikidata_nat_live_follow_campaign_plan(
    campaign: Mapping[str, Any],
) -> dict[str, Any]:
    categories = campaign.get("categories")
    if not isinstance(categories, list):
        raise ValueError("campaign requires categories")

    plan_rows: list[dict[str, Any]] = []
    source_class_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for category in categories:
        if not isinstance(category, Mapping):
            continue
        category_id = _stringify(category.get("category_id")).strip()
        if not category_id:
            continue
        targets = category.get("targets")
        if not isinstance(targets, list):
            continue
        preferred_source_order = _string_list(category.get("preferred_source_order"))
        if not preferred_source_order:
            continue
        first_source_class = preferred_source_order[0]
        max_hops = int(category.get("max_hops") or 0)
        stop_condition = _stringify(category.get("stop_condition")).strip()
        uncertainty_kind = _stringify(category.get("uncertainty_kind")).strip()
        category_counts[category_id] = category_counts.get(category_id, 0) + len(targets)
        source_class_counts[first_source_class] = (
            source_class_counts.get(first_source_class, 0) + len(targets)
        )
        for index, target in enumerate(targets, start=1):
            if not isinstance(target, Mapping):
                continue
            qid = _stringify(target.get("qid")).strip()
            target_ref = _target_ref(target)
            plan_rows.append(
                {
                    "plan_id": f"{category_id}:{index}",
                    "category_id": category_id,
                    "uncertainty_kind": uncertainty_kind,
                    "target_kind": _target_kind(target),
                    "target_ref": target_ref,
                    "qid": qid or None,
                    "preferred_source_class": first_source_class,
                    "source_order": preferred_source_order,
                    "max_hops": max_hops,
                    "stop_condition": stop_condition,
                    "trigger": f"live_follow:{category_id}:{target_ref}",
                    "execution_mode": "bounded_live_follow",
                    "local_first": True,
                }
            )

    plan_rows.sort(key=lambda row: (row["category_id"], row["target_ref"]))
    return {
        "schema_version": CAMPAIGN_PLAN_SCHEMA_VERSION,
        "campaign_id": _stringify(campaign.get("campaign_id")).strip(),
        "lane_id": _stringify(campaign.get("lane_id")).strip(),
        "campaign_rule": _stringify(campaign.get("campaign_rule")).strip(),
        "plan_count": len(plan_rows),
        "category_counts": category_counts,
        "preferred_source_class_counts": source_class_counts,
        "plan_rows": plan_rows,
    }


__all__ = [
    "CAMPAIGN_PLAN_SCHEMA_VERSION",
    "build_wikidata_nat_live_follow_campaign_plan",
]
