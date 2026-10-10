from __future__ import annotations

import pytest

from src.ontology.wikidata_nat_source_discovery import (
    build_same_source_identity_receipt,
    build_source_discovery_plan,
    normalize_discovery_provider_receipt,
)
from src.ontology.wikidata_nat_source_discovery_integration import (
    build_replayable_alternate_source_fetch_plan,
)


def _source_plan() -> dict:
    r1 = {
        "residual_ref": "r1",
        "source_row_ref": "row-1",
        "subject_qid": "Q1",
        "statement_reference": "Q1$A",
        "source_property": "P5991",
        "target_property": "P14143",
    }
    r2 = {
        "residual_ref": "r2",
        "source_row_ref": "row-2",
        "subject_qid": "Q2",
        "statement_reference": "Q2$B",
        "source_property": "P5991",
        "target_property": "P14143",
    }
    return {
        "plan_ref": "source-plan",
        "source_batch_ref": "batch",
        "source_coverage_dispatch_ref": "coverage",
        "source_residuals": [r1, r2],
        "fetch_demands": [
            {
                "fetch_ref": "fetch-ok",
                "url": "https://example.org/report.pdf",
                "consumer_residual_refs": ["r1"],
            },
            {
                "fetch_ref": "fetch-dead",
                "url": "https://example.org/resolve?urn=urn%3Anbn%3Ase%3Anaturvardsverket%3Adiva-8814",
                "consumer_residual_refs": ["r2"],
            },
        ],
    }


def _source_dispatch() -> dict:
    return {
        "dispatch_ref": "source-dispatch",
        "fetch_receipts": [
            {
                "fetch_ref": "fetch-ok",
                "receipt_ref": "receipt-ok",
                "url": "https://example.org/report.pdf",
                "status": "content_acquired",
            },
            {
                "fetch_ref": "fetch-dead",
                "receipt_ref": "receipt-dead",
                "url": "https://example.org/resolve?urn=urn%3Anbn%3Ase%3Anaturvardsverket%3Adiva-8814",
                "status": "fetch_failed",
                "failure_type": "HTTPError",
                "failure_detail": "403 Client Error",
            },
        ],
    }


def test_discovery_is_scheduled_only_for_failed_locator() -> None:
    plan = build_source_discovery_plan(_source_plan(), _source_dispatch())
    assert plan["failed_locator_count"] == 1
    assert plan["blocked_residual_count"] == 1
    demand = plan["demands"][0]
    assert demand["consumer_residual_refs"] == ["r2"]
    assert demand["same_source_identity_required"] is True
    assert demand["source_support_payment_claimed"] is False
    assert any("urn:nbn:se:naturvardsverket:diva-8814" in query for query in demand["query_seeds"])


def test_provider_result_is_candidate_only() -> None:
    plan = build_source_discovery_plan(_source_plan(), _source_dispatch())
    demand = plan["demands"][0]
    receipt = normalize_discovery_provider_receipt(
        demand,
        {
            "provider": "mcp:tavily",
            "provider_call_ref": "tool-call-1",
            "query_refs": ["query-1"],
            "candidates": [
                {
                    "url": "https://new.example.org/report.pdf",
                    "title": "Recovered report",
                    "snippet": "Search snippet mentioning the report",
                    "rank": 1,
                }
            ],
        },
    )
    candidate = receipt["candidates"][0]
    assert candidate["same_source_identity_trit"] == 0
    assert candidate["same_source_identity_state"] == "open"
    assert candidate["source_support_paid"] is False
    assert receipt["same_source_identity_paid"] is False
    assert receipt["source_support_paid"] is False


def test_terminal_identity_requires_evidence_locator() -> None:
    plan = build_source_discovery_plan(_source_plan(), _source_dispatch())
    demand = plan["demands"][0]
    discovery = normalize_discovery_provider_receipt(
        demand,
        {
            "provider": "google_search",
            "candidates": [{"url": "https://new.example.org/report.pdf"}],
        },
    )
    candidate = discovery["candidates"][0]
    with pytest.raises(ValueError):
        build_same_source_identity_receipt(
            demand,
            candidate,
            disposition="same_source",
            verifier_reference="reviewer",
            identity_evidence_locator="",
        )


def test_same_source_identity_is_balanced_and_still_not_source_support() -> None:
    plan = build_source_discovery_plan(_source_plan(), _source_dispatch())
    demand = plan["demands"][0]
    discovery = normalize_discovery_provider_receipt(
        demand,
        {
            "provider": "exa",
            "candidates": [{"url": "https://new.example.org/report.pdf"}],
        },
    )
    candidate = discovery["candidates"][0]
    admitted = build_same_source_identity_receipt(
        demand,
        candidate,
        disposition="same_source",
        verifier_reference="identity-review-v1",
        identity_evidence_locator="urn:nbn:se:naturvardsverket:diva-8814",
    )
    assert admitted["same_source_identity_trit"] == 1
    assert admitted["same_source_identity_paid"] is True
    assert admitted["source_support_paid"] is False
    assert admitted["authority_evaluated"] is False


def test_only_same_source_admission_reenters_existing_fetch_contract() -> None:
    source_plan = _source_plan()
    discovery_plan = build_source_discovery_plan(source_plan, _source_dispatch())
    demand = discovery_plan["demands"][0]
    discovery_receipt = normalize_discovery_provider_receipt(
        demand,
        {
            "provider": "mcp:search",
            "candidates": [
                {"url": "https://new.example.org/report.pdf", "rank": 1},
                {"url": "https://wrong.example.org/other.pdf", "rank": 2},
            ],
        },
    )
    discovery_dispatch = {
        "dispatch_ref": "discovery-dispatch",
        "receipts": [discovery_receipt],
    }
    good, bad = discovery_receipt["candidates"]
    admitted = build_same_source_identity_receipt(
        demand,
        good,
        disposition="same_source",
        verifier_reference="reviewer",
        identity_evidence_locator="persistent-id-match",
    )
    rejected = build_same_source_identity_receipt(
        demand,
        bad,
        disposition="different_source",
        verifier_reference="reviewer",
        identity_evidence_locator="title/date mismatch",
    )
    replay = build_replayable_alternate_source_fetch_plan(
        source_plan,
        discovery_plan,
        discovery_dispatch,
        [admitted, rejected],
    )
    assert replay["distinct_url_count"] == 1
    assert replay["fetch_demands"][0]["url"] == good["candidate_locator"]
    assert replay["source_residual_count"] == 1
    assert replay["source_residuals"][0]["residual_ref"] == "r2"
    assert replay["source_support_paid_count"] == 0
    assert replay["consumer_verification_performed"] is False
