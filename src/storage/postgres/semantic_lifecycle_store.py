"""Batched persistence for the explicit PNF semantic lifecycle."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(row for row in value if isinstance(row, Mapping))


def persist_semantic_lifecycle_artifacts(
    cursor: Any,
    *,
    document_ref: str,
    artifacts: Mapping[str, Any],
) -> dict[str, int]:
    """Persist lifecycle parents before projection and execution children."""

    lifecycle = artifacts.get("semantic_lifecycle") or {}
    domain_build = artifacts.get("domain_ir_build") or {}
    assessments = _rows(
        lifecycle.get("candidate_assessments")
        if isinstance(lifecycle, Mapping)
        else ()
    )
    admissions = _rows(
        lifecycle.get("admissibility_receipts")
        if isinstance(lifecycle, Mapping)
        else ()
    )
    resolutions = _rows(
        lifecycle.get("resolution_receipts")
        if isinstance(lifecycle, Mapping)
        else ()
    )
    contracts = _rows(
        domain_build.get("contracts") if isinstance(domain_build, Mapping) else ()
    )
    demands = _rows(
        domain_build.get("demands") if isinstance(domain_build, Mapping) else ()
    )
    losses = _rows(
        domain_build.get("losses") if isinstance(domain_build, Mapping) else ()
    )
    projection_receipts = _rows(
        domain_build.get("receipts") if isinstance(domain_build, Mapping) else ()
    )
    projections = _rows(
        domain_build.get("projections") if isinstance(domain_build, Mapping) else ()
    )
    executions = _rows(artifacts.get("ir_execution_receipts") or ())

    if assessments:
        cursor.executemany(
            """
            INSERT INTO pnf_candidate_assessment
                (assessment_ref, document_ref, proposal_ref,
                 semantic_coordinate_ref, outcome, coverage_complete,
                 applicable, payload, assessment_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (assessment_ref) DO NOTHING
            """,
            [
                (
                    row["assessment_ref"],
                    document_ref,
                    row["proposal_ref"],
                    row["semantic_coordinate_ref"],
                    row["outcome"],
                    bool(row.get("coverage_complete")),
                    bool(row.get("applicable", True)),
                    _json(row),
                    _sha(row),
                )
                for row in assessments
            ],
        )
    if admissions:
        cursor.executemany(
            """
            INSERT INTO pnf_admissibility_receipt
                (receipt_ref, document_ref, proposal_ref, assessment_ref,
                 state, authority_ceiling, payload, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            [
                (
                    row["receipt_ref"],
                    document_ref,
                    row["proposal_ref"],
                    row["assessment_ref"],
                    row["state"],
                    row["authority_ceiling"],
                    _json(row),
                    _sha(row),
                )
                for row in admissions
            ],
        )
    if resolutions:
        cursor.executemany(
            """
            INSERT INTO pnf_resolution_receipt
                (resolution_ref, document_ref, fibre_summary_ref,
                 semantic_coordinate_ref, state, selected_proposal_ref,
                 selector_ref, payload, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (resolution_ref) DO NOTHING
            """,
            [
                (
                    row["resolution_ref"],
                    document_ref,
                    row["fibre_summary_ref"],
                    row["semantic_coordinate_ref"],
                    row["state"],
                    row.get("selected_proposal_ref"),
                    row["selector_ref"],
                    _json(row),
                    _sha(row),
                )
                for row in resolutions
            ],
        )
    if contracts:
        cursor.executemany(
            """
            INSERT INTO pnf_domain_ir_projection_contract
                (contract_ref, domain, authority_ceiling, residual_policy,
                 payload, contract_sha256)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (contract_ref) DO NOTHING
            """,
            [
                (
                    row["contract_ref"],
                    row["domain"],
                    row["authority_ceiling"],
                    row["residual_policy"],
                    _json(row),
                    _sha(row),
                )
                for row in contracts
            ],
        )
    if demands:
        cursor.executemany(
            """
            INSERT INTO pnf_projection_demand
                (demand_ref, document_ref, domain, resolution_ref,
                 source_factor_ref, structural_signature_ref, demand_kind,
                 priority, payload, demand_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (demand_ref) DO NOTHING
            """,
            [
                (
                    row["demand_ref"],
                    document_ref,
                    row["domain"],
                    row["resolution_ref"],
                    row["source_factor_ref"],
                    row["structural_signature_ref"],
                    row["demand_kind"],
                    int(row.get("priority") or 50),
                    _json(row),
                    _sha(row),
                )
                for row in demands
            ],
        )
    if losses:
        cursor.executemany(
            """
            INSERT INTO pnf_projection_loss_receipt
                (loss_ref, document_ref, domain, source_resolution_ref,
                 projection_contract_ref, payload, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (loss_ref) DO NOTHING
            """,
            [
                (
                    row["loss_ref"],
                    document_ref,
                    row["domain"],
                    row["source_resolution_ref"],
                    row["projection_contract_ref"],
                    _json(row),
                    _sha(row),
                )
                for row in losses
            ],
        )
    if projection_receipts:
        cursor.executemany(
            """
            INSERT INTO pnf_domain_ir_projection_receipt
                (receipt_ref, document_ref, domain, source_resolution_ref,
                 source_factor_ref, projection_contract_ref, state,
                 selected_proposal_ref, loss_ref, payload, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            [
                (
                    row["receipt_ref"],
                    document_ref,
                    row["domain"],
                    row["source_resolution_ref"],
                    row["source_factor_ref"],
                    row["projection_contract_ref"],
                    row["state"],
                    row.get("selected_proposal_ref"),
                    row.get("loss_ref"),
                    _json(row),
                    _sha(row),
                )
                for row in projection_receipts
            ],
        )
    if projections:
        cursor.executemany(
            """
            INSERT INTO pnf_domain_ir
                (domain_ir_ref, document_ref, domain, source_resolution_ref,
                 source_factor_ref, selected_proposal_ref,
                 structural_signature_ref, projection_contract_ref,
                 projection_receipt_ref, loss_ref, validation_state,
                 payload, ir_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s)
            ON CONFLICT (domain_ir_ref) DO NOTHING
            """,
            [
                (
                    row["domain_ir_ref"],
                    document_ref,
                    row["domain"],
                    row["source_resolution_ref"],
                    row["source_factor_ref"],
                    row["selected_proposal_ref"],
                    row["structural_signature_ref"],
                    row["projection_contract_ref"],
                    row["projection_receipt_ref"],
                    row["loss_ref"],
                    row["validation_state"],
                    _json(row),
                    _sha(row),
                )
                for row in projections
            ],
        )
    if executions:
        cursor.executemany(
            """
            INSERT INTO pnf_ir_execution_receipt
                (receipt_ref, document_ref, request_ref, domain_ir_ref,
                 rule_or_query_ref, outcome, applicability_witnessed,
                 payload, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            [
                (
                    row["receipt_ref"],
                    document_ref,
                    row["request_ref"],
                    row["domain_ir_ref"],
                    row["rule_or_query_ref"],
                    row["outcome"],
                    bool(row.get("applicability_witnessed")),
                    _json(row),
                    _sha(row),
                )
                for row in executions
            ],
        )
    return {
        "candidate_assessments": len(assessments),
        "admissibility_receipts": len(admissions),
        "resolution_receipts": len(resolutions),
        "projection_contracts": len(contracts),
        "projection_demands": len(demands),
        "projection_losses": len(losses),
        "projection_receipts": len(projection_receipts),
        "domain_ir": len(projections),
        "execution_receipts": len(executions),
    }


__all__ = ["persist_semantic_lifecycle_artifacts"]
