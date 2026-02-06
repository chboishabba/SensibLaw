from __future__ import annotations

from typing import Any, Mapping

# Language guard: we never emit causal/advisory phrasing for context overlays.
BANNED_CAUSAL_TERMS = {"caused", "influenced", "impacted", "due to", "led to"}


def render_context_summary(context_type: str, payload: Mapping[str, Any] | None = None) -> str:
    """
    Render a neutral, non-causal one-liner for a context field.

    This is intentionally minimal; it is a safe default for UI or logging when
    a context overlay is present. It must not imply behaviour, advice, or
    causality.
    """
    payload = payload or {}
    label = context_type.replace("_", " ").strip()
    if payload:
        keys = ", ".join(sorted(payload.keys()))
        return f"Context: {label} observed (fields: {keys}); no interpretation."
    return f"Context: {label} observed; no interpretation."


__all__ = ["render_context_summary", "BANNED_CAUSAL_TERMS"]
