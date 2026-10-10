from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_source_support_verification import (
    admit_source_support,
    build_source_verification_receipt,
)
from src.policy.carriers.canonical import canonical_sha256


SOURCE_ADJUDICATION_SCHEMA_VERSION = "sl.nat_source_adjudication.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def compile_reviewed_source_decisions(
    verification_plan: Mapping[str, Any],
    decision_sidecar: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile explicit reviewed proposition decisions to exact support admissions.

    This function performs no semantic interpretation itself.  The sidecar must name
    an exact ready demand, acquired artifact receipt, verifier, disposition and (for
    supported/contradicted) evidence locator.  The existing verification compiler
    then rechecks proposition/artifact identity before any source-support payment.
    """

    demands = {
        _text(demand.get("demand_ref")): demand
        for demand in _sequence(verification_plan.get("demands"))
        if isinstance(demand, Mapping) and _text(demand.get("demand_ref"))
    }
    decisions = [
        item
        for item in _sequence(decision_sidecar.get("decisions"))
        if isinstance(item, Mapping)
    ]
    decisions.sort(key=lambda item: _text(item.get("source_verification_demand_ref")))

    seen: set[str] = set()
    receipts: list[dict[str, Any]] = []
    admissions: list[dict[str, Any]] = []
    for decision in decisions:
        demand_ref = _text(decision.get("source_verification_demand_ref"))
        if not demand_ref:
            raise ValueError("review decision requires source_verification_demand_ref")
        if demand_ref in seen:
            raise ValueError(f"duplicate review decision for demand: {demand_ref}")
        seen.add(demand_ref)
        demand = demands.get(demand_ref)
        if demand is None:
            raise ValueError(f"review decision references unknown demand: {demand_ref}")
        if _text(demand.get("state")) != "ready":
            raise ValueError(f"review decision cannot bypass blocked demand: {demand_ref}")

        verifier_reference = _text(decision.get("verifier_reference"))
        artifact_ref = _text(decision.get("source_artifact_receipt_ref"))
        disposition = _text(decision.get("disposition"))
        evidence_locator = _text(decision.get("evidence_locator"))
        if not verifier_reference:
            raise ValueError("review decision requires verifier_reference")
        if not artifact_ref:
            raise ValueError("review decision requires source_artifact_receipt_ref")

        receipt = build_source_verification_receipt(
            demand,
            disposition=disposition,
            verifier_reference=verifier_reference,
            source_artifact_receipt_ref=artifact_ref,
            evidence_locator=evidence_locator,
            verification_note=_text(decision.get("verification_note")),
        )
        admission = admit_source_support(demand, receipt)
        receipts.append(receipt)
        admissions.append(admission)

    receipts.sort(key=lambda item: _text(item.get("receipt_ref")))
    admissions.sort(key=lambda item: _text(item.get("admission_ref")))
    dispositions = Counter(_text(item.get("disposition")) for item in receipts)
    decided_refs = {
        _text(item.get("source_verification_demand_ref")) for item in receipts
    }
    ready_refs = {
        ref for ref, demand in demands.items() if _text(demand.get("state")) == "ready"
    }
    blocked_count = sum(
        1 for demand in demands.values() if _text(demand.get("state")) != "ready"
    )

    payload_without_ref = {
        "schema_version": SOURCE_ADJUDICATION_SCHEMA_VERSION,
        "source_verification_plan_ref": _text(verification_plan.get("plan_ref")),
        "decision_sidecar_ref": _text(decision_sidecar.get("sidecar_ref")),
        "verification_demand_count": len(demands),
        "ready_demand_count": len(ready_refs),
        "blocked_demand_count": blocked_count,
        "reviewed_decision_count": len(receipts),
        "unreviewed_ready_count": len(ready_refs - decided_refs),
        "counts_by_disposition": dict(sorted(dispositions.items())),
        "verification_receipts": receipts,
        "source_support_admissions": admissions,
        "source_support_paid_count": sum(
            1 for item in admissions if bool(item.get("source_support_paid"))
        ),
        "source_support_rejected_count": sum(
            1 for item in admissions if bool(item.get("source_support_rejected"))
        ),
        "source_support_open_reviewed_count": sum(
            1 for item in admissions if item.get("source_support_state") == "open"
        ),
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
        "migration_authority": False,
    }
    payload = dict(payload_without_ref)
    payload["adjudication_ref"] = "nat-source-adjudication:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "SOURCE_ADJUDICATION_SCHEMA_VERSION",
    "compile_reviewed_source_decisions",
]
