from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

RECIPIENT_PROFILES = {"lawyer", "doctor", "advocate", "regulator"}
DEFAULT_HANDOFF_SHARE_WITH = ("lawyer", "doctor", "advocate", "regulator")
DEFAULT_PROTECTED_ALLOWED_RECIPIENT_PROFILES = ("lawyer", "regulator")


@dataclass(frozen=True)
class ProtectedDisclosureSettings:
    enabled: bool
    disclosure_level: str
    envelope_policy: str
    handling_notice: str
    allowed_recipient_profiles: tuple[str, ...]


def stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_payload(payload: object) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def created_at_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_profile(value: str) -> str:
    text = str(value or "").strip().casefold()
    if text not in RECIPIENT_PROFILES:
        raise ValueError(f"unsupported recipient_profile: {value}")
    return text


def normalize_profile_list(values: Sequence[Any], *, field_name: str, require_unique: bool = True) -> list[str]:
    out = [normalize_profile(str(value)) for value in values]
    if require_unique and len(set(out)) != len(out):
        raise ValueError(f"{field_name} must not contain duplicates")
    return out


def normalize_share_with(
    entry: Mapping[str, Any],
    *,
    default_share_with: Sequence[str] | None = None,
    field_name: str = "entry.share_with",
    require_unique: bool = False,
) -> list[str]:
    raw = entry.get("share_with")
    if not isinstance(raw, list) or not raw:
        return list(default_share_with) if default_share_with is not None else []
    return normalize_profile_list(raw, field_name=field_name, require_unique=require_unique)


def build_protected_disclosure_settings(
    handoff: Mapping[str, Any],
    *,
    require_enabled: bool,
    default_allowed_recipient_profiles: Sequence[str],
    default_disclosure_level: str,
    default_envelope_policy: str,
    default_handling_notice: str,
) -> ProtectedDisclosureSettings:
    raw = handoff.get("protected_disclosure")
    if not isinstance(raw, Mapping) or not bool(raw.get("enabled")):
        if require_enabled:
            raise ValueError("protected_disclosure.enabled=true is required for protected disclosure envelopes")
        return ProtectedDisclosureSettings(
            enabled=False,
            disclosure_level="none",
            envelope_policy="none",
            handling_notice="",
            allowed_recipient_profiles=(),
        )

    allowed_raw = raw.get("allowed_recipient_profiles")
    if isinstance(allowed_raw, list) and allowed_raw:
        allowed = tuple(
            normalize_profile_list(
                allowed_raw,
                field_name="protected_disclosure.allowed_recipient_profiles",
                require_unique=require_enabled,
            )
        )
    elif require_enabled:
        raise ValueError("protected_disclosure.allowed_recipient_profiles is required")
    else:
        allowed = tuple(default_allowed_recipient_profiles)

    return ProtectedDisclosureSettings(
        enabled=True,
        disclosure_level=str(raw.get("disclosure_level") or default_disclosure_level),
        envelope_policy=str(raw.get("envelope_policy") or default_envelope_policy),
        handling_notice=str(raw.get("handling_notice") or default_handling_notice),
        allowed_recipient_profiles=allowed,
    )
