from __future__ import annotations

import pytest

from src.policy.domain_invariants import build_invariant_revision
from src.policy.external_graph_bridge import build_graph_view
from src.policy.nat_zelph_peer_pipeline import run_nat_zelph_peer_pipeline
from src.policy.pruned_graph_preservation import build_query_family_preservation_receipt
from src.policy.zelph_routed_relation_observations import (
    build_zelph_routed_relation_observations,
)


def _entity() -> dict[str, object]:
    return {
        "entities": {
            "QCOMPANY": {
                "id": "QCOMPANY",
                "lastrevid": 42,
                "claims": {
                    "P31": [
                        {
                            "id": "QCOMPANY$P31",
                            "rank": "normal",
                            "mainsnak": {
                                "snaktype": "value",
                                "datatype": "wikibase-item",
                                "datavalue": {"value": {"id": "Q783794"}},
                            },
                        }
                    ],
                    "P5991": [
                        {
                            "id": "QCOMPANY$P5991",
                            "rank": "normal",
                            "mainsnak": {
                                "snaktype": "value",
                                "datatype": "quantity",
                                "datavalue": {"value": {"amount": "+1000", "unit": "1"}},
                            },
                            "qualifiers": {
                                "P459": [
                                    {
                                        "snaktype": "value",
                                        "datatype": "wikibase-item",
                                        "datavalue": {"value": {"id": "Q56296245"}},
                                    }
                                ]
                            },
                        }
                    ],
                },
            }
        }
    }


def _graph_view() -> dict[str, object]:
    return build_graph_view(
        graph_view_id="graph:qcompany",
        artifact_id="zelph:wikidata-pruned",
        artifact_revision="2026-03-09",
        coverage_state="complete",
        selected_sections=["left", "right", "nameOfNode"],
        selected_chunks=[{"which": "left", "chunkIndex": 1, "sizeBytes": 10}],
        selected_bytes=10,
        coverage_policy={"profile": "type-module", "seed": "QCOMPANY"},
        completeness_receipt_ref="coverage:graph:qcompany",
    )


def _preservation() -> dict[str, object]:
    return build_query_family_preservation_receipt(
        source_artifact_ref="wikidata:full",
        source_revision_ref="2026-03-09",
        pruned_artifact_ref="zelph:wikidata-pruned",
        pruned_revision_ref="2026-03-09",
        query_family_ref="query:p31-p279-type-closure",
        preservation_state="sound_only",
        soundness_receipt_ref="proof:type-positive-sound",
        covered_relations=["P31", "P279"],
    )


def _routed(graph_view: dict[str, object]) -> dict[str, object]:
    return build_zelph_routed_relation_observations(
        graph_view=graph_view,
        execution_receipt_ref="zelph-exec:qcompany:type",
        selectors=["route-node:QCOMPANY"],
        query_family_ref="query:p31-p279-type-closure",
        subject_qid="QCOMPANY",
        relation_rows=[
            {
                "source_ref": "QCOMPANY",
                "property_id": "P31",
                "object_ref": "Q783794",
            },
            {
                "source_ref": "Q783794",
                "property_id": "P279",
                "object_ref": "Q4830453",
            },
        ],
    )


def _snapshot() -> dict[str, object]:
    # Intentionally sparse: the item surface carries many more conditioned
    # coordinates, so the resulting peer residual should be partial, not exact.
    result = build_invariant_revision(
        domain_invariant_ref="domain:climate",
        policy_model_ref="policy:P14143",
        policy_requirements=[
            {
                "feature": "property_statement_presence",
                "condition": "P14143",
                "value": "no_statement_observed",
            }
        ],
        contribution_receipts=[
            {
                "member": {
                    "candidate_ref": "candidate:reviewed",
                    "source_revision_ref": "wikidata:QREVIEWED@1",
                    "review_disposition": "confirmed_model_conformant",
                    "review_decision_ref": "review:1",
                    "reviewer_authority_ref": "reviewer:1",
                    "coverage_state": "observed",
                    "feature_contributions": [
                        {
                            "feature": "property_statement_presence",
                            "condition": "P14143",
                            "value": "no_statement_observed",
                        }
                    ],
                }
            }
        ],
        reviewer_authority_ref="reviewer:1",
    )
    return result["snapshot"]


def _pressure() -> dict[str, object]:
    return {
        "candidate_ref": "candidate:qcompany:p5991",
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "residuals": [
            {"residual_kind": "target_model", "state": "exact"},
            {
                "residual_kind": "peer_cohort",
                "state": "unresolved",
                "coverage_state": "uninspected",
            },
            {"residual_kind": "temporal", "state": "exact"},
        ],
    }


def test_full_pipeline_builds_type_module_item_surface_and_peer_weld() -> None:
    graph = _graph_view()
    result = run_nat_zelph_peer_pipeline(
        pressure_assessment=_pressure(),
        invariant_snapshot=_snapshot(),
        entity_document=_entity(),
        subject_qid="QCOMPANY",
        entity_revision_ref="42",
        graph_view=graph,
        routed_observations=_routed(graph),
        type_preservation_receipt=_preservation(),
        type_module_receipt_ref="module:qcompany:p31-p279",
        coverage_policy_ref="coverage:nat-climate-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        property_coverage={
            "P31": "observed",
            "P5991": "observed",
            "P14143": "observed",
        },
        qualifier_specs={
            "P5991": {"allowed": ["P459"], "mandatory": ["P459"]},
        },
        qualifier_profile_coverage_state="observed",
        scope_profile_coverage_state="observed",
        revision_alignment_ref="align:42-to-2026-03-09",
    )

    module = result["type_module"]
    assert module["positive_answers_sound"] is True
    assert module["negative_answers_complete"] is False
    assert [row["property_id"] for row in module["relations"]] == ["P31", "P279"]

    surface = result["joined_item_surface"]["item_surface"]
    assert surface["property_inventory"]["no_statement_observed_property_ids"] == [
        "P14143"
    ]
    assert surface["property_inventory"]["explicit_novalue_property_ids"] == []
    assert any(
        row["feature"] == "property_relation"
        and row["condition"] == "P279->Q4830453"
        and row["value"] == "derived"
        for row in surface["peer_features"]
    )

    welded = result["pressure_assessment"]
    residuals = {row["residual_kind"]: row for row in welded["residuals"]}
    assert residuals["target_model"] == {"residual_kind": "target_model", "state": "exact"}
    assert residuals["temporal"] == {"residual_kind": "temporal", "state": "exact"}
    assert residuals["peer_cohort"]["state"] == "partial"
    assert welded["authority"] == "diagnostic_only"
    assert welded["promotion_effect"] == "not_evaluated"
    assert welded["edit_effect"] == "none"


def test_sound_only_type_preservation_cannot_make_negative_answers_complete() -> None:
    graph = _graph_view()
    result = run_nat_zelph_peer_pipeline(
        pressure_assessment=_pressure(),
        invariant_snapshot=_snapshot(),
        entity_document=_entity(),
        subject_qid="QCOMPANY",
        entity_revision_ref="42",
        graph_view=graph,
        routed_observations=_routed(graph),
        type_preservation_receipt=_preservation(),
        type_module_receipt_ref="module:qcompany:p31-p279",
        coverage_policy_ref="coverage:nat-climate-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        property_coverage={"P31": "observed", "P5991": "observed", "P14143": "observed"},
        revision_alignment_ref="align:42-to-2026-03-09",
    )
    assert result["type_module"]["negative_answers_complete"] is False


def test_pipeline_rejects_mismatched_routed_query_family() -> None:
    graph = _graph_view()
    routed = build_zelph_routed_relation_observations(
        graph_view=graph,
        execution_receipt_ref="zelph-exec:qcompany:other",
        relation_rows=[{"property_id": "P31", "object_ref": "Q783794"}],
        query_family_ref="query:other",
        subject_qid="QCOMPANY",
    )
    with pytest.raises(ValueError, match="query family"):
        run_nat_zelph_peer_pipeline(
            pressure_assessment=_pressure(),
            invariant_snapshot=_snapshot(),
            entity_document=_entity(),
            subject_qid="QCOMPANY",
            entity_revision_ref="42",
            graph_view=graph,
            routed_observations=routed,
            type_preservation_receipt=_preservation(),
            type_module_receipt_ref="module:qcompany:p31-p279",
            coverage_policy_ref="coverage:nat-climate-v1",
            required_property_ids=["P31"],
            revision_alignment_ref="align:42-to-2026-03-09",
        )
