from __future__ import annotations

from typing import Any, Mapping


CONTROL_PROFILE_SCHEMA_VERSION = "sl.control_profile.v0_1"
GOV1_PROFILE_ID = "itir_gov1_integrated"

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

_GOV1_GROUPS = [
    ("authority_provenance", "Authority and provenance", ["ISO 9001", "ISO/IEC 42001"]),
    ("requirements_acceptance", "Requirements and acceptance", ["ISO 9001", "Six Sigma"]),
    ("ai_lifecycle", "AI intended use and lifecycle", ["ISO/IEC 42001"]),
    ("ai_risk", "AI risk", ["ISO/IEC 23894", "NIST AI RMF"]),
    ("information_security", "Information security", ["ISO/IEC 27001"]),
    ("privacy_information_management", "Privacy information management", ["ISO/IEC 27701"]),
    ("access_scope", "Access and scope", ["ISO/IEC 27001", "ISO/IEC 27701"]),
    ("human_oversight", "Human oversight", ["ISO/IEC 42001", "NIST AI RMF"]),
    ("uncertainty_non_promotion", "Uncertainty and non-promotion", ["ISO/IEC 42001", "ISO/IEC 23894", "NIST AI RMF"]),
    ("service_change_release_incident", "Service/change/release/incident/problem", ["ITIL"]),
    ("capa_defect_reduction", "CAPA and defect reduction", ["ISO 9001", "Six Sigma"]),
    ("usability_hcd_accessibility", "Usability, HCD, UI semantics and accessibility", ["ISO 9241-110", "ISO 9241-161", "ISO 9241-210", "ISO 9241-171", "ISO 24552", "ISO 24505-1", "ISO 24505-2", "ISO 22727"]),
    ("architecture_traceability", "Architecture traceability", ["C4", "PlantUML"]),
]

GOV1_INTEGRATED_PROFILE = {
    "schema_version": CONTROL_PROFILE_SCHEMA_VERSION,
    "profile_id": GOV1_PROFILE_ID,
    "title": "ITIR GOV-1 integrated control case",
    "source_standards": sorted({standard for _, _, standards in _GOV1_GROUPS for standard in standards}),
    "control_groups": [
        {
            "control_group_id": group_id,
            "title": title,
            "source_standards": list(standards),
            "member_clause_ids": [f"gov1_{group_id}"],
        }
        for group_id, title, standards in _GOV1_GROUPS
    ],
}

_PROFILES = {
    ISO_TRACEABILITY_MIN_PROFILE["profile_id"]: ISO_TRACEABILITY_MIN_PROFILE,
    GOV1_INTEGRATED_PROFILE["profile_id"]: GOV1_INTEGRATED_PROFILE,
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
                dict(group)
                for group in profile["control_groups"]
                if isinstance(group, Mapping)
            ]
        return base
    raise KeyError("control profile requires profile_id")


__all__ = [
    "CONTROL_PROFILE_SCHEMA_VERSION",
    "GOV1_PROFILE_ID",
    "ISO_TRACEABILITY_MIN_PROFILE",
    "GOV1_INTEGRATED_PROFILE",
    "get_control_profile",
    "list_control_profiles",
    "normalize_control_profile",
]
