from __future__ import annotations

from typing import Any, Mapping

from .compiler_contract import normalize_promoted_outcomes


PRODUCT_GATE_SCHEMA_VERSION = "sl.product_gate.v0_1"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_product_gate(
    *,
    lane: str,
    product_ref: str,
    compiler_contract: Mapping[str, Any],
) -> dict[str, Any]:
    promoted = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )
    derived_products = (
        compiler_contract.get("derived_products")
        if isinstance(compiler_contract.get("derived_products"), list)
        else []
    )
    promoted_count = _int(promoted.get("promoted_count"))
    review_count = _int(promoted.get("review_count"))
    abstained_count = _int(promoted.get("abstained_count"))
    product_roles = [
        str(row.get("role") or "").strip()
        for row in derived_products
        if isinstance(row, Mapping) and str(row.get("role") or "").strip()
    ]

    if promoted_count <= 0:
        decision = "abstain"
        reason = "no_promoted_outcomes"
    elif review_count > 0 or abstained_count > 0:
        decision = "audit"
        reason = "mixed_promote_review_or_abstain_pressure"
    else:
        decision = "promote"
        reason = "promoted_outcomes_without_open_pressure"

    return {
        "schema_version": PRODUCT_GATE_SCHEMA_VERSION,
        "lane": str(lane),
        "product_ref": str(product_ref),
        "decision": decision,
        "reason": reason,
        "evidence": {
            "promoted_count": promoted_count,
            "review_count": review_count,
            "abstained_count": abstained_count,
            "product_roles": product_roles,
        },
    }
