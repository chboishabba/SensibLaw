"""Validation helpers shared by immutable policy carriers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .canonical import require_text


def require_schema(carrier: Mapping[str, Any], expected: str) -> None:
    actual = require_text(carrier.get("schema_version"), "schema_version")
    if actual != expected:
        raise ValueError(f"expected schema {expected}, got {actual}")


def require_authority(carrier: Mapping[str, Any], expected: str) -> None:
    actual = require_text(carrier.get("authority"), "authority")
    if actual != expected:
        raise ValueError(f"expected authority {expected}, got {actual}")
