from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


ProfileName = str


@dataclass(frozen=True)
class LintIssue:
    severity: str
    code: str
    message: str
    path: str


PROFILE_RULES: dict[ProfileName, dict[str, set[str]]] = {
    "sl_profile": {
        "allowed_groups": {"statute_ref", "case_ref", "principle_ref", "actor_role"},
        "allowed_axes": {"jurisdiction", "authority_level", "modality"},
        "allowed_overlays": {"citation", "holding", "norm_constraint", "actor_role"},
    },
    "sb_profile": {
        "allowed_groups": {"task_ref", "actor_role", "state_transition", "evidence_ref"},
        "allowed_axes": {"state_phase", "adapter_source", "confidence_tier"},
        "allowed_overlays": {"activity_label", "transition_label", "evidence_link", "receipt"},
    },
    "infra_profile": {
        "allowed_groups": {"system_component", "service_ref", "pipeline_step", "signal_ref"},
        "allowed_axes": {"deployment_scope", "hosting", "severity"},
        "allowed_overlays": {"ops_label", "incident_marker", "metric_annotation"},
    },
}


def _spans(value: Any) -> list[dict[str, Any]]:
    spans = value.get("spans", []) if isinstance(value, dict) else []
    return spans if isinstance(spans, list) else []


def lint_payload(payload: dict[str, Any]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    source_text = str(payload.get("source_text", ""))
    max_len = len(source_text)

    for collection in ("groups", "axes", "overlays"):
        rows = payload.get(collection, [])
        if not isinstance(rows, list):
            issues.append(
                LintIssue("error", "invalid_collection", f"{collection} must be a list", collection)
            )
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append(
                    LintIssue(
                        "error",
                        "invalid_item",
                        f"{collection}[{idx}] must be an object",
                        f"{collection}[{idx}]",
                    )
                )
                continue
            spans = _spans(row)
            if not spans:
                issues.append(
                    LintIssue(
                        "error",
                        "empty_spans",
                        f"{collection}[{idx}] has no spans",
                        f"{collection}[{idx}].spans",
                    )
                )
                continue
            for sidx, span in enumerate(spans):
                start = int(span.get("start", -1))
                end = int(span.get("end", -1))
                if start < 0 or end <= start or end > max_len:
                    issues.append(
                        LintIssue(
                            "error",
                            "span_oob",
                            f"{collection}[{idx}] span out of bounds",
                            f"{collection}[{idx}].spans[{sidx}]",
                        )
                    )
    return issues


def apply_profile_admissibility(
    payload: dict[str, Any], profile: ProfileName
) -> tuple[dict[str, Any], list[LintIssue]]:
    if profile not in PROFILE_RULES:
        raise ValueError(f"Unknown profile: {profile}")

    rules = PROFILE_RULES[profile]
    issues = lint_payload(payload)
    result = deepcopy(payload)

    groups = result.get("groups", [])
    axes = result.get("axes", [])
    overlays = result.get("overlays", [])

    kept_groups: list[dict[str, Any]] = []
    for idx, row in enumerate(groups if isinstance(groups, list) else []):
        gid = str(row.get("group_id", ""))
        if gid in rules["allowed_groups"]:
            kept_groups.append(row)
        else:
            issues.append(
                LintIssue(
                    "error",
                    "forbidden_group",
                    f"group_id '{gid}' not allowed for {profile}",
                    f"groups[{idx}]",
                )
            )

    kept_axes: list[dict[str, Any]] = []
    for idx, row in enumerate(axes if isinstance(axes, list) else []):
        aid = str(row.get("axis_id", ""))
        if aid in rules["allowed_axes"]:
            kept_axes.append(row)
        else:
            issues.append(
                LintIssue(
                    "error",
                    "forbidden_axis",
                    f"axis_id '{aid}' not allowed for {profile}",
                    f"axes[{idx}]",
                )
            )

    kept_overlays: list[dict[str, Any]] = []
    for idx, row in enumerate(overlays if isinstance(overlays, list) else []):
        oid = str(row.get("overlay_id", ""))
        if oid in rules["allowed_overlays"]:
            kept_overlays.append(row)
        else:
            issues.append(
                LintIssue(
                    "error",
                    "forbidden_overlay",
                    f"overlay_id '{oid}' not allowed for {profile}",
                    f"overlays[{idx}]",
                )
            )

    result["groups"] = kept_groups
    result["axes"] = kept_axes
    result["overlays"] = kept_overlays
    return result, issues

