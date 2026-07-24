from __future__ import annotations

from src.storage.postgres.semantic_lifecycle_store import (
    persist_semantic_lifecycle_artifacts,
)


class Cursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[tuple[object, ...]]]] = []

    def executemany(self, statement, rows) -> None:
        self.calls.append((" ".join(statement.split()), list(rows)))


def test_semantic_lifecycle_store_batches_in_parent_first_order() -> None:
    artifacts = {
        "semantic_lifecycle": {
            "candidate_assessments": [
                {
                    "assessment_ref": "assessment:1",
                    "proposal_ref": "proposal:1",
                    "semantic_coordinate_ref": "coordinate:1",
                    "outcome": "satisfied",
                    "coverage_complete": True,
                    "applicable": True,
                }
            ],
            "admissibility_receipts": [
                {
                    "receipt_ref": "admission:1",
                    "proposal_ref": "proposal:1",
                    "assessment_ref": "assessment:1",
                    "state": "admitted",
                    "authority_ceiling": "candidate_pnf_only",
                }
            ],
            "resolution_receipts": [
                {
                    "resolution_ref": "resolution:1",
                    "fibre_summary_ref": "factor:1",
                    "semantic_coordinate_ref": "coordinate:1",
                    "state": "resolved_unique",
                    "selected_proposal_ref": "proposal:1",
                    "selector_ref": "selector:1",
                }
            ],
        },
        "domain_ir_build": {
            "contracts": [
                {
                    "contract_ref": "contract:legal",
                    "domain": "legal",
                    "authority_ceiling": "legal_ir_candidate",
                    "residual_policy": "block",
                }
            ],
            "demands": [],
            "losses": [
                {
                    "loss_ref": "loss:1",
                    "domain": "legal",
                    "source_resolution_ref": "resolution:1",
                    "projection_contract_ref": "contract:legal",
                }
            ],
            "receipts": [
                {
                    "receipt_ref": "projection-receipt:1",
                    "domain": "legal",
                    "source_resolution_ref": "resolution:1",
                    "source_factor_ref": "factor:1",
                    "projection_contract_ref": "contract:legal",
                    "state": "projected",
                    "selected_proposal_ref": "proposal:1",
                    "loss_ref": "loss:1",
                }
            ],
            "projections": [
                {
                    "domain_ir_ref": "legal-ir:1",
                    "domain": "legal",
                    "source_resolution_ref": "resolution:1",
                    "source_factor_ref": "factor:1",
                    "selected_proposal_ref": "proposal:1",
                    "structural_signature_ref": "signature:1",
                    "projection_contract_ref": "contract:legal",
                    "projection_receipt_ref": "projection-receipt:1",
                    "loss_ref": "loss:1",
                    "validation_state": "operational_candidate",
                }
            ],
        },
        "ir_execution_receipts": [
            {
                "receipt_ref": "execution:1",
                "request_ref": "request:1",
                "domain_ir_ref": "legal-ir:1",
                "rule_or_query_ref": "rule:1",
                "outcome": "executed",
                "applicability_witnessed": True,
            }
        ],
    }
    cursor = Cursor()

    counts = persist_semantic_lifecycle_artifacts(
        cursor,
        document_ref="document:1",
        artifacts=artifacts,
    )

    tables = [call[0].split("INSERT INTO ", 1)[1].split()[0] for call in cursor.calls]
    assert tables == [
        "pnf_candidate_assessment",
        "pnf_admissibility_receipt",
        "pnf_resolution_receipt",
        "pnf_domain_ir_projection_contract",
        "pnf_projection_loss_receipt",
        "pnf_domain_ir_projection_receipt",
        "pnf_domain_ir",
        "pnf_ir_execution_receipt",
    ]
    assert counts["candidate_assessments"] == 1
    assert counts["domain_ir"] == 1
    assert counts["execution_receipts"] == 1
