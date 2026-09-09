from __future__ import annotations

from src.ontology.wikidata_nat_hf_selector import _evaluate_manifest
from src.ontology.wikidata_nat_residual_bound_acquisition import (
    assess_acquisition_for_recomputation,
    build_bound_coverage_demand,
    build_target_property_coverage_residual,
)


def _row(qid: str, row_ref: str) -> dict:
    return {
        "row_ref": row_ref,
        "qid": qid,
        "target_property": "P14143",
        "source_revision_reference": "rev:test",
        "required_producer": "acquire_source_support",
        "selector_class": "zelph_hf_selector",
    }


def _manifest() -> dict:
    return {
        "manifestVersion": "zelph-hf-layout/v2",
        "createdAtUtc": "2026-06-30T17:54:09Z",
        "transport": {"primary": "hf-object-fetch"},
        "capabilities": {
            "selectedChunkRead": True,
            "nodeRouteIndex": False,
            "fullReasoningSafe": False,
        },
        "layoutPlan": {"isCanonical": True},
    }


def _selector() -> dict:
    return {
        "candidate_only": True,
        "full_reasoning_required": False,
        "operations": ["node_route_selection", "partial_loading"],
        "qids": ["Q1", "Q2"],
        "properties": ["P14143", "P854"],
        "required_outputs": [
            "statement_snapshot",
            "qualifier_snaks",
            "reference_snaks",
            "source_revision_lineage",
            "content_address",
        ],
    }


def test_bound_demand_names_exact_live_residual_and_never_claims_payment() -> None:
    residual = build_target_property_coverage_residual(_row("Q1", "row:1"))
    demand = build_bound_coverage_demand(residual, task_ref="task:1")

    assert residual["subject_qid"] == "Q1"
    assert residual["property"] == "P14143"
    assert residual["missing_coordinate"] == "targetPropertyFamily"
    assert residual["formal_producer_class"] == "empiricalEvidenceProducer"
    assert residual["required_coverage_basis"] == "native_full_statement_family"
    assert residual["truthy_projection_sufficient_for_coverage"] is False
    assert demand["live_residual_ref"] == residual["residual_ref"]
    assert demand["exact_subject_qid"] == "Q1"
    assert demand["exact_property"] == "P14143"
    assert demand["coverage_basis"] == "native_full_statement_family"
    assert demand["truthy_projection_accepted_as_coverage_basis"] is False
    assert demand["coverage_payment_claimed"] is False
    assert demand["migration_authority"] is False


def test_partial_union_identity_scan_progresses_resolved_subset_only() -> None:
    fetched: list[list[str]] = []

    def partial_scan(_manifest: dict, qids: list[str]) -> dict:
        assert qids == ["Q1", "Q2"]
        return {
            "status": "partial",
            "resolved_qids": {"Q1": 101},
            "resolved_qid_chunks": {"Q1": 1},
            "qid_route_cache_seed": {
                "Q1": {"zelph_node_id": 101, "node_of_name_chunk": 1}
            },
            "unresolved_qids": ["Q2"],
            "network_performed": True,
        }

    def statement_fetcher(qids: list[str], properties: list[str]) -> dict:
        fetched.append(list(qids))
        assert qids == ["Q1"]
        assert properties == ["P14143", "P854"]
        return {
            "statement_snapshot": {
                "Q1": {
                    "claims": {
                        "P14143": [
                            {"id": "statement:1", "mainsnak": {"snaktype": "value"}}
                        ]
                    }
                }
            },
            "qualifier_snaks": {"Q1": {}},
            "reference_snaks": {"Q1": {}},
            "source_revision_lineage": {"Q1": {"revid": 1}},
            "content_address": "sha256:test",
        }

    result = _evaluate_manifest(
        _selector(),
        manifest=_manifest(),
        headers={},
        partial_scan_resolver=partial_scan,
        statement_fetcher=statement_fetcher,
    )

    assert fetched == [["Q1"]]
    assert result["execution_outcome"] == "executed_with_output"
    receipt = result["executor_receipt"]
    assert receipt["partial_identity_subset"] is True
    assert receipt["statement_fetch_qids"] == ["Q1"]
    assert receipt["unresolved_qids"] == ["Q2"]
    assert result["outputs"]["statement_snapshot"].keys() == {"Q1"}


def test_recomputation_is_qid_local_and_can_pay_only_coverage_coordinate() -> None:
    result = {
        "result_ref": "result:shared",
        "execution_outcome": "executed_with_output",
        "executor_receipt": {
            "projection_properties": ["P14143", "P854"],
            "partial_read": {
                "resolved_qids": {"Q1": 101},
                "unresolved_qids": ["Q2"],
            },
        },
        "outputs": {
            "statement_snapshot": {
                "Q1": {"revid": 1, "claims": {}}
            }
        },
    }
    q1 = build_target_property_coverage_residual(_row("Q1", "row:1"))
    q2 = build_target_property_coverage_residual(_row("Q2", "row:2"))

    q1_assessment = assess_acquisition_for_recomputation(q1, result)
    q2_assessment = assess_acquisition_for_recomputation(q2, result)

    assert q1_assessment["observation_state"] == "coverage_recomputed_family_absent"
    assert q1_assessment["qid_identity_resolved"] is True
    assert q1_assessment["exact_property_was_requested"] is True
    assert q1_assessment["coverage_basis"] == "native_full_statement_family"
    assert q1_assessment["truthy_projection_used_for_coverage"] is False
    assert q1_assessment["property_family_status"] == "absent"
    assert q1_assessment["recomputed_coverage_status"] == "complete"
    assert q1_assessment["coverage_coordinate_paid"] is True
    assert q1_assessment["source_support_paid"] is False
    assert q1_assessment["source_authority_evaluation_required"] is True
    assert q1_assessment["consumer_closure_claimed"] is False

    assert q2_assessment["observation_state"] == "still_open_subject_identity_unresolved"
    assert q2_assessment["qid_identity_unresolved"] is True
    assert q2_assessment["coverage_coordinate_paid"] is False
    assert q2_assessment["source_support_paid"] is False


def test_present_property_also_pays_only_exact_coverage_coordinate() -> None:
    residual = build_target_property_coverage_residual(_row("Q1", "row:1"))
    result = {
        "result_ref": "result:present",
        "execution_outcome": "executed_with_output",
        "executor_receipt": {
            "projection_properties": ["P14143"],
            "partial_read": {"resolved_qids": {"Q1": 101}, "unresolved_qids": []},
        },
        "outputs": {
            "statement_snapshot": {
                "Q1": {
                    "revid": 2,
                    "claims": {
                        "P14143": [
                            {"id": "statement:1", "mainsnak": {"snaktype": "value"}}
                        ]
                    },
                }
            }
        },
    }

    assessment = assess_acquisition_for_recomputation(residual, result)
    assert assessment["observation_state"] == "coverage_recomputed_family_present"
    assert assessment["property_family_status"] == "present"
    assert assessment["recomputed_coverage_status"] == "complete"
    assert assessment["native_statement_count"] == 1
    assert assessment["observed_native_snak_types"] == ["value"]
    assert assessment["concrete_value_observed"] is True
    assert assessment["coverage_coordinate_paid"] is True
    assert assessment["source_support_paid"] is False
    assert assessment["semantic_promotion_performed"] is False


def test_novalue_is_explicit_family_presence_not_family_absence() -> None:
    residual = build_target_property_coverage_residual(_row("Q1", "row:1"))
    result = {
        "result_ref": "result:novalue",
        "execution_outcome": "executed_with_output",
        "executor_receipt": {
            "projection_properties": ["P14143"],
            "partial_read": {"resolved_qids": {"Q1": 101}, "unresolved_qids": []},
        },
        "outputs": {
            "statement_snapshot": {
                "Q1": {
                    "revid": 3,
                    "claims": {
                        "P14143": [
                            {
                                "id": "statement:novalue",
                                "mainsnak": {"snaktype": "novalue"},
                            }
                        ]
                    },
                }
            }
        },
    }

    assessment = assess_acquisition_for_recomputation(residual, result)
    assert assessment["coverage_coordinate_paid"] is True
    assert assessment["property_family_status"] == "present"
    assert assessment["explicit_novalue_observed"] is True
    assert assessment["concrete_value_observed"] is False
    assert assessment["novalue_equals_family_absence"] is False


def test_somevalue_is_explicit_family_presence_not_concrete_value() -> None:
    residual = build_target_property_coverage_residual(_row("Q1", "row:1"))
    result = {
        "result_ref": "result:somevalue",
        "execution_outcome": "executed_with_output",
        "executor_receipt": {
            "projection_properties": ["P14143"],
            "partial_read": {"resolved_qids": {"Q1": 101}, "unresolved_qids": []},
        },
        "outputs": {
            "statement_snapshot": {
                "Q1": {
                    "revid": 4,
                    "claims": {
                        "P14143": [
                            {
                                "id": "statement:somevalue",
                                "mainsnak": {"snaktype": "somevalue"},
                            }
                        ]
                    },
                }
            }
        },
    }

    assessment = assess_acquisition_for_recomputation(residual, result)
    assert assessment["coverage_coordinate_paid"] is True
    assert assessment["property_family_status"] == "present"
    assert assessment["explicit_somevalue_observed"] is True
    assert assessment["concrete_value_observed"] is False


def test_truthy_projection_cannot_substitute_for_native_family_coverage() -> None:
    residual = build_target_property_coverage_residual(_row("Q1", "row:1"))
    demand = build_bound_coverage_demand(residual, task_ref="task:1")
    assert "native full statement-family" in demand["required_representation"]
    assert demand["truthy_projection_accepted_as_coverage_basis"] is False
