from __future__ import annotations

from typing import Dict, Mapping, Sequence


def compile_frame(
    node: Mapping[str, object],
    neighbors: Sequence[Mapping[str, object]],
    factors: Sequence[Mapping[str, object]],
) -> Dict[str, str]:
    """Build a deterministic textual summary for a node.

    Parameters
    ----------
    node:
        Mapping containing at least an ``id`` or ``label``.
    neighbors:
        Sequence of neighbor mappings. Each may include ``receipts`` listing
        associated receipt identifiers.
    factors:
        Sequence of factor mappings, potentially carrying ``receipts``.

    Returns
    -------
    dict with ``thesis``, ``summary`` and ``brief`` text.
    """

    if not neighbors:
        return {
            "thesis": "No neighbors to summarise.",
            "summary": "No receipts.",
            "brief": "No receipts.",
        }

    receipts: list[str] = []
    for neighbor in neighbors:
        receipts.extend(str(r) for r in neighbor.get("receipts", []))
    for factor in factors:
        receipts.extend(str(r) for r in factor.get("receipts", []))

    thesis = f"{node.get('label', 'node')} references {len(neighbors)} sources"
    receipts_str = ", ".join(receipts)
    summary = f"Receipts referenced: {receipts_str}"
    brief = f"Receipts: {receipts_str}"
    return {"thesis": thesis, "summary": summary, "brief": brief}
