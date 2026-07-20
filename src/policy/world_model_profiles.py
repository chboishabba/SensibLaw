from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

WORLD_MODEL_PROFILE_SCHEMA_VERSION = "sl.world_model_profile.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    seen: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in seen:
            seen.append(text)
    return seen


def build_profile(
    *,
    profile_id: str,
    lane_family: str,
    source_kinds: Sequence[str] = (),
    authority_surfaces: Sequence[str] = (),
    external_bridges: Sequence[str] = (),
    promotion_policy: str = "candidate_only",
    default_projection_kinds: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": WORLD_MODEL_PROFILE_SCHEMA_VERSION,
        "profile_id": _text(profile_id),
        "lane_family": _text(lane_family),
        "source_kinds": _string_list(source_kinds),
        "authority_surfaces": _string_list(authority_surfaces),
        "external_bridges": _string_list(external_bridges),
        "promotion_policy": _text(promotion_policy) or "candidate_only",
        "default_projection_kinds": _string_list(default_projection_kinds),
        "metadata": deepcopy(dict(metadata or {})),
    }


def normalize_profile(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = profile if isinstance(profile, Mapping) else {}
    return build_profile(
        profile_id=_text(payload.get("profile_id")) or _text(payload.get("lane_family")),
        lane_family=_text(payload.get("lane_family")) or _text(payload.get("profile_id")),
        source_kinds=payload.get("source_kinds", []),
        authority_surfaces=payload.get("authority_surfaces", []),
        external_bridges=payload.get("external_bridges", []),
        promotion_policy=_text(payload.get("promotion_policy")) or "candidate_only",
        default_projection_kinds=payload.get("default_projection_kinds", []),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None,
    )


__all__ = [
    "WORLD_MODEL_PROFILE_SCHEMA_VERSION",
    "build_profile",
    "normalize_profile",
]
