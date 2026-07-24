"""Compatibility projection from lawful legal Domain IR to LegalIRObservation.

The old Legal IR carrier remains stable for consumers, but its inputs now come
from resolved, receipted Domain IR rather than directly from reduced factors.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.pnf.legal_adjunct import LegalIRObservation
from src.policy.carriers.canonical import canonical_sha256

LEGAL_IR_DOMAIN_BRIDGE_CONTRACT = "legal-ir-domain-bridge:v0_1"


def project_legal_ir_from_domain_ir(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[LegalIRObservation, ...]:
    projected: dict[str, LegalIRObservation] = {}
    for row in rows:
        if str(row.get("domain") or "") != "legal":
            continue
        domain_ir_ref = str(row.get("domain_ir_ref") or "")
        source_factor_ref = str(row.get("source_factor_ref") or "")
        resolution_ref = str(row.get("source_resolution_ref") or "")
        signature_ref = str(row.get("structural_signature_ref") or "")
        projection_receipt_ref = str(row.get("projection_receipt_ref") or "")
        loss_ref = str(row.get("loss_ref") or "")
        payload = row.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue
        if not all(
            (
                domain_ir_ref,
                source_factor_ref,
                resolution_ref,
                signature_ref,
                projection_receipt_ref,
                loss_ref,
            )
        ):
            continue
        identity = {
            "contract": LEGAL_IR_DOMAIN_BRIDGE_CONTRACT,
            "domain_ir_ref": domain_ir_ref,
            "projection_receipt_ref": projection_receipt_ref,
        }
        observation_ref = "legal-ir-observation:" + canonical_sha256(identity)
        projected[observation_ref] = LegalIRObservation(
            observation_ref=observation_ref,
            pnf_factor_ref=source_factor_ref,
            pnf_revision_ref=resolution_ref,
            structural_signature_ref=signature_ref,
            predicate_ref=str(payload.get("predicate_ref") or ""),
            role_bindings=dict(payload.get("role_bindings") or {}),
            qualifier_state=dict(payload.get("qualifier_state") or {}),
            wrapper_state={
                "domain_ir_ref": domain_ir_ref,
                "projection_receipt_ref": projection_receipt_ref,
                "projection_loss_ref": loss_ref,
                "validation_state": str(
                    row.get("validation_state") or "operational_candidate"
                ),
                "authority": "resolved_domain_ir_projection",
                "applicability_closed": False,
                "legal_truth_closed": False,
            },
            provenance_refs=tuple(
                sorted(str(value) for value in row.get("provenance_refs") or ())
            ),
            residual_refs=tuple(
                sorted(str(value) for value in row.get("residual_refs") or ())
            ),
            projection_state="resolved_domain_projection",
        )
    return tuple(sorted(projected.values(), key=lambda row: row.observation_ref))


__all__ = [
    "LEGAL_IR_DOMAIN_BRIDGE_CONTRACT",
    "project_legal_ir_from_domain_ir",
]
