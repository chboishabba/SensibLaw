from __future__ import annotations

from src.ontology.wikidata_nat_source_adjudication import (
    compile_reviewed_source_decisions,
)


def _ready_demand() -> dict:
    return {
        "demand_ref": "demand:1",
        "source_residual_ref": "residual:1",
        "source_row_ref": "row:1",
        "candidate_digest": "candidate:digest",
        "state": "ready",
        "source_artifacts": [{"receipt_ref": "artifact:1"}],
        "proposition": {
            "source_claim_digest": "sha256:source",
            "target_claim_digest": "sha256:target",
        },
    }


def test_reviewed_supported_decision_pays_only_source_support() -> None:
    result = compile_reviewed_source_decisions(
        {
            "plan_ref": "verify:1",
            "demands": [_ready_demand()],
        },
        {
            "sidecar_ref": "review:1",
            "decisions": [
                {
                    "source_verification_demand_ref": "demand:1",
                    "source_artifact_receipt_ref": "artifact:1",
                    "verifier_reference": "reviewer:test",
                    "evidence_locator": "page=4 chars=100-180",
                    "disposition": "supported",
                }
            ],
        },
    )
    assert result["reviewed_decision_count"] == 1
    assert result["source_support_paid_count"] == 1
    assert result["source_support_rejected_count"] == 0
    assert result["authority_evaluated"] is False
    assert result["semantic_promotion_performed"] is False
    assert result["migration_authority"] is False
    admission = result["source_support_admissions"][0]
    assert admission["source_support_trit"] == 1
    assert admission["authority_state"] == "open"


def test_reviewed_contradiction_is_negative_without_authority() -> None:
    result = compile_reviewed_source_decisions(
        {"plan_ref": "verify:2", "demands": [_ready_demand()]},
        {
            "sidecar_ref": "review:2",
            "decisions": [
                {
                    "source_verification_demand_ref": "demand:1",
                    "source_artifact_receipt_ref": "artifact:1",
                    "verifier_reference": "reviewer:test",
                    "evidence_locator": "page=7 chars=200-260",
                    "disposition": "contradicted",
                }
            ],
        },
    )
    admission = result["source_support_admissions"][0]
    assert admission["source_support_trit"] == -1
    assert admission["source_support_rejected"] is True
    assert admission["migration_authority"] is False


def test_blocked_demand_cannot_be_bypassed_by_review_sidecar() -> None:
    blocked = _ready_demand()
    blocked["state"] = "blocked_no_acquired_source_content"
    try:
        compile_reviewed_source_decisions(
            {"plan_ref": "verify:3", "demands": [blocked]},
            {
                "decisions": [
                    {
                        "source_verification_demand_ref": "demand:1",
                        "source_artifact_receipt_ref": "artifact:1",
                        "verifier_reference": "reviewer:test",
                        "evidence_locator": "page=1",
                        "disposition": "supported",
                    }
                ]
            },
        )
    except ValueError as exc:
        assert "cannot bypass blocked demand" in str(exc)
    else:
        raise AssertionError("blocked source demand was bypassed")
