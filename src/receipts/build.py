"""Receipt building utilities."""

from __future__ import annotations

from typing import Any, Dict


def build_receipt(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a receipt from *data*.

    This placeholder implementation simply returns the input ``data`` unchanged.
    """
    return data


__all__ = ["build_receipt"]
