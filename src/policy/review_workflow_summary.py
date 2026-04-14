from __future__ import annotations

from typing import Any, Mapping, Sequence


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_counts(counts: Mapping[str, Any]) -> dict[str, int]:
    return {str(key): _int(value) for key, value in counts.items()}


def _rule_triggered(rule: Mapping[str, Any], counts: Mapping[str, int]) -> bool:
    count_keys = rule.get("count_keys")
    keys: list[str] = []
    if isinstance(count_keys, Sequence) and not isinstance(count_keys, (str, bytes)):
        keys.extend(str(value).strip() for value in count_keys if str(value).strip())
    count_key = str(rule.get("count_key") or "").strip()
    if count_key:
        keys.append(count_key)
    keys = [key for key in keys if key]
    if not keys:
        return False
    threshold = _int(rule.get("threshold"))
    if threshold <= 0:
        threshold = 1
    return any(_int(counts.get(key)) >= threshold for key in keys)


def _format_reason(template: Any, counts: Mapping[str, int]) -> str:
    text = str(template or "").strip()
    if not text:
        return ""
    try:
        return text.format(**counts)
    except Exception:
        return text


def build_count_priority_workflow_summary(
    *,
    counts: Mapping[str, Any],
    promotion_gate: Mapping[str, Any] | None,
    rules: Sequence[Mapping[str, Any]],
    default_step: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_counts = _normalize_counts(counts)
    shared = {
        "counts": normalized_counts,
        "promotion_gate": dict(promotion_gate or {}),
    }

    for rule in rules:
        if not isinstance(rule, Mapping) or not _rule_triggered(rule, normalized_counts):
            continue
        payload = {
            "stage": str(rule.get("stage") or "").strip(),
            "title": str(rule.get("title") or "").strip(),
            "recommended_view": str(rule.get("recommended_view") or "").strip(),
            "reason": _format_reason(rule.get("reason_template"), normalized_counts),
            **shared,
        }
        for key in ("recommended_filter", "focus_fact_id"):
            if key in rule:
                payload[key] = rule.get(key)
        return payload

    payload = {
        "stage": str(default_step.get("stage") or "").strip(),
        "title": str(default_step.get("title") or "").strip(),
        "recommended_view": str(default_step.get("recommended_view") or "").strip(),
        "reason": _format_reason(default_step.get("reason_template"), normalized_counts),
        **shared,
    }
    for key in ("recommended_filter", "focus_fact_id"):
        if key in default_step:
            payload[key] = default_step.get(key)
    return payload


__all__ = ["build_count_priority_workflow_summary"]
