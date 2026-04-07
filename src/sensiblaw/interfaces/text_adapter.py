from __future__ import annotations

"""Supported cross-product access to SL-owned canonical text shaping helpers."""

try:
    from src.reporting.text_unit_builders import build_canonical_conversation_text
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from reporting.text_unit_builders import build_canonical_conversation_text

__all__ = ["build_canonical_conversation_text"]
