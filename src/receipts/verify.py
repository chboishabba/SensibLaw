"""Receipt verification helpers."""

from __future__ import annotations

from typing import Any, Dict


def verify_receipt(receipt: Dict[str, Any]) -> bool:
    """Verify a receipt.

    The current implementation always returns ``True``.
    """
    return True


__all__ = ["verify_receipt"]
