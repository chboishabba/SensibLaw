"""Role-aware applicability normalization for Domain IR projection.

A projection contract that is undefined for the current statement role returns
``inapplicable``. It does not create a repair demand, because no missing evidence
can make that contract applicable without changing the statement role itself.
"""

from __future__ import annotations

from typing import Any, Sequence

from src.pnf.domain_ir import (
    DomainIRBuild,
    DomainIRProjectionContract,
    DomainIRProjectionReceipt,
)
from src.pnf.domain_ir_projection import (
    DEFAULT_DOMAIN_IR_CONTRACTS,
    build_domain_ir,
)
from src.pnf.semantic_lifecycle import ResolutionReceipt


def normalize_projection_applicability(build: DomainIRBuild) -> DomainIRBuild:
    demands_by_ref = {row.demand_ref: row for row in build.demands}
    inapplicable_receipt_refs: set[str] = set()
    replacement_receipts: list[DomainIRProjectionReceipt] = []
    removed_demand_refs: set[str] = set()

    for receipt in build.receipts:
        role_demands = tuple(
            demands_by_ref[ref]
            for ref in receipt.demand_refs
            if ref in demands_by_ref
            and demands_by_ref[ref].demand_kind == "statement_role_inapplicable"
        )
        if not role_demands:
            replacement_receipts.append(receipt)
            continue
        inapplicable_receipt_refs.add(receipt.receipt_ref)
        removed_demand_refs.update(receipt.demand_refs)
        replacement_receipts.append(
            DomainIRProjectionReceipt(
                document_ref=receipt.document_ref,
                domain=receipt.domain,
                source_resolution_ref=receipt.source_resolution_ref,
                source_factor_ref=receipt.source_factor_ref,
                projection_contract_ref=receipt.projection_contract_ref,
                state="inapplicable",
                selected_proposal_ref=receipt.selected_proposal_ref,
                demand_refs=(),
                loss_ref=None,
                reason_refs=tuple(
                    sorted({*receipt.reason_refs, "statement_role_inapplicable"})
                ),
            )
        )

    # Role-inapplicable results are blocked before projection, so they should not
    # normally have projection/loss children. Filtering keeps this invariant
    # explicit if a future producer supplies them inconsistently.
    inapplicable_keys = {
        (
            receipt.source_resolution_ref,
            receipt.domain,
        )
        for receipt in build.receipts
        if receipt.receipt_ref in inapplicable_receipt_refs
    }
    return DomainIRBuild(
        document_ref=build.document_ref,
        contracts=build.contracts,
        projections=tuple(
            row
            for row in build.projections
            if (row.source_resolution_ref, row.domain) not in inapplicable_keys
        ),
        receipts=tuple(
            sorted(replacement_receipts, key=lambda row: row.receipt_ref)
        ),
        losses=tuple(
            row
            for row in build.losses
            if (row.source_resolution_ref, row.domain) not in inapplicable_keys
        ),
        demands=tuple(
            row for row in build.demands if row.demand_ref not in removed_demand_refs
        ),
    )


def build_applicable_domain_ir(
    *,
    document_ref: str,
    resolutions: Sequence[ResolutionReceipt],
    factors: Sequence[Any],
    proposals: Sequence[Any],
    contracts: Sequence[
        DomainIRProjectionContract
    ] = DEFAULT_DOMAIN_IR_CONTRACTS,
) -> DomainIRBuild:
    return normalize_projection_applicability(
        build_domain_ir(
            document_ref=document_ref,
            resolutions=resolutions,
            factors=factors,
            proposals=proposals,
            contracts=contracts,
        )
    )


__all__ = [
    "build_applicable_domain_ir",
    "normalize_projection_applicability",
]
