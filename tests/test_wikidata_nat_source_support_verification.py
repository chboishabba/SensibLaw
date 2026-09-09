from __future__ import annotations

from src.ontology.wikidata_nat_source_support_verification import (
    admit_source_support,
    build_source_verification_plan,
    build_source_verification_receipt,
)
from src.policy.carriers.canonical import canonical_sha256


def _candidate() -> dict:
    return {
        "candidate_id": "Q1|P5991|1",
        "entity_qid": "Q1",
        "classification": "safe_with_reference_transfer",
        "action": "migrate_with_refs",
        "claim_bundle_before": {
            "subject": "Q1",
            "property": "P5991",
            "value": "+442",
            "rank": "normal",
            "qualifiers": {"P585": ["+2021-00-00T00:00:00Z"]},
            "references": [{"P854": ["https://example.com/report.pdf"]}],
        },
        "claim_bundle_after": {
            "subject": "Q1",
            "property": "P14143",
            "value": "+442",
            "rank": "normal",
            "qualifiers": {"P585": ["+2021-00-00T00:00:00Z"]},
            "references": [{"P854": ["https://example.com/report.pdf"]}],
        },
    }


def _fixtures() -> tuple[dict, dict, dict, list[dict]]:
    candidate = _candidate()
    digest = canonical_sha256(candidate)
    batch = {
        "batch_ref": "batch:1",
        "rows": [
            {
                "row_ref": "row:1",
                "qid": "Q1",
                "statement_reference": "Q1$SOURCE-GUID",
                "input_digest": digest,
            }
        ],
    }
    source_plan = {
        "plan_ref": "source-plan:1",
        "source_residuals": [
            {
                "residual_ref": "source-residual:1",
                "source_row_ref": "row:1",
                "subject_qid": "Q1",
                "statement_reference": "Q1$SOURCE-GUID",
                "reference_urls": ["https://example.com/report.pdf"],
            }
        ],
    }
    source_dispatch = {
        "dispatch_ref": "source-dispatch:1",
        "fetch_receipts": [
            {
                "receipt_ref": "source-fetch-receipt:1",
                "url": "https://example.com/report.pdf",
                "final_url": "https://example.com/report.pdf",
                "content_digest": "sha256:content",
                "content_type": "application/pdf",
                "content_acquired": True,
            }
        ],
    }
    return batch, source_plan, source_dispatch, [{"candidates": [candidate]}]


def test_verification_plan_recovers_exact_candidate_by_digest() -> None:
    batch, source_plan, source_dispatch, packs = _fixtures()
    plan = build_source_verification_plan(
        batch=batch,
        source_plan=source_plan,
        source_dispatch=source_dispatch,
        migration_packs=packs,
    )
    assert plan["demand_count"] == 1
    assert plan["ready_count"] == 1
    demand = plan["demands"][0]
    assert demand["state"] == "ready"
    assert demand["candidate_digest"] == batch["rows"][0]["input_digest"]
    assert demand["proposition"]["source_claim_bundle"]["value"] == "+442"
    assert demand["proposition"]["target_claim_bundle"]["property"] == "P14143"
    assert demand["source_support_payment_claimed"] is False
    assert demand["authority_evaluated"] is False


def test_supported_receipt_pays_only_source_support() -> None:
    batch, source_plan, source_dispatch, packs = _fixtures()
    demand = build_source_verification_plan(
        batch=batch,
        source_plan=source_plan,
        source_dispatch=source_dispatch,
        migration_packs=packs,
    )["demands"][0]
    receipt = build_source_verification_receipt(
        demand,
        disposition="supported",
        verifier_reference="verifier:test",
        source_artifact_receipt_ref="source-fetch-receipt:1",
        evidence_locator="p. 42, emissions table",
    )
    admission = admit_source_support(demand, receipt)
    assert admission["source_support_state"] == "admitted"
    assert admission["source_support_trit"] == 1
    assert admission["source_support_paid"] is True
    assert admission["authority_evaluated"] is False
    assert admission["authority_state"] == "open"
    assert admission["semantic_promotion_performed"] is False
    assert admission["migration_authority"] is False


def test_contradicted_receipt_is_explicit_negative_not_fetch_failure() -> None:
    batch, source_plan, source_dispatch, packs = _fixtures()
    demand = build_source_verification_plan(
        batch=batch,
        source_plan=source_plan,
        source_dispatch=source_dispatch,
        migration_packs=packs,
    )["demands"][0]
    receipt = build_source_verification_receipt(
        demand,
        disposition="contradicted",
        verifier_reference="verifier:test",
        source_artifact_receipt_ref="source-fetch-receipt:1",
        evidence_locator="p. 42 states 441 tCO2e, not 442",
    )
    admission = admit_source_support(demand, receipt)
    assert admission["source_support_state"] == "rejected"
    assert admission["source_support_trit"] == -1
    assert admission["source_support_paid"] is False
    assert admission["source_support_rejected"] is True


def test_unresolved_receipt_preserves_balanced_zero() -> None:
    batch, source_plan, source_dispatch, packs = _fixtures()
    demand = build_source_verification_plan(
        batch=batch,
        source_plan=source_plan,
        source_dispatch=source_dispatch,
        migration_packs=packs,
    )["demands"][0]
    receipt = build_source_verification_receipt(
        demand,
        disposition="unresolved",
        verifier_reference="verifier:test",
        source_artifact_receipt_ref="source-fetch-receipt:1",
        evidence_locator="",
        verification_note="source table is ambiguous between gross and net emissions",
    )
    admission = admit_source_support(demand, receipt)
    assert admission["source_support_state"] == "open"
    assert admission["source_support_trit"] == 0
    assert admission["source_support_paid"] is False
    assert admission["source_support_rejected"] is False


def test_terminal_disposition_requires_evidence_locator() -> None:
    batch, source_plan, source_dispatch, packs = _fixtures()
    demand = build_source_verification_plan(
        batch=batch,
        source_plan=source_plan,
        source_dispatch=source_dispatch,
        migration_packs=packs,
    )["demands"][0]
    try:
        build_source_verification_receipt(
            demand,
            disposition="supported",
            verifier_reference="verifier:test",
            source_artifact_receipt_ref="source-fetch-receipt:1",
            evidence_locator="",
        )
    except ValueError as exc:
        assert "evidence locator" in str(exc)
    else:
        raise AssertionError("terminal source verification must require an evidence locator")
