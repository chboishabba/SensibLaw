from __future__ import annotations

from src.policy.compiler_contract import (
    PromotedOutcomeContract,
    build_au_fact_review_bundle_contract,
    build_au_public_handoff_contract,
    build_gwb_broader_review_contract,
    build_gwb_public_handoff_contract,
    build_gwb_public_review_contract,
    build_wikidata_migration_pack_contract,
    normalize_promoted_outcomes,
)
from src.policy.product_gate import build_product_gate


def test_build_au_public_handoff_contract() -> None:
    payload = build_au_public_handoff_contract(
        {
            "source_bundle_paths": ["a.json", "b.json"],
            "selected_facts": [
                {"fact_id": "f1", "review_status": "captured"},
                {"fact_id": "f2", "review_status": "review_queue"},
            ],
            "summary": {"fact_count": 2, "abstained_fact_count": 1},
        }
    )

    assert payload["lane"] == "au"
    assert payload["evidence_bundle"]["source_count"] == 2
    assert payload["promoted_outcomes"]["promoted_count"] == 1
    assert payload["promoted_outcomes"]["review_count"] == 1
    assert payload["promoted_outcomes"]["abstained_count"] == 1
    assert payload["derived_products"][0]["role"] == "operator_handoff"


def test_build_gwb_public_handoff_contract() -> None:
    payload = build_gwb_public_handoff_contract(
        {
            "timeline_event_count": 12,
            "summary": {"selected_promoted_relation_count": 5},
            "selected_seed_lanes": [
                {"review_status": "matched"},
                {"review_status": "candidate_only"},
            ],
            "unresolved_surfaces": [{"surface_text": "Bush administration"}],
        }
    )

    assert payload["lane"] == "gwb"
    assert payload["evidence_bundle"]["item_count"] == 12
    assert payload["promoted_outcomes"]["promoted_count"] == 5
    assert payload["promoted_outcomes"]["review_count"] == 2
    assert payload["derived_products"][2]["product_kind"] == "graph"


def test_build_gwb_public_review_contract() -> None:
    payload = build_gwb_public_review_contract(
        {
            "summary": {
                "source_row_count": 20,
                "covered_count": 8,
                "missing_review_count": 12,
            }
        }
    )

    assert payload["lane"] == "gwb"
    assert payload["evidence_bundle"]["source_family"] == "gwb_public_review"
    assert payload["promoted_outcomes"]["promoted_count"] == 8
    assert payload["promoted_outcomes"]["review_count"] == 12
    assert payload["derived_products"][0]["role"] == "public_review"


def test_build_gwb_broader_review_contract() -> None:
    payload = build_gwb_broader_review_contract(
        {
            "summary": {
                "source_row_count": 30,
                "covered_count": 18,
                "missing_review_count": 12,
            }
        }
    )

    assert payload["lane"] == "gwb"
    assert payload["evidence_bundle"]["source_family"] == "gwb_broader_review"
    assert payload["promoted_outcomes"]["promoted_count"] == 18
    assert payload["promoted_outcomes"]["review_count"] == 12
    assert payload["derived_products"][0]["role"] == "broader_review"
    payload_with_artifact = build_gwb_broader_review_contract(
        {
            "summary": {
                "source_row_count": 30,
                "covered_count": 18,
                "missing_review_count": 12,
                "broader_review_adjacent": True,
            }
        }
    )
    assert any(
        product["role"] == "parliamentary_reasoning"
        for product in payload_with_artifact["derived_products"]
    )


def test_build_au_fact_review_bundle_contract() -> None:
    payload = build_au_fact_review_bundle_contract(
        fact_report={
            "summary": {"fact_count": 4},
            "abstentions": {"fact_abstentions": 1},
        },
        review_summary={
            "review_queue": [
                {"fact_id": "f2"},
            ]
        },
        source_documents=[{"sourceDocumentId": "doc:1"}],
    )

    assert payload["lane"] == "au"
    assert payload["evidence_bundle"]["source_family"] == "au_fact_review_bundle"
    assert payload["promoted_outcomes"]["promoted_count"] == 2
    assert payload["promoted_outcomes"]["review_count"] == 1
    assert payload["promoted_outcomes"]["abstained_count"] == 1
    assert payload["derived_products"][0]["role"] == "fact_review_bundle"
    assert any(row["role"] == "legal_follow_graph" for row in payload["derived_products"])


def test_build_wikidata_migration_pack_contract() -> None:
    payload = build_wikidata_migration_pack_contract(
        {
            "source_slice": {"window_ids": ["t1_previous", "t2_current"]},
            "summary": {
                "candidate_count": 3,
                "checked_safe_subset": ["a", "b"],
                "abstained": ["c"],
                "requires_review_count": 2,
            },
        }
    )

    assert payload["lane"] == "wikidata_nat"
    assert payload["evidence_bundle"]["source_count"] == 2
    assert payload["promoted_outcomes"]["promoted_count"] == 2
    assert payload["promoted_outcomes"]["abstained_count"] == 1
    assert payload["derived_products"][0]["role"] == "migration_review_pack"


def test_build_product_gate_promotes_when_only_promoted_pressure_exists() -> None:
    gate = build_product_gate(
        lane="au",
        product_ref="au_public_handoff_v1",
        compiler_contract={
            "promoted_outcomes": {
                "promoted_count": 2,
                "review_count": 0,
                "abstained_count": 0,
            },
            "derived_products": [{"role": "operator_handoff"}],
        },
    )

    assert gate["decision"] == "promote"
    assert gate["reason"] == "promoted_outcomes_without_open_pressure"
    assert gate["evidence"]["product_roles"] == ["operator_handoff"]


def test_build_product_gate_audits_mixed_pressure() -> None:
    gate = build_product_gate(
        lane="gwb",
        product_ref="gwb_public_review_v1",
        compiler_contract={
            "promoted_outcomes": {
                "promoted_count": 8,
                "review_count": 12,
                "abstained_count": 0,
            },
            "derived_products": [{"role": "public_review"}],
        },
    )

    assert gate["decision"] == "audit"
    assert gate["reason"] == "mixed_promote_review_or_abstain_pressure"


def test_build_product_gate_abstains_when_no_promoted_outcomes_exist() -> None:
    gate = build_product_gate(
        lane="wikidata_nat",
        product_ref="wikidata_migration_pack",
        compiler_contract={
            "promoted_outcomes": {
                "promoted_count": 0,
                "review_count": 4,
                "abstained_count": 2,
            },
            "derived_products": [{"role": "migration_review_pack"}],
        },
    )

    assert gate["decision"] == "abstain"
    assert gate["reason"] == "no_promoted_outcomes"


def test_normalize_promoted_outcomes_preserves_explicit_values() -> None:
    normalized = normalize_promoted_outcomes(
        PromotedOutcomeContract(
            outcome_family="procedural_review_outcomes",
            promoted_count=2,
            review_count=1,
            abstained_count=1,
            outcome_labels=("captured", "review_queue", "abstained"),
        )
    )

    assert normalized == {
        "outcome_family": "procedural_review_outcomes",
        "promoted_count": 2,
        "review_count": 1,
        "abstained_count": 1,
        "outcome_labels": ["captured", "review_queue", "abstained"],
    }


def test_normalize_promoted_outcomes_fails_closed_on_malformed_input() -> None:
    normalized = normalize_promoted_outcomes(
        {
            "outcome_family": None,
            "promoted_count": "bad",
            "review_count": "3",
            "abstained_count": object(),
            "outcome_labels": ["covered", "covered", "", None, "review_required"],
        }
    )

    assert normalized == {
        "outcome_family": "",
        "promoted_count": 0,
        "review_count": 3,
        "abstained_count": 0,
        "outcome_labels": ["covered", "review_required"],
    }
