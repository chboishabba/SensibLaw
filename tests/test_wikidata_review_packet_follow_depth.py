from __future__ import annotations

from typing import Sequence

import pytest

from src.ontology import wikidata_review_packet_follow_depth as follow_depth


def _build_receipt(
    *,
    url: str,
    extracted_evidence: Sequence[str] | None = None,
    unresolved_uncertainty: Sequence[str] | None = None,
) -> dict[str, object]:
    return {
        "receipt_id": "receipt-for-" + url,
        "url": url,
        "extracted_evidence": extracted_evidence,
        "unresolved_uncertainty": unresolved_uncertainty,
    }


def test_enrich_follow_receipt_from_extracted_evidence() -> None:
    raw = _build_receipt(
        url="https://example.org/follow/1",
        extracted_evidence=[
            "The extracted detail describes the migration step.",
            "Second snippet elaborates on qualifier propagation.",
        ],
    )
    enriched = follow_depth.enrich_follow_receipt_with_depth(
        raw,
        max_excerpt_chars=200,
    )
    assert enriched["status"] == "enriched"
    assert enriched["excerpt_source"] == "extracted_evidence"
    assert enriched["evidence_excerpt"] == "The extracted detail describes the migration step."
    assert enriched["evidence_summary"] == (
        "The extracted detail describes the migration step.; Second snippet elaborates on qualifier propagation."
    )
    assert "failure_reason" not in enriched


def test_enrich_follow_receipt_from_source_text_when_no_evidence() -> None:
    raw = _build_receipt(
        url="https://example.org/follow/2",
        extracted_evidence=None,
        unresolved_uncertainty=["initial_uncertainty"],
    )
    enriched = follow_depth.enrich_follow_receipt_with_depth(
        raw,
        source_text="   Source text with newlines\nand multi-spaces   ",
        max_excerpt_chars=100,
    )
    assert enriched["status"] == "enriched"
    assert enriched["excerpt_source"] == "source_text"
    assert enriched["evidence_excerpt"] == "Source text with newlines and multi-spaces"
    assert enriched["evidence_summary"] == "derived_from_bounded_source_text"
    assert "excerpt_derived_without_explicit_extracted_evidence" in enriched["unresolved_uncertainty"]


def test_enrich_follow_receipt_with_no_excerpt_data() -> None:
    raw = _build_receipt(url="https://example.org/follow/3", extracted_evidence=None)
    enriched = follow_depth.enrich_follow_receipt_with_depth(raw)
    assert enriched["status"] == "no_excerpt_available"
    assert enriched["failure_reason"] == "no_extracted_evidence_or_source_text"


def test_enrich_review_packet_receipts_tracks_counts() -> None:
    follow_receipts = [
        _build_receipt(
            url="https://example.org/follow/1",
            extracted_evidence=["evidence one"],
        ),
        _build_receipt(
            url="https://example.org/follow/2",
            extracted_evidence=None,
        ),
    ]
    review_packet = {
        "packet_id": "packet-123",
        "follow_receipts": follow_receipts,
    }
    enriched = follow_depth.enrich_review_packet_follow_depth(
        review_packet,
        source_text_by_url={"https://example.org/follow/2": "Replacement source text"},
    )
    assert enriched["schema_version"] == follow_depth.FOLLOW_DEPTH_SCHEMA_VERSION
    assert enriched["packet_id"] == "packet-123"
    assert enriched["receipt_count"] == 2
    assert enriched["enriched_count"] == 2
    assert enriched["no_excerpt_count"] == 0
    assert {receipt["status"] for receipt in enriched["receipts"]} == {"enriched"}
    assert enriched["receipts"][1]["excerpt_source"] == "source_text"

