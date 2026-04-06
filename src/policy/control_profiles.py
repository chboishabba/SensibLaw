from __future__ import annotations

from typing import Any, Mapping


CONTROL_PROFILE_SCHEMA_VERSION = "sl.control_profile.v0_1"

ISO_TRACEABILITY_MIN_PROFILE = {
    "schema_version": CONTROL_PROFILE_SCHEMA_VERSION,
    "profile_id": "iso_traceability_min",
    "title": "ISO traceability minimum",
    "source_standards": ["ISO 9001", "ISO 42001", "ISO 27001", "NIST AI RMF"],
    "control_groups": [
        {
            "control_group_id": "workflow_traceability",
            "title": "Workflow traceability",
            "member_clause_ids": [
                "provenance_traceability",
                "follow_pressure_visibility",
            ],
        },
        {
            "control_group_id": "semantic_grounding",
            "title": "Semantic grounding",
            "member_clause_ids": ["semantic_grounding"],
        },
        {
            "control_group_id": "execution_traceability",
            "title": "Execution traceability",
            "member_clause_ids": ["casey_execution_traceability"],
        },
    ],
}

_PROFILES = {
    ISO_TRACEABILITY_MIN_PROFILE["profile_id"]: ISO_TRACEABILITY_MIN_PROFILE,
}


def get_control_profile(profile_id: str) -> dict[str, Any]:
    profile = _PROFILES.get(str(profile_id or "").strip())
    if profile is None:
        raise KeyError(f"unsupported control profile: {profile_id}")
    return {
        "schema_version": profile["schema_version"],
        "profile_id": profile["profile_id"],
        "title": profile["title"],
        "source_standards": list(profile["source_standards"]),
        "control_groups": [dict(group) for group in profile["control_groups"]],
    }


def list_control_profiles() -> list[dict[str, Any]]:
    return [get_control_profile(profile_id) for profile_id in sorted(_PROFILES)]


def normalize_control_profile(profile: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(profile, str):
        return get_control_profile(profile)
    profile_id = str(profile.get("profile_id") or "").strip()
    if profile_id:
        base = get_control_profile(profile_id)
        if isinstance(profile.get("control_groups"), list):
            base["control_groups"] = [
                dict(group) for group in profile["control_groups"] if isinstance(group, Mapping)
            ]
        return base
    raise KeyError("control profile requires profile_id")


__all__ = [
    "CONTROL_PROFILE_SCHEMA_VERSION",
    "ISO_TRACEABILITY_MIN_PROFILE",
    "get_control_profile",
    "list_control_profiles",
    "normalize_control_profile",
]
