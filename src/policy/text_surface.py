from __future__ import annotations

from typing import Any, Mapping

from src.text.shared_text_normalization import (
    split_semicolon_clauses,
    split_text_clauses,
    split_text_segments,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)


TEXT_SURFACE_SCHEMA_VERSION = "sl.text_surface.v0_1"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def build_text_surface(
    *,
    text: Any,
    text_role: Any,
    source_kind: Any,
    anchor_refs: Mapping[str, Any] | None = None,
    text_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    rendered = _clean_text(text)
    role = _clean_text(text_role)
    source = _clean_text(source_kind)
    if not rendered or not role or not source:
        return None

    payload: dict[str, Any] = {
        "text": rendered,
        "text_role": role,
        "source_kind": source,
    }
    clean_anchor_refs = _clean_mapping(anchor_refs)
    if clean_anchor_refs:
        payload["anchor_refs"] = clean_anchor_refs
    clean_text_ref = _clean_mapping(text_ref)
    if clean_text_ref:
        payload["text_ref"] = clean_text_ref
    return payload


__all__ = [
    "TEXT_SURFACE_SCHEMA_VERSION",
    "build_text_surface",
    "split_semicolon_clauses",
    "split_text_clauses",
    "split_text_segments",
    "strip_enumeration_prefix",
    "tokenize_canonical_text",
]
