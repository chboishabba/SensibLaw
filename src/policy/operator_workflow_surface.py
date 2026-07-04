from __future__ import annotations

from typing import Any, Mapping

from .compiler_contract import normalize_compiler_contract
from .product_gate import normalize_product_gate


OPERATOR_WORKFLOW_SURFACE_SCHEMA_VERSION = "sl.operator_workflow_surface.v0_1"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_operator_workflow_surface(
    *,
    compiler_contract: Mapping[str, Any] | None,
    promotion_gate: Mapping[str, Any] | None,
    workflow_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_contract = normalize_compiler_contract(compiler_contract)
    normalized_gate = normalize_product_gate(promotion_gate)
    workflow = workflow_summary if isinstance(workflow_summary, Mapping) else {}
    counts = workflow.get("counts") if isinstance(workflow.get("counts"), Mapping) else {}
    promoted_outcomes = normalized_contract.get("promoted_outcomes", {})
    evidence_bundle = normalized_contract.get("evidence_bundle", {})
    derived_products = normalized_contract.get("derived_products", [])

    return {
        "schema_version": OPERATOR_WORKFLOW_SURFACE_SCHEMA_VERSION,
        "lane": str(normalized_contract.get("lane") or normalized_gate.get("lane") or "").strip(),
        "stage": str(workflow.get("stage") or "").strip(),
        "title": str(workflow.get("title") or "").strip(),
        "recommended_view": str(workflow.get("recommended_view") or "").strip(),
        "recommended_filter": workflow.get("recommended_filter"),
        "focus_fact_id": workflow.get("focus_fact_id"),
        "reason": str(workflow.get("reason") or "").strip(),
        "counts": {str(key): _int(value) for key, value in counts.items()},
        "compiler_contract": normalized_contract,
        "promotion_gate": normalized_gate,
        "summary": {
            "gate_decision": str(normalized_gate.get("decision") or "").strip(),
            "gate_reason": str(normalized_gate.get("reason") or "").strip(),
            "product_ref": str(normalized_gate.get("product_ref") or "").strip(),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": _int(promoted_outcomes.get("review_count")),
            "abstained_count": _int(promoted_outcomes.get("abstained_count")),
            "derived_product_roles": [
                str(row.get("role") or "").strip()
                for row in derived_products
                if isinstance(row, Mapping) and str(row.get("role") or "").strip()
            ],
            "evidence_bundle_kind": str(evidence_bundle.get("bundle_kind") or "").strip(),
            "evidence_source_family": str(evidence_bundle.get("source_family") or "").strip(),
            "evidence_item_count": _int(evidence_bundle.get("item_count")),
        },
    }


__all__ = [
    "OPERATOR_WORKFLOW_SURFACE_SCHEMA_VERSION",
    "build_operator_workflow_surface",
]
