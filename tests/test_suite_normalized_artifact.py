from __future__ import annotations

from src.policy.suite_normalized_artifact import (
    build_affidavit_coverage_review_normalized_artifact,
    build_au_fact_review_bundle_normalized_artifact,
    build_gwb_broader_review_normalized_artifact,
    build_gwb_public_review_normalized_artifact,
)


def _compiler_contract(*, lane: str, source_family: str) -> dict[str, object]:
    return {
        "schema_version": "sl.compiler_contract.v0_1",
        "lane": lane,
        "evidence_bundle": {
            "source_family": source_family,
            "item_label": "row",
            "source_count": 1,
            "item_count": 1,
        },
        "promoted_outcomes": {
            "promoted_count": 1,
            "review_count": 0,
            "abstained_count": 0,
        },
    }


def _promotion_gate() -> dict[str, str]:
    return {
        "decision": "promote",
        "reason": "fixture",
        "product_ref": "fixture_product",
    }


def test_build_gwb_public_review_normalized_artifact_preserves_explicit_text_ref() -> None:
    artifact = build_gwb_public_review_normalized_artifact(
        artifact_id="fixture",
        compiler_contract=_compiler_contract(lane="gwb", source_family="gwb_public_review"),
        promotion_gate=_promotion_gate(),
        source_input={
            "path": "tests/fixtures/example.json",
            "text_ref": {
                "text_id": "text:gwb:public:1",
                "envelope_id": "env:gwb:public:1",
                "segment_id": "segment:1",
            },
        },
        workflow_summary={"stage": "record", "recommended_view": "summary"},
    )

    assert artifact["text_ref"] == {
        "text_id": "text:gwb:public:1",
        "envelope_id": "env:gwb:public:1",
        "segment_ids": ["segment:1"],
    }


def test_build_gwb_broader_review_normalized_artifact_keeps_segment_ids() -> None:
    artifact = build_gwb_broader_review_normalized_artifact(
        artifact_id="fixture",
        compiler_contract=_compiler_contract(lane="gwb", source_family="gwb_broader_review"),
        promotion_gate=_promotion_gate(),
        source_input={
            "path": "tests/fixtures/example.json",
            "text_ref": {
                "text_id": "text:gwb:broader:1",
                "envelope_id": "env:gwb:broader:1",
                "segment_ids": ["segment:1", "segment:2", "segment:1"],
            },
        },
        workflow_summary={"stage": "record", "recommended_view": "summary"},
    )

    assert artifact["text_ref"] == {
        "text_id": "text:gwb:broader:1",
        "envelope_id": "env:gwb:broader:1",
        "segment_ids": ["segment:1", "segment:2"],
    }


def test_build_au_fact_review_bundle_normalized_artifact_uses_first_document_text_ref() -> None:
    artifact = build_au_fact_review_bundle_normalized_artifact(
        semantic_run_id="semantic:run:1",
        workflow_kind="au_semantic",
        compiler_contract=_compiler_contract(lane="au", source_family="au_fact_review_bundle"),
        promotion_gate=_promotion_gate(),
        source_documents=[
            {
                "doc_id": "doc:1",
                "text_ref": {
                    "text_id": "text:au:1",
                    "envelope_id": "env:au:1",
                    "segment_ids": ["segment:au:1"],
                },
            }
        ],
    )

    assert artifact["text_ref"] == {
        "text_id": "text:au:1",
        "envelope_id": "env:au:1",
        "segment_ids": ["segment:au:1"],
    }


def test_build_affidavit_coverage_review_normalized_artifact_omits_text_ref_when_absent() -> None:
    artifact = build_affidavit_coverage_review_normalized_artifact(
        artifact_id="fixture",
        compiler_contract=_compiler_contract(
            lane="affidavit",
            source_family="affidavit_coverage_review",
        ),
        promotion_gate=_promotion_gate(),
        source_input={"path": "tests/fixtures/affidavit.json"},
        workflow_summary={"stage": "record", "recommended_view": "summary"},
    )

    assert "text_ref" not in artifact
