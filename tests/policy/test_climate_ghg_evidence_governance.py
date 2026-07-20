from __future__ import annotations

import json

import pytest

from src.policy.climate_ghg_evidence_governance import (
    build_contract_proposal,
    build_evidence_outputs,
    build_hold_reason_inventory,
)
from src.policy.orthogonal_assessment import validate_review_adjudications
from scripts.materialize_climate_ghg_evidence_governance import materialize


def _assessment(count: int = 5) -> dict:
    statements = []
    for index in range(count):
        statements.append(
            {
                "statement_ref": f"s{index}",
                "family_ref": "f1",
                "semantic_subtype": "organisation_wide_total",
                "axes": {
                    "family_geometry": "atomic",
                    "slot_integrity": "coherent",
                    "component_coverage": "not_applicable",
                    "statement_semantics": "A1_total",
                    "execution_outcome": "eligible",
                },
                "eligibility_predicates": {
                    "enterprise_subject": "true",
                    "exact_annual_period": "true",
                    "target_semantics_fit": "true",
                    "supported_statement_shape": "true",
                    "compatible_method": "true",
                    "compatible_unit": "true",
                    "structurally_adequate_reference": "true",
                    "unique_semantic_slot": "true",
                    "no_target_collision": "true",
                },
            }
        )
    return {
        "assessment_ref": "orthogonal-assessment:test",
        "statements": statements,
        "families": [
            {
                "family_ref": "f1",
                "member_count": count,
                "component_coverage": "unknown",
                "member_statement_refs": [f"s{i}" for i in range(count)],
            }
        ],
    }


def _manifest(assessment: dict) -> dict:
    return {
        "selected_family_refs": ["f1"],
        "families": [
            {
                "family_ref": "f1",
                "statements": assessment["statements"],
            }
        ],
    }


def test_hold_inventory_separates_primary_and_overlapping_reasons() -> None:
    assessment = _assessment(1)
    row = assessment["statements"][0]
    row["axes"]["execution_outcome"] = "hold"
    row["axes"]["slot_integrity"] = "unresolved"
    row["eligibility_predicates"]["exact_annual_period"] = "unresolved"
    report = build_hold_reason_inventory(assessment)
    assert report["hold_statement_count"] == 1
    assert report["primary_reason_counts"] == {"unresolved_semantic_slot": 1}
    assert report["overlapping_reason_counts"]["unresolved_annual_period"] == 1


def test_contract_requires_five_reviewed_eligible_statements() -> None:
    assessment = _assessment(5)
    adjudications = {
        "schema_version": "sl.orthogonal_review_adjudications.v1",
        "status": "complete",
        "assessment_ref": assessment["assessment_ref"],
        "selected_family_refs": ["f1"],
        "statements": [
            {
                "statement_ref": row["statement_ref"],
                "family_ref": "f1",
                "v2_outcome_correct": True,
                "semantic_subtype_correct": True,
                "target_semantics_appropriate": True,
                "qualifiers_preserved": True,
                "qualifier_repair_needed": False,
                "different_target_required": False,
                "hold_reason_correct": None,
            }
            for row in assessment["statements"]
        ],
    }
    proposal = build_contract_proposal(assessment, adjudications)
    assert proposal["contract_status"] == "proposed"
    assert proposal["selected_subtype"] == "organisation_wide_total"
    assert proposal["canary"]["maximum_statement_count"] == 25


def test_review_validation_rejects_duplicate_or_incomplete_complete_sample() -> None:
    assessment = _assessment(2)
    manifest = _manifest(assessment)
    duplicate = {
        "schema_version": "sl.orthogonal_review_adjudications.v1",
        "status": "pending",
        "assessment_ref": assessment["assessment_ref"],
        "statements": [
            {"family_ref": "f1", "statement_ref": "s0"},
            {"family_ref": "f1", "statement_ref": "s0"},
        ],
    }
    with pytest.raises(ValueError, match="duplicate"):
        validate_review_adjudications(
            assessment=assessment, manifest=manifest, adjudications=duplicate
        )

    incomplete = {
        "schema_version": "sl.orthogonal_review_adjudications.v1",
        "status": "complete",
        "assessment_ref": assessment["assessment_ref"],
        "statements": [{"family_ref": "f1", "statement_ref": "s0"}],
    }
    with pytest.raises(ValueError, match="every sampled statement"):
        validate_review_adjudications(
            assessment=assessment, manifest=manifest, adjudications=incomplete
        )


def test_evidence_outputs_include_canonical_sidecar_and_hash_manifest() -> None:
    assessment = _assessment(1)
    outputs = build_evidence_outputs(
        assessment=assessment,
        manifest=_manifest(assessment),
        migration_pack={
            "candidates": [
                {
                    "statement_family_context": {
                        "family_id": "f1",
                        "total_component_relation": "no_total",
                    }
                }
            ]
        },
        rule_coverage={"rules": [], "coverage": {}},
    )
    assert outputs["review_adjudications.json"]["status"] == "pending"
    assert outputs["contract_proposal.json"]["contract_status"] == "diagnostic_only"
    manifest = outputs["evidence_governance_manifest.json"]
    assert sorted(manifest["output_files"]) == sorted(outputs)
    assert set(manifest["output_hashes"]) == set(outputs) - {
        "evidence_governance_manifest.json"
    }


def test_offline_materializer_reuses_identical_output(tmp_path) -> None:
    assessment = _assessment(1)
    assessment_dir = tmp_path / "assessment"
    replay_dir = tmp_path / "replay"
    assessment_dir.mkdir()
    replay_dir.mkdir()
    (assessment_dir / "orthogonal_assessment.json").write_text(
        json.dumps(assessment), encoding="utf-8"
    )
    (assessment_dir / "eligibility_review_manifest.json").write_text(
        json.dumps(_manifest(assessment)), encoding="utf-8"
    )
    (replay_dir / "migration_pack.json").write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "source_statement_id": "s0",
                        "statement_family_context": {
                            "family_id": "f1",
                            "total_component_relation": "no_total",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (replay_dir / "rule_coverage.json").write_text(
        json.dumps({"rules": [], "coverage": {}}), encoding="utf-8"
    )
    output = tmp_path / "evidence"
    assert (
        materialize(
            assessment_dir=assessment_dir, replay_dir=replay_dir, output_dir=output
        )
        == output
    )
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    assert (
        materialize(
            assessment_dir=assessment_dir, replay_dir=replay_dir, output_dir=output
        )
        == output
    )
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
