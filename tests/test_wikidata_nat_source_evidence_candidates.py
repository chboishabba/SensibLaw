from __future__ import annotations

import hashlib

from src.ontology.wikidata_nat_source_evidence_candidates import (
    build_source_evidence_candidate_plan,
)
from src.ontology.wikidata_nat_source_media_materialization import (
    materialize_source_fetch_receipt,
)
from src.ontology.wikidata_nat_source_support import fetch_source_content


class _Response:
    def __init__(self, body: bytes) -> None:
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.url = "https://example.test/report"
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 65536):
        del chunk_size
        yield self._body


def test_candidate_compiler_locates_quantity_year_and_scope_without_paying_support(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.ontology.wikidata_nat_source_support._public_http_url",
        lambda url: (True, "public_http_origin"),
    )
    body = (
        b"<html><body><p>During 2024, Scope 1 greenhouse gas emissions were "
        b"1,082 tonnes CO2e.</p></body></html>"
    )
    artifact_dir = tmp_path / "artifacts"
    fetch_receipt = fetch_source_content(
        {"fetch_ref": "fetch:1", "url": "https://example.test/report"},
        http_get=lambda *args, **kwargs: _Response(body),
        artifact_store_dir=artifact_dir,
    )
    materialized_dir = tmp_path / "materialized"
    materialization = materialize_source_fetch_receipt(
        fetch_receipt,
        artifact_store_dir=artifact_dir,
        materialized_store_dir=materialized_dir,
    )
    media_dispatch = {
        "dispatch_ref": "media:1",
        "materializations": [materialization],
    }
    verification_plan = {
        "plan_ref": "verify:1",
        "demands": [
            {
                "demand_ref": "demand:1",
                "source_residual_ref": "residual:1",
                "source_row_ref": "row:1",
                "statement_reference": "Q1$abc",
                "state": "ready",
                "source_artifacts": [
                    {
                        "receipt_ref": fetch_receipt["receipt_ref"],
                        "content_digest": fetch_receipt["content_digest"],
                    }
                ],
                "proposition": {
                    "source_claim_bundle": {
                        "value": "+1082",
                        "qualifiers": {
                            "P3831": ["Q124883250"],
                            "P580": ["+2024-01-01T00:00:00Z"],
                            "P582": ["+2024-12-31T00:00:00Z"],
                        },
                    }
                },
            }
        ],
    }

    plan = build_source_evidence_candidate_plan(
        verification_plan,
        media_dispatch,
        materialized_store_dir=materialized_dir,
    )
    assert plan["demand_count"] == 1
    assert plan["demands_with_candidates_count"] == 1
    assert plan["source_support_paid_count"] == 0
    candidate = plan["candidates"][0]
    assert candidate["matched_quantity"] == "1,082"
    assert candidate["observed_years"] == ["2024"]
    assert "scope 1" in candidate["observed_scope_cues"]
    assert candidate["matched_axes"] == ["quantity", "year", "scope_cue"]
    assert candidate["candidate_only"] is True
    assert candidate["proposition_support_evaluated"] is False
    assert candidate["source_support_paid"] is False


def test_quantity_match_without_context_stays_candidate_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.ontology.wikidata_nat_source_support._public_http_url",
        lambda url: (True, "public_http_origin"),
    )
    body = b"<html><body><p>Unrelated table cell: 1082</p></body></html>"
    artifact_dir = tmp_path / "artifacts"
    fetch_receipt = fetch_source_content(
        {"fetch_ref": "fetch:2", "url": "https://example.test/report"},
        http_get=lambda *args, **kwargs: _Response(body),
        artifact_store_dir=artifact_dir,
    )
    materialized_dir = tmp_path / "materialized"
    materialization = materialize_source_fetch_receipt(
        fetch_receipt,
        artifact_store_dir=artifact_dir,
        materialized_store_dir=materialized_dir,
    )
    plan = build_source_evidence_candidate_plan(
        {
            "plan_ref": "verify:2",
            "demands": [
                {
                    "demand_ref": "demand:2",
                    "source_residual_ref": "residual:2",
                    "source_row_ref": "row:2",
                    "statement_reference": "Q2$abc",
                    "state": "ready",
                    "source_artifacts": [
                        {"receipt_ref": fetch_receipt["receipt_ref"]}
                    ],
                    "proposition": {
                        "source_claim_bundle": {
                            "value": "+1082",
                            "qualifiers": {
                                "P3831": ["Q124883250"],
                                "P580": ["+2024-01-01T00:00:00Z"],
                            },
                        }
                    },
                }
            ],
        },
        {"dispatch_ref": "media:2", "materializations": [materialization]},
        materialized_store_dir=materialized_dir,
    )
    candidate = plan["candidates"][0]
    assert candidate["matched_axes"] == ["quantity"]
    assert candidate["candidate_score"] == 1
    assert candidate["proposition_support_evaluated"] is False
    assert plan["source_support_paid_count"] == 0


def test_blocked_verification_demand_is_not_reopened_by_media_candidates(tmp_path) -> None:
    plan = build_source_evidence_candidate_plan(
        {
            "plan_ref": "verify:blocked",
            "demands": [
                {
                    "demand_ref": "demand:blocked",
                    "state": "blocked_no_acquired_source_content",
                }
            ],
        },
        {"dispatch_ref": "media:none", "materializations": []},
        materialized_store_dir=tmp_path,
    )
    assert plan["blocked_count"] == 1
    assert plan["candidate_count"] == 0
    assert plan["source_support_paid_count"] == 0
