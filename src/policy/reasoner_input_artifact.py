from __future__ import annotations

from typing import Any, Mapping

from .compiler_contract import normalize_promoted_outcomes


REASONER_INPUT_ARTIFACT_SCHEMA_VERSION = "sl.reasoner_input.v0_1"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_reasoner_input_artifact(
    *,
    source_system: str,
    suite_normalized_artifact: Mapping[str, Any],
    compiler_contract: Mapping[str, Any],
    promotion_gate: Mapping[str, Any],
) -> dict[str, Any]:
    promoted_outcomes = normalize_promoted_outcomes(
        compiler_contract.get("promoted_outcomes")
        if isinstance(compiler_contract.get("promoted_outcomes"), Mapping)
        else None
    )

    return {
        "schema_version": REASONER_INPUT_ARTIFACT_SCHEMA_VERSION,
        "source_system": str(source_system),
        "source_lane": str(compiler_contract.get("lane") or ""),
        "source_artifact_ref": str(suite_normalized_artifact.get("artifact_id") or ""),
        "artifact_role": str(suite_normalized_artifact.get("artifact_role") or ""),
        "reasoner_scope": {
            "allowed_outputs": ["derived_product", "bounded_union_surface"],
            "forbidden_outputs": ["promoted_record", "compiled_state"],
            "allowed_operations": [
                "explanation",
                "comparison",
                "hypothesis",
                "follow_planning",
            ],
            "forbidden_operations": [
                "promotion",
                "canonical_write",
                "state_reduction",
            ],
        },
        "normalized_artifact": dict(suite_normalized_artifact),
        "compiler_contract": dict(compiler_contract),
        "promotion_gate": dict(promotion_gate),
        "summary": {
            "gate_decision": str(promotion_gate.get("decision") or ""),
            "gate_reason": str(promotion_gate.get("reason") or ""),
            "promoted_count": _int(promoted_outcomes.get("promoted_count")),
            "review_count": _int(promoted_outcomes.get("review_count")),
            "abstained_count": _int(promoted_outcomes.get("abstained_count")),
        },
    }
