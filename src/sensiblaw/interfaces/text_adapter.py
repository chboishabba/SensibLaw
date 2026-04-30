from __future__ import annotations

"""Supported cross-product access to SL-owned canonical text shaping helpers."""

from ._compat import install_src_package_aliases

install_src_package_aliases()

try:
    from src.reporting.text_unit_builders import build_canonical_conversation_text
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    raise

__all__ = ["build_canonical_conversation_text"]
