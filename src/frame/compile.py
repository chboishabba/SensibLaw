"""Deterministic, fail-closed compilation of evidenced action frames."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"frame missing {field}")
    return value.strip()


def _receipts(items: Sequence[Mapping[str, object]], kind: str) -> list[str]:
    found: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"frame invalid {kind}[{index}]")
        raw = item.get("receipts", ())
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
            raise ValueError(f"frame invalid {kind}[{index}].receipts")
        for value in raw:
            found.append(_required_text(value, "receipt"))
    return found


def compile_frame(
    node: Mapping[str, object],
    neighbors: Sequence[Mapping[str, object]],
    factors: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    """Compile only frames with explicit thesis, evidence receipts, and action.

    Raise ValueError on missing or malformed required fields. Never synthesize
    evidence or decisions from a label or the number of neighbors.
    """
    if not isinstance(node, Mapping):
        raise ValueError("frame invalid node")
    thesis = _required_text(node.get("thesis"), "thesis")
    action = _required_text(node.get("action"), "action")
    receipts = _receipts(neighbors, "neighbors") + _receipts(factors, "factors")
    if not receipts:
        raise ValueError("frame missing receipt")
    joined = ", ".join(receipts)
    return {
        "thesis": thesis,
        "summary": f"Receipts referenced: {joined}",
        "brief": f"Receipts: {joined}",
        "action": action,
    }
