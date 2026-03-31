from __future__ import annotations

from src.fact_intake.disclosure_policy import (
    build_protected_disclosure_settings,
    normalize_profile,
    normalize_share_with,
    sha256_payload,
)


def test_normalize_profile_accepts_known_profiles() -> None:
    assert normalize_profile("Lawyer") == "lawyer"
    assert normalize_profile(" regulator ") == "regulator"


def test_normalize_share_with_uses_default_or_explicit_scope() -> None:
    default_scope = normalize_share_with({}, default_share_with=("lawyer", "doctor"))
    explicit_scope = normalize_share_with(
        {"share_with": ["lawyer", "regulator"]},
        default_share_with=("lawyer",),
        require_unique=True,
    )

    assert default_scope == ["lawyer", "doctor"]
    assert explicit_scope == ["lawyer", "regulator"]


def test_build_protected_disclosure_settings_normalizes_enabled_payload() -> None:
    settings = build_protected_disclosure_settings(
        {
            "protected_disclosure": {
                "enabled": True,
                "allowed_recipient_profiles": ["lawyer", "regulator"],
            }
        },
        require_enabled=True,
        default_allowed_recipient_profiles=(),
        default_disclosure_level="protected_disclosure_v1",
        default_envelope_policy="protected_disclosure_local_only_v1",
        default_handling_notice="notice",
    )

    assert settings.enabled is True
    assert settings.allowed_recipient_profiles == ("lawyer", "regulator")
    assert settings.envelope_policy == "protected_disclosure_local_only_v1"


def test_sha256_payload_is_stable_for_sorted_keys() -> None:
    left = sha256_payload({"b": 2, "a": 1})
    right = sha256_payload({"a": 1, "b": 2})

    assert left == right
