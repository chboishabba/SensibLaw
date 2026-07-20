from __future__ import annotations

from typing import Any, Mapping

from .compiler_contract import normalize_compiler_contract


PRODUCT_GATE_SCHEMA_VERSION = "sl.product_gate.v0_1"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_product_gate(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    mapping = value if isinstance(value, Mapping) else {}
    evidence = mapping.get("evidence") if isinstance(mapping.get("evidence"), Mapping) else {}
    product_roles = [
        str(role).strip()
        for role in evidence.get("product_roles", [])
        if str(role).strip()
    ]
    return {
        "schema_version": str(mapping.get("schema_version") or PRODUCT_GATE_SCHEMA_VERSION),
        "lane": str(mapping.get("lane") or "").strip(),
        "product_ref": str(mapping.get("product_ref") or "").strip(),
        "decision": str(mapping.get("decision") or "").strip(),
        "reason": str(mapping.get("reason") or "").strip(),
        "evidence": {
            "promoted_count": max(0, _int(evidence.get("promoted_count"))),
            "review_count": max(0, _int(evidence.get("review_count"))),
            "abstained_count": max(0, _int(evidence.get("abstained_count"))),
            "product_roles": product_roles,
        },
    }


def build_product_gate(
    *,
    lane: str,
    product_ref: str,
    compiler_contract: Mapping[str, Any],
) -> dict[str, Any]:
    # Product gate decisions are promotion postures over compiled products.
    # They are intentionally separate from proposition-resolution states such as
    # "hold" and "abstain" in `proposition_resolution_policy.py`.
    normalized_contract = normalize_compiler_contract(compiler_contract)
    promoted = normalized_contract["promoted_outcomes"]
    derived_products = normalized_contract["derived_products"]
    promoted_count = _int(promoted.get("promoted_count"))
    review_count = _int(promoted.get("review_count"))
    abstained_count = _int(promoted.get("abstained_count"))
    product_roles = [
        str(row.get("role") or "").strip()
        for row in derived_products
        if isinstance(row, Mapping) and str(row.get("role") or "").strip()
    ]

    if promoted_count <= 0:
        # "abstain" here means the product gate declines promotion because no
        # promotable product outcome exists. It is not proposition-resolution
        # "abstain", and should not be read as the proposition-resolution
        # neutral state "hold".
        decision = "abstain"
        reason = "no_promoted_outcomes"
    elif review_count > 0 or abstained_count > 0:
        decision = "audit"
        reason = "mixed_promote_review_or_abstain_pressure"
    else:
        decision = "promote"
        reason = "promoted_outcomes_without_open_pressure"

    return normalize_product_gate({
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
    })
