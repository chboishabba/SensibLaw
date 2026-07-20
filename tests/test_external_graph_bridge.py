from __future__ import annotations

import json
from pathlib import Path

import pytest

from sensiblaw import (
    attach_receipt,
    build_world_model,
    project_linkage_case,
    project_review_surface,
)
from src.policy.external_graph_bridge import (
    build_bounded_type_closure_pressure,
    build_external_bridge_candidate,
    build_external_bridge_decision,
    build_external_graph_context,
    build_external_pressure_result,
    build_expected_property_pressure,
    build_graph_view,
    build_graph_view_from_transport,
)
from src.policy.wikibase_entity_export_adapter import build_entity_export_observation
from src.policy.world_model import build_state_node


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "wikidata"


def _transport_view() -> dict[str, object]:
    return {
        "artifact_identity": {
            "contractVersion": "shared-shard-artifact/v1",
            "artifactId": "wikidata-20260309-all-pruned",
            "artifactRevision": "revision:example",
            "artifactClass": "zelph-graph",
        },
        "selectors": ["direct-shard=left-000000", "direct-shard=right-000000"],
        "selected_sections": ["left", "right"],
        "selected_shards": [
            {"shardId": "left-000000", "section": "left", "sizeBytes": 12},
            {"shardId": "right-000000", "section": "right", "sizeBytes": 18},
        ],
        "completeness": "partial",
        "subset_of_artifact": True,
    }


def test_graph_view_from_transport_keeps_bounded_coverage_explicit() -> None:
    graph_view = build_graph_view_from_transport(
        _transport_view(), graph_view_id="graph:pruned:0"
    )

    assert graph_view["coverage_state"] == "incomplete"
    assert graph_view["selected_bytes"] == 30
    assert graph_view["candidate_only"] is True
    assert graph_view["complete_closure"] is False
    assert graph_view["source"]["selectors"] == [
        "direct-shard=left-000000",
        "direct-shard=right-000000",
    ]


def test_complete_graph_view_requires_policy_coverage_and_receipt() -> None:
    with pytest.raises(ValueError, match="complete graph views require"):
        build_graph_view(
            graph_view_id="graph:complete",
            artifact_id="artifact",
            artifact_revision="revision",
            coverage_state="complete",
        )

    graph_view = build_graph_view(
        graph_view_id="graph:complete",
        artifact_id="artifact",
        artifact_revision="revision",
        coverage_state="complete",
        coverage_policy={"query_scope": "declared"},
        completeness_receipt_ref="receipt:complete",
    )
    assert graph_view["complete_closure"] is True
    assert graph_view["candidate_only"] is False

    with pytest.raises(ValueError, match="complete graph views require"):
        build_external_graph_context(
            model_id="bad:complete",
            graph_views=[
                {
                    "graph_view_id": "bad:complete",
                    "artifact_id": "artifact",
                    "artifact_revision": "revision",
                    "coverage_state": "complete",
                }
            ],
        )


def test_external_graph_context_projects_reviewable_entity_event_and_pressure_paths() -> (
    None
):
    graph_view = build_graph_view_from_transport(
        _transport_view(), graph_view_id="graph:pruned:0"
    )
    entity = build_state_node(
        node_id="entity:local:brisbane",
        node_kind="entity_candidate",
        label="Brisbane",
        source_anchor_ids=["source:brisbane"],
    )
    event = build_state_node(
        node_id="event:local:capital-designation",
        node_kind="event_candidate",
        label="Local capital-designation event",
        source_anchor_ids=["source:event"],
    )
    entity_bridge = build_external_bridge_candidate(
        bridge_candidate_id="bridge:entity:brisbane",
        subject_ref=entity["node_id"],
        subject_kind="entity",
        bridge_namespace="wikidata",
        external_ref="Q34932",
        attachment_kind="same_entity",
        graph_view_ref=graph_view["graph_view_id"],
        external_revision_ref="revision:example",
        basis=[{"source_anchor_id": "source:brisbane", "match": "label_and_context"}],
        candidate_status="review_required",
    )
    event_bridge = build_external_bridge_candidate(
        bridge_candidate_id="bridge:event:capital-designation",
        subject_ref=event["node_id"],
        subject_kind="event",
        bridge_namespace="wikidata",
        external_ref="Q34932",
        attachment_kind="related_concept",
        graph_view_ref=graph_view["graph_view_id"],
        candidate_status="review_required",
    )
    decision = build_external_bridge_decision(
        bridge_decision_id="decision:entity:brisbane",
        bridge_candidate_ref=entity_bridge["bridge_candidate_id"],
        decision="accepted",
        review_basis=[{"reviewer": "fixture", "basis": "source_and_revision"}],
    )
    pressure = build_external_pressure_result(
        pressure_result_id="pressure:brisbane:city-shape",
        target_ref=entity["node_id"],
        graph_view_ref=graph_view["graph_view_id"],
        profile_id="city_expected_shape",
        outcome="warning",
        diagnostics=[
            {"kind": "expected_shape", "field": "P1376", "strength": "conditional"}
        ],
    )
    context = build_external_graph_context(
        model_id="fixture:external-graph",
        graph_views=[graph_view],
        entities=[entity],
        events=[event],
        bridge_candidates=[entity_bridge, event_bridge],
        bridge_decisions=[decision],
        pressure_results=[pressure],
        provenance_graph=[
            {"source": "fixture", "manifest_revision": "revision:example"}
        ],
    )

    world_model = build_world_model(context)
    review_surface = project_review_surface(world_model)
    linkage_case = project_linkage_case(world_model)
    receipt = attach_receipt(linkage_case)

    assert world_model["lane_family"] == "generic_input"
    assert world_model["external_graph_views"][0]["coverage_state"] == "incomplete"
    assert (
        world_model["external_bridge_candidates"][0]["subject_ref"] == entity["node_id"]
    )
    assert world_model["external_bridge_candidates"][0]["legal_authority"] is False
    assert world_model["external_bridge_decisions"][0]["authority_inherited"] is False
    assert (
        review_surface["payload"]["external_pressure_results"][0]["diagnostic_only"]
        is True
    )
    layers = {node["layer"] for node in linkage_case["payload"]["nodes"]}
    assert {
        "external_graph_view",
        "external_bridge_candidate",
        "external_pressure_diagnostic",
    } <= layers
    assert (
        receipt["linkage_depth_receipt"]["diagnostics"]["linkage_depth_status"]
        == "complete"
    )


def test_revision_pinned_cohort_d_observation_abstains_from_global_missing_type_claim() -> (
    None
):
    """A Nat fixture supplies evidence; generic carriers own the semantics."""

    tranche = json.loads(
        (FIXTURE_ROOT / "wikidata_nat_cohort_a_live_tranche_20260401.json").read_text(
            encoding="utf-8"
        )
    )
    q178_revision = next(
        row["newer_revid"]
        for row in tranche["revision_pairs"]
        if row["qid"] == "Q1785637"
    )
    entity = build_state_node(
        node_id="entity:local:q1785637",
        node_kind="entity_candidate",
        label="Apoteket",
        source_anchor_ids=["packet:review-packet:f451ac11e012b114"],
    )
    graph_view = build_graph_view(
        graph_view_id="graph:wikidata:q1785637:2443793937",
        artifact_id="wikidata-entity-export:Q1785637",
        artifact_revision=str(q178_revision),
        coverage_state="incomplete",
        selected_sections=["claims"],
        selected_chunks=[{"entity_ref": "Q1785637", "revision": q178_revision}],
        coverage_policy={"scope": "one revision-pinned entity export"},
        unresolved_coverage=[
            {
                "kind": "unexamined_graph_coverage",
                "reason": "entity export is not a closed type graph",
            }
        ],
        source={"source_kind": "revision_pinned_entity_export"},
    )
    bridge = build_external_bridge_candidate(
        bridge_candidate_id="bridge:q1785637:identity",
        subject_ref=entity["node_id"],
        subject_kind="entity",
        bridge_namespace="wikidata",
        external_ref="Q1785637",
        attachment_kind="same_entity",
        graph_view_ref=graph_view["graph_view_id"],
        external_revision_ref=str(q178_revision),
        basis=[
            {
                "source_anchor_id": "packet:review-packet:f451ac11e012b114",
                "match": "revision_pinned_qid",
            }
        ],
        candidate_status="review_required",
    )
    decision = build_external_bridge_decision(
        bridge_decision_id="decision:q1785637:identity",
        bridge_candidate_ref=bridge["bridge_candidate_id"],
        decision="accepted",
        review_basis=[{"basis": "existing Nat packet plus revision-pinned QID"}],
    )
    pressure = build_expected_property_pressure(
        pressure_result_id="pressure:q1785637:direct-type",
        target_ref=entity["node_id"],
        graph_view_ref=graph_view["graph_view_id"],
        profile_id="direct_type_presence",
        coverage_state=graph_view["coverage_state"],
        expected_properties=[{"property_ref": "P31", "strength": "strong_expected"}],
        observed_properties=[
            {
                "property_ref": "P31",
                "state": "observed_absent",
                "evidence_ref": f"wikidata-entity-export:Q1785637:{q178_revision}",
            }
        ],
    )
    context = build_external_graph_context(
        model_id="fixture:q1785637:cohort-d",
        graph_views=[graph_view],
        entities=[entity],
        bridge_candidates=[bridge],
        bridge_decisions=[decision],
        pressure_results=[pressure],
        provenance_graph=[
            {
                "packet_id": "review-packet:f451ac11e012b114",
                "entity_ref": "Q1785637",
                "entity_revision": q178_revision,
            }
        ],
    )

    world_model = build_world_model(context)
    review_surface = project_review_surface(world_model)
    receipt = attach_receipt(project_linkage_case(world_model))

    assert graph_view["candidate_only"] is True
    assert bridge["legal_authority"] is False
    assert decision["authority_inherited"] is False
    assert pressure["outcome"] == "abstain"
    assert pressure["residuals"] == [
        {
            "kind": "coverage_limited_absence",
            "property_ref": "P31",
            "reason": "observed absence is not global absence in an incomplete graph view",
        }
    ]
    assert (
        review_surface["payload"]["external_pressure_results"][0]["outcome"]
        == "abstain"
    )
    assert (
        receipt["linkage_depth_receipt"]["diagnostics"]["linkage_depth_status"]
        == "complete"
    )


def test_revision_pinned_entity_export_observation_drives_direct_type_pressure() -> (
    None
):
    """The provider adapter yields evidence; generic bridge records own review."""

    entity_export = {
        "entities": {
            "Q1785637": {
                "id": "Q1785637",
                "lastrevid": 2443793937,
                "labels": {"en": {"language": "en", "value": "Apoteket"}},
                "aliases": {"en": [{"language": "en", "value": "Apoteket AB"}]},
                "claims": {
                    "P31": [{"id": "Q1785637$direct-type"}],
                    "P17": [{"id": "Q1785637$country"}],
                },
            }
        }
    }
    observation = build_entity_export_observation(
        entity_export,
        external_ref="Q1785637",
        external_revision_ref="2443793937",
        source_ref="https://www.wikidata.org/wiki/Special:EntityData/Q1785637.json?revision=2443793937",
    )
    entity = build_state_node(
        node_id="entity:local:q1785637",
        node_kind="entity_candidate",
        label="Apoteket",
        source_anchor_ids=["packet:review-packet:f451ac11e012b114"],
    )
    graph_view = build_graph_view(
        graph_view_id="graph:wikidata:q1785637:2443793937:entity-export",
        artifact_id="wikidata-entity-export:Q1785637",
        artifact_revision=observation["external_revision_ref"],
        coverage_state="incomplete",
        selected_sections=["entity_export", "claims"],
        selected_chunks=[
            {
                "entity_ref": observation["external_ref"],
                "revision": observation["external_revision_ref"],
                "property_count": len(observation["observed_properties"]),
            }
        ],
        coverage_policy={"scope": "one revision-pinned entity export"},
        unresolved_coverage=[
            {
                "kind": "unexamined_graph_coverage",
                "reason": "entity export does not close superclass coverage",
            }
        ],
        source=observation["source"],
    )
    bridge = build_external_bridge_candidate(
        bridge_candidate_id="bridge:q1785637:entity-export",
        subject_ref=entity["node_id"],
        subject_kind="entity",
        bridge_namespace="wikidata",
        external_ref=observation["external_ref"],
        attachment_kind="same_entity",
        graph_view_ref=graph_view["graph_view_id"],
        external_revision_ref=observation["external_revision_ref"],
        basis=[
            {
                "source_anchor_id": "packet:review-packet:f451ac11e012b114",
                "match": "revision_pinned_label_and_qid",
            }
        ],
        candidate_status="review_required",
        adapter_id=observation["provider_id"],
    )
    event = build_state_node(
        node_id="event:local:q1785637:review",
        node_kind="event_candidate",
        label="Local review event concerning Apoteket",
        source_anchor_ids=["packet:review-packet:f451ac11e012b114"],
    )
    event_bridge = build_external_bridge_candidate(
        bridge_candidate_id="bridge:q1785637:review-event",
        subject_ref=event["node_id"],
        subject_kind="event",
        bridge_namespace="wikidata",
        external_ref=observation["external_ref"],
        attachment_kind="related_concept",
        graph_view_ref=graph_view["graph_view_id"],
        external_revision_ref=observation["external_revision_ref"],
        basis=[
            {
                "source_anchor_id": "packet:review-packet:f451ac11e012b114",
                "match": "event_mentions_revision_pinned_entity",
            }
        ],
        candidate_status="review_required",
        adapter_id=observation["provider_id"],
    )
    decision = build_external_bridge_decision(
        bridge_decision_id="decision:q1785637:entity-export",
        bridge_candidate_ref=bridge["bridge_candidate_id"],
        decision="accepted",
        reviewer_ref="fixture:deterministic-revision-review",
        review_basis=[
            {
                "basis": "local packet anchor plus revision-pinned label and external reference",
            }
        ],
    )
    pressure = build_expected_property_pressure(
        pressure_result_id="pressure:q1785637:direct-type:entity-export",
        target_ref=entity["node_id"],
        graph_view_ref=graph_view["graph_view_id"],
        profile_id="direct_type_presence",
        coverage_state=graph_view["coverage_state"],
        expected_properties=[{"property_ref": "P31", "strength": "strong_expected"}],
        observed_properties=observation["observed_properties"],
    )
    context = build_external_graph_context(
        model_id="fixture:q1785637:entity-export",
        graph_views=[graph_view],
        entities=[entity],
        events=[event],
        bridge_candidates=[bridge, event_bridge],
        bridge_decisions=[decision],
        pressure_results=[pressure],
        provenance_graph=[observation],
    )
    world_model = build_world_model(context)
    review_surface = project_review_surface(world_model)
    receipt = attach_receipt(project_linkage_case(world_model))

    assert observation["labels"] == [{"language": "en", "value": "Apoteket"}]
    assert observation["aliases"] == [{"language": "en", "value": "Apoteket AB"}]
    assert observation["observed_properties"][0]["property_ref"] == "P17"
    assert pressure["outcome"] == "compatible"
    assert "evidence_ref" not in pressure["diagnostics"][0]
    assert bridge["role_authority"] is False
    assert event_bridge["attachment_kind"] == "related_concept"
    assert decision["authority_inherited"] is False
    assert (
        review_surface["payload"]["external_bridge_candidates"][0]["external_ref"]
        == "Q1785637"
    )
    assert (
        receipt["linkage_depth_receipt"]["diagnostics"]["linkage_depth_status"]
        == "complete"
    )


def test_revision_pinned_entity_export_rejects_wrong_revision_or_entity() -> None:
    entity_export = {
        "entities": {
            "Q1785637": {"id": "Q1785637", "lastrevid": 2443793937, "claims": {}}
        }
    }
    with pytest.raises(ValueError, match="revision"):
        build_entity_export_observation(
            entity_export,
            external_ref="Q1785637",
            external_revision_ref="2443793938",
        )
    with pytest.raises(ValueError, match="does not contain"):
        build_entity_export_observation(
            entity_export,
            external_ref="Q1",
            external_revision_ref="2443793937",
        )


def test_bounded_type_closure_requires_direct_type_and_abstains_when_incomplete() -> (
    None
):
    compatible = build_bounded_type_closure_pressure(
        pressure_result_id="pressure:organisation:closure",
        target_ref="entity:local:q1785637",
        graph_view_ref="graph:closure",
        profile_id="organisation_direct_superclass",
        coverage_state="incomplete",
        direct_type_refs=["Q4830453", "Q61676930"],
        closure_observations=[
            {
                "type_ref": "Q4830453",
                "superclass_refs": ["Q43229", "Q155076"],
                "evidence_refs": ["Q4830453$P279:revision:2514362964"],
            },
            {
                "type_ref": "Q61676930",
                "superclass_refs": ["Q507619", "Q13107184"],
                "evidence_refs": ["Q61676930$P279:revision:2486376441"],
            },
        ],
        expected_superclass_refs=["Q43229"],
    )
    abstained = build_bounded_type_closure_pressure(
        pressure_result_id="pressure:unobserved:closure",
        target_ref="entity:local:unknown",
        graph_view_ref="graph:closure",
        profile_id="organisation_direct_superclass",
        coverage_state="incomplete",
        direct_type_refs=["Q4830453"],
        closure_observations=[],
        expected_superclass_refs=["Q43229"],
    )

    assert compatible["outcome"] == "compatible"
    assert compatible["diagnostics"][0]["property_ref"] == "P279"
    assert abstained["outcome"] == "abstain"
    assert {row["kind"] for row in abstained["residuals"]} == {
        "type_closure_observation_missing",
        "coverage_limited_superclass_expectation",
    }


def test_expected_property_pressure_is_reusable_across_entity_profiles() -> None:
    missing_company_property = build_expected_property_pressure(
        pressure_result_id="pressure:company:direct-type",
        target_ref="entity:company",
        graph_view_ref="graph:complete:company",
        profile_id="organisation_shape",
        coverage_state="complete",
        expected_properties=[{"property_ref": "P31", "strength": "strong_expected"}],
        observed_properties=[{"property_ref": "P31", "state": "observed_absent"}],
    )
    present_city_property = build_expected_property_pressure(
        pressure_result_id="pressure:city:coordinates",
        target_ref="entity:city",
        graph_view_ref="graph:complete:city",
        profile_id="city_shape",
        coverage_state="complete",
        expected_properties=[{"property_ref": "P625", "strength": "common"}],
        observed_properties=[{"property_ref": "P625", "state": "present"}],
    )

    assert missing_company_property["outcome"] == "warning"
    assert missing_company_property["residuals"] == []
    assert present_city_property["outcome"] == "compatible"
